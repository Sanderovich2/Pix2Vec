"""Консольный интерфейс Pix2Vec.

Примеры:
    python -m pix2vec.main                      # конвертация input/ профилем "color"
    python -m pix2vec.main C:\\path\\to\\images  # своя папка
    python -m pix2vec.main --profile logo
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import DEFAULT_PROFILE, INPUT_DIR, OUTPUT_DIR, PROFILES, get_profile
from .converter import convert_directory

C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"

_WIN_VT_OK: bool | None = None

_BANNER_WIDTH = 50
_BANNER_TITLE = "   Pix2Vec   растровые картинки → векторный SVG   "


def _force_utf8_stdio() -> None:
    """Force UTF-8 output regardless of the active code page."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _stdin_isatty() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def _enable_windows_ansi() -> bool:
    """Enable ANSI escape processing in the classic Windows console."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        handle = kernel32.GetStdHandle(-11)
        if not handle or handle == 0xFFFFFFFFFFFFFFFF:
            return False
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        if mode.value & 0x0004:
            return True
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def _use_color() -> bool:
    """Colors only for a live ANSI-capable console."""
    global _WIN_VT_OK
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        if not sys.stdout.isatty():
            return False
    except (AttributeError, ValueError, OSError):
        return False
    if sys.platform == "win32":
        if _WIN_VT_OK is None:
            _WIN_VT_OK = _enable_windows_ansi()
        return _WIN_VT_OK
    return True


def _c(code: str, text: str) -> str:
    return f"{code}{text}{C_RESET}" if _use_color() else text


def banner() -> None:
    print()
    print(_c(C_CYAN, "  ╔" + "═" * _BANNER_WIDTH + "╗"))
    print(_c(C_CYAN, "  ║") + _c(C_BOLD + C_CYAN, _BANNER_TITLE) + _c(C_CYAN, "║"))
    print(_c(C_CYAN, "  ╚" + "═" * _BANNER_WIDTH + "╝"))
    print()


def progress_bar(done: int, total: int, name: str) -> None:
    cols = shutil.get_terminal_size((100, 24)).columns
    bar_width = max(10, min(cols - 28, 50))
    filled = int(bar_width * done / max(total, 1))
    bar = "█" * filled + "░" * (bar_width - filled)
    short = name if len(name) <= 24 else "…" + name[-23:]
    print(f"\r [{bar}] {done}/{total}  {short:24s}", end="")


def show_menu() -> str | None:
    """Меню профилей: имя режима или None (выход)."""
    names = list(PROFILES)
    while True:
        print(_c(C_BOLD, "  Выбери режим трассировки:"))
        for i, key in enumerate(names, start=1):
            prof = PROFILES[key]
            default = "  " + _c(C_GREEN, "(по умолчанию)") if key == DEFAULT_PROFILE else ""
            print(f"   {i}. {prof['label']}{default}")
            print(f"        {_c(C_CYAN, prof.get('description', ''))}")
        print()
        try:
            choice = input("  → Номер режима [Enter = по умолчанию, q — выход]: ").strip().lower()
        except (EOFError, OSError):
            return None
        if not choice:
            return DEFAULT_PROFILE
        if choice in ("q", "0"):
            return None
        try:
            idx = int(choice)
        except ValueError:
            print(_c(C_YELLOW, "  Нужно число, Enter или q."))
            continue
        if 1 <= idx <= len(names):
            return names[idx - 1]
        print(_c(C_YELLOW, f"  Нет режима с номером {idx}, попробуй ещё раз."))


def summarize(report) -> None:
    """Финальная сводка: таблица результатов + итоги."""
    print()
    print(_c(C_BOLD, "  ───── СВОДКА ─────"))

    rows = list(report.results)
    name_w = max([len(r.name) for r in rows] + [len("Файл")])
    res_w = max([len((r.detail or "—")[:40]) for r in rows] + [len("Результат")])
    size_w = 30
    sep_len = 6 + 2 + name_w + 2 + res_w + 2 + size_w + 2 + 6

    header = f"  {'Статус':<6}  {'Файл':<{name_w}}  {'Результат':<{res_w}}  {'Размер':^30}  {'Время':>6}"
    print(header)
    print("  " + "─" * sep_len)

    for r in rows:
        outcome = r.detail or "—"
        if len(outcome) > 40:
            outcome = outcome[:39] + "…"
        if r.status == "ok":
            status = _c(C_GREEN, "OK".ljust(6))
            size = f"{r.size_src / 1024:6.1f} KB → {r.size_svg / 1024:6.1f} KB ({r.ratio:.2f}x)"
            t = f"{r.time_s:5.1f}s"
        elif r.status == "skip":
            status = _c(C_YELLOW, "SKIP".ljust(6))
            size = " " * size_w
            t = " " * 6
        else:
            status = _c(C_RED, "ERR".ljust(6))
            size = " " * size_w
            t = " " * 6
        print(f"  {status}  {r.name:<{name_w}}  {outcome:<{res_w}}  {size}  {t:>6}")

    print("  " + "─" * sep_len)
    if report.ok:
        src_kb = report.total_size_src / 1024
        svg_kb = report.total_size_svg / 1024
        pct = report.total_size_svg / report.total_size_src if report.total_size_src else 0.0
        print(f"  Размер: {src_kb:6.1f} KB → {svg_kb:6.1f} KB ({pct:.2f}x)")
    print(
        f"  Итог: {_c(C_GREEN, str(report.ok))} готово, "
        f"{_c(C_YELLOW, str(report.skipped))} пропущено, "
        f"{_c(C_RED, str(report.errors))} ошибок, "
        f"{report.elapsed:.2f}с"
    )
    print()


def ensure_folders() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="Pix2Vec",
        description="Конвертер растровых изображений (PNG/JPG/WEBP/BMP/GIF/TIFF/ICO) в векторный SVG.",
    )
    p.add_argument("folder", nargs="?", default=None, help="входная папка с картинками")
    p.add_argument(
        "-p", "--profile",
        default=None,
        choices=list(PROFILES),
        help=f"профиль трассировки (по умолчанию: {DEFAULT_PROFILE})",
    )
    p.add_argument("-o", "--output", default=None, help="выходная папка для SVG")
    p.add_argument("--overwrite", action="store_true", help="перезаписывать существующие SVG (иначе они пропускаются)")
    p.add_argument("--no-menu", action="store_true", help="не показывать меню, взять профиль из аргумента")
    p.add_argument("--no-open", action="store_true", help="не открывать папку результата в Проводнике")
    p.add_argument("--version", action="version", version=f"Pix2Vec {__version__}")
    return p.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_folders()
    _force_utf8_stdio()

    source = Path(args.folder) if args.folder else INPUT_DIR
    output = Path(args.output) if args.output else OUTPUT_DIR

    if not source.exists():
        print(_c(C_RED, f"  Папка не найдена: {source}"))
        return 1
    if not source.is_dir():
        print(_c(C_RED, f"  Это не папка: {source}"))
        return 1

    profile = args.profile
    if profile is None and not args.no_menu:
        banner()
        profile = show_menu()
        if profile is None:
            print(_c(C_YELLOW, "  Отмена."))
            return 0
    else:
        banner()

    print(_c(C_BOLD, f"  Режим: {get_profile(profile)['label']}"))
    print()
    print(_c(C_CYAN, f"  Вход : {source}"))
    print(_c(C_CYAN, f"  Выход: {output}"))
    if source.resolve() == output.resolve():
        print(_c(C_YELLOW, "  ⚠ Выходная папка совпадает со входной — SVG появятся рядом с исходниками."))
    print()

    def on_progress(done, total, name):
        progress_bar(done, total, name)

    report = convert_directory(
        source, output, profile_name=profile, overwrite=args.overwrite,
        on_progress=on_progress,
    )
    print()

    if not report.results:
        print(_c(C_YELLOW, f"  В папке не найдено изображений: {source}"))
        print(_c(C_YELLOW, "  Поддержка: PNG, JPG, JPEG, BMP, GIF, TIFF, WEBP, ICO и др."))
        print(_c(C_YELLOW, f"  Положи файлы в {source} и запусти снова."))
        return 0

    summarize(report)

    if _stdin_isatty() and not args.no_open:
        try:
            os.startfile(str(output))
        except OSError:
            pass

    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
