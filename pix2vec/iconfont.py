"""Сборка иконного TTF-шрифта из растровых иконок.

Пример:
    python -m pix2vec.iconfont
    python -m pix2vec.iconfont -o output/Pix2Vec.ttf --profile logo
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.transform import Transform
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import SVGPath

from .config import ROOT_DIR, INPUT_DIR, get_profile
from .tracer import _PATH_TAG_RE, render_svg

DEFAULT_OUT = ROOT_DIR / "output" / "Pix2Vec.ttf"
UNITS_PER_EM = 1000
TARGET_SIZE = 800  # высота слота глифа в единицах em
PNG_BY_SUFFIX = ".png"


def _parse_transform(raw: str | None) -> Transform:
    """'translate(265,73)' -> Transform; 'matrix(a b c d e f)' — тоже."""
    t = Transform()
    if not raw:
        return t
    m = re.search(r"translate\(([-0-9.eE\s,]+)\)", raw)
    if m:
        x, y = [float(v) for v in re.findall(r"-?\d*\.?\d+", m.group(1))][:2]
        return t.translate(x, y)
    m = re.search(r"scale\(([-0-9.eE\s,]+)\)", raw)
    if m:
        vals = [float(v) for v in re.findall(r"-?\d*\.?\d+", m.group(1))]
        if len(vals) == 1:
            vals = vals * 2
        return t.scale(vals[0], vals[1])
    m = re.search(r"matrix\(([-0-9.eE\s,]+)\)", raw)
    if m:
        vals = [float(v) for v in re.findall(r"-?\d*\.?\d+", m.group(1))]
        if len(vals) == 6:
            return Transform(*vals)
    return t


_TRANSFORM_ATTR_RE = re.compile(r'\stransform="[^"]*"')


def _iter_paths(svg: str):
    """(очищенный тег <path>, transform пути) для каждого пути SVG."""
    for m in _PATH_TAG_RE.finditer(svg):
        tag = m.group(0)
        tm = re.search(r'\stransform="([^"]*)"', tag)
        t = _parse_transform(tm.group(1) if tm else None)
        cleaned = _TRANSFORM_ATTR_RE.sub("", tag)
        yield cleaned, t


class _BBoxPen:
    """Собирает все точки пути для расчёта bbox."""

    def __init__(self) -> None:
        self.xs: list[float] = []
        self.ys: list[float] = []

    def _add(self, pt: tuple[float, float] | None) -> None:
        if pt is not None and len(pt) == 2:
            self.xs.append(pt[0])
            self.ys.append(pt[1])

    def moveTo(self, pt) -> None: self._add(pt)
    def lineTo(self, pt) -> None: self._add(pt)
    def curveTo(self, *pts) -> None:
        for p in pts:
            self._add(p)
    def qCurveTo(self, *pts) -> None:
        for p in pts:
            self._add(p)
    def closePath(self) -> None: pass
    def endPath(self) -> None: pass
    def addComponent(self, glyphName, transformation, *args, **kwargs) -> None: pass


def _svg_bbox(svg: str) -> tuple[float, float, float, float] | None:
    """Сквозной bbox всех путей SVG в координатах канваса."""
    pen = _BBoxPen()
    for tag, t in _iter_paths(svg):
        SVGPath.fromstring(tag, transform=t).draw(pen)
    if not pen.xs:
        return None
    return min(pen.xs), min(pen.ys), max(pen.xs), max(pen.ys)


def _svg_to_glyph(svg: str) -> object:
    """Все пути SVG -> один TrueType-глиф, нормализованный в слот [0..TARGET_SIZE]."""
    bbox = _svg_bbox(svg)
    if not bbox:
        raise ValueError("в SVG нет путей")
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        raise ValueError("пустой bbox")

    scale = TARGET_SIZE / max(w, h)
    # x: центрируем по ширине em; y: низ глифа сажается на baseline (0),
    # верх поднимается до TARGET_SIZE.
    tx = (UNITS_PER_EM - scale * w) / 2 - scale * x0
    ty = scale * y1
    canvas_to_glyph = Transform(scale, 0, 0, -scale, tx, ty)

    tt_pen = TTGlyphPen(None)
    pen = Cu2QuPen(tt_pen, max_err=0.1)
    for tag, t in _iter_paths(svg):
        combined = canvas_to_glyph.transform(t)
        SVGPath.fromstring(tag, transform=combined).draw(pen)
    return tt_pen.glyph()


def build_icon_font(
    images: list[tuple[str, bytes]],
    out_path: Path,
    profile: str = "logo",
) -> list[str]:
    """Собрать TTF. images: (имя_глифа, png-байты). Глифы добавляются по списку."""
    prof = get_profile(profile)
    glyphs: dict[str, object] = {}
    for name, data in images:
        try:
            svg = render_svg(data, prof)
        except Exception:
            svg = render_svg(data, get_profile("color"))
        glyphs[name] = _svg_to_glyph(svg)

    glyph_order = [".notdef"] + [n for n, _ in images]
    cmap = {ord("A") + i: name for i, (name, _) in enumerate(images)}

    empty = TTGlyphPen(None)
    glyphs = {".notdef": empty.glyph(), **glyphs}

    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(
        {name: (UNITS_PER_EM, 0) for name in glyph_order}
    )
    fb.setupHorizontalHeader(ascent=TARGET_SIZE, descent=0)
    fb.setupNameTable(
        {
            "familyName": "Pix2Vec Icons",
            "styleName": "Regular",
            "uniqueFontIdentifier": "Pix2Vec Icons Regular",
            "fullName": "Pix2Vec Icons",
            "version": "Version 1.0",
            "psName": "Pix2VecIcons-Regular",
        }
    )
    fb.setupOS2(
        sTypoAscender=TARGET_SIZE,
        sTypoDescender=0,
        usWinAscent=TARGET_SIZE,
        usWinDescent=0,
        sCapHeight=round(TARGET_SIZE * 0.72),
        sxHeight=round(TARGET_SIZE * 0.52),
        usWeightClass=400,
        usWidthClass=5,
        fsType=0,
    )
    fb.setupPost()
    fb.setupMaxp()
    # head хранит дату как SDT (секунды от 01.01.1904)
    now = int(time.time()) + 0x7C259DC0
    fb.setupHead(created=now, modified=now)
    fb.save(out_path)
    return [f"{name} -> {chr(ord('A') + i)} (U+{ord('A') + i:04X})" for i, (name, _) in enumerate(images)]


def _list_pngs() -> list[tuple[str, Path]]:
    return [(p.stem, p) for p in sorted(INPUT_DIR.glob("*" + PNG_BY_SUFFIX))]


def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="Pix2Vec.iconfont", description="Иконки из input/ -> TTF.")
    p.add_argument("-o", "--output", default=str(DEFAULT_OUT), help="куда сохранить TTF")
    p.add_argument("--profile", default="color", choices=["color", "logo"], help="профиль трассировки")
    p.add_argument("--first", default=None, help="какой файл поставить первым глифом (без расширения)")
    return _run(p.parse_args(argv))


def _run(args) -> int:
    items = _list_pngs()
    first = Path(args.first).stem if args.first else "kitty_client"
    items = [it for it in items if it[0] != first]
    items = [(first, INPUT_DIR / (first + ".png"))] + items
    images = [(name, f.read_bytes()) for name, f in items]

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    mapping = build_icon_font(
        images,
        out,
        profile=args.profile,
    )
    print(f"Файл сохранён: {out} ({out.stat().st_size} байт)")
    for line in mapping:
        print(" ", line)
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()