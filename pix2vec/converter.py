"""Ядро: поиск файлов, запуск воркеров, логирование, отчёт о результатах."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import (
    DEFAULT_PROFILE,
    INPUT_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    SUPPORTED_FORMATS,
    SVG_EXT,
    get_profile,
)


@dataclass
class FileResult:
    """Результат обработки одного файла."""

    name: str
    status: str = "pending"
    detail: str = ""
    duration_svg: str = ""
    time_s: float = 0.0
    ratio: float = 0.0
    size_src: int = 0
    size_svg: int = 0


@dataclass
class BatchReport:
    """Сводный отчёт по всем файлам."""

    ok: int = 0
    skipped: int = 0
    errors: int = 0
    total_size_src: int = 0
    total_size_svg: int = 0
    elapsed: float = 0.0
    results: list = field(default_factory=list)


def find_images(source_dir: Path) -> list[tuple[Path, str]]:
    """Найти в папке (рекурсивно) все картинки поддерживаемых форматов."""
    found: list[tuple[Path, str]] = []
    if not source_dir.exists():
        return found
    for p in sorted(source_dir.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in SUPPORTED_FORMATS:
            found.append((p, SUPPORTED_FORMATS[ext]))
    return found


def convert_directory(
    source_dir: Path,
    output_dir: Path,
    profile_name: str | None = None,
    overwrite: bool = False,
    on_progress=None,
) -> BatchReport:
    """Прогнать папку через конвертацию и вернуть сводный отчёт."""
    get_profile(profile_name)
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    files = find_images(source_dir)
    report = BatchReport()
    t_start = time.perf_counter()

    for i, (src, _fmt) in enumerate(files, start=1):
        if on_progress:
            on_progress(i, len(files), src.name)

        result = _convert_one(src, output_dir, profile_name, overwrite)
        report.results.append(result)

        if result.status == "ok":
            report.ok += 1
            report.total_size_src += result.size_src
            report.total_size_svg += result.size_svg
        elif result.status == "error":
            report.errors += 1
        else:
            report.skipped += 1

    report.elapsed = time.perf_counter() - t_start
    _write_log(report, source_dir)
    return report


def _convert_one(src: Path, output_dir: Path, profile_name: str | None, overwrite: bool) -> FileResult:
    """Конвертировать один файл в изолированном воркер-процессе."""
    result = FileResult(name=src.name)
    try:
        result.size_src = src.stat().st_size
    except OSError:
        result.status = "error"
        result.detail = "не удаётся прочитать файл"
        return result

    out_path = output_dir / f"{src.stem}{SVG_EXT}"
    if not overwrite and out_path.exists():
        result.status = "skip"
        result.detail = "уже существует, используй --overwrite"
        return result

    cmd = [
        sys.executable,
        "-m",
        "pix2vec.worker",
        str(src),
        str(out_path),
        profile_name or DEFAULT_PROFILE,
    ]

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300,
        )
    except OSError as exc:
        result.status = "error"
        result.detail = f"не удалось запустить воркер: {exc}"
        return result

    result.time_s = time.perf_counter() - t0

    if proc.returncode == 0 and out_path.exists():
        try:
            svg_text = out_path.read_text(encoding="utf-8")
        except OSError:
            svg_text = ""
        result.size_svg = out_path.stat().st_size
        from .tracer import svg_size

        w, h = svg_size(svg_text)
        result.duration_svg = f"{w}x{h}"
        result.ratio = (result.size_svg / result.size_src) if result.size_src else 0.0
        result.status = "ok"
        result.detail = out_path.name
        return result

    if proc.returncode == 0:
        result.status = "error"
        result.detail = "воркер завершился без результата"
        return result

    err = (proc.stderr or "").strip().splitlines()
    if proc.returncode == 0xC0000005:
        result.status = "error"
        result.detail = "движок трассировки упал (сегфолт)"
    elif err:
        result.status = "error"
        result.detail = err[-1]
    else:
        result.status = "error"
        result.detail = f"воркер завершился с кодом {proc.returncode}"

    if out_path.exists():
        try:
            out_path.unlink()
        except OSError:
            pass
    return result


def _write_log(report: BatchReport, source_dir: Path) -> None:
    """Сохранить лог запуска в logs/."""
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"run_{stamp}.log"
    lines = [f"Pix2Vec | папка: {source_dir}", "=" * 50]
    for r in report.results:
        if r.status == "ok":
            lines.append(f"[OK]   {r.name} -> {r.detail}  (svg/src={r.ratio:.2f}x, {r.time_s:.2f}s)")
        elif r.status == "error":
            lines.append(f"[FAIL] {r.name}: {r.detail}")
        else:
            lines.append(f"[SKIP] {r.name}")
    lines.append("=" * 50)
    lines.append(
        f"Успешно: {report.ok} | Пропущено: {report.skipped} | Ошибок: {report.errors}"
    )
    lines.append(f"Время: {report.elapsed:.2f}s")
    try:
        log_file.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass
