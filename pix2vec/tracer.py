"""Конвертация растра в SVG: подготовка пикселей (Pillow) + трассировка (vtracer)."""

from __future__ import annotations

import io
import re

from PIL import Image, ImageFilter, ImageOps

import vtracer

from .config import to_engine_args


class ConversionError(Exception):
    """Ошибка конвертации одного файла."""


_PREPROCESS_STEPS = {
    "smooth": lambda im: im.filter(ImageFilter.SMOOTH),
    "grayscale": lambda im: im.convert("L"),
    "autocontrast": lambda im: ImageOps.autocontrast(im),
}


def prepare_image(image: Image.Image, profile: dict) -> Image.Image:
    """Подготовить изображение к трассировке согласно профилю."""
    img = image.convert("RGBA")

    # Прозрачность теряется при пороговой ч/б трассировке и предобработке
    # в градации серого, поэтому там подкладываем фон. Цветным профилям
    # прозрачность передаём как есть: vtracer не рисует прозрачные области,
    # а белый композит превращался в «белый фон» в выходном SVG.
    threshold = profile.get("threshold")
    preprocess = profile.get("preprocess") or ()
    drops_alpha = threshold is not None or "grayscale" in preprocess
    background = profile.get("background")
    if drops_alpha and background:
        bg = Image.new("RGBA", img.size, background)
        img = Image.alpha_composite(bg, img)

    max_dim = int(profile.get("max_dim", 4096))
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize(
            (max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS
        )

    for step in profile.get("preprocess") or ():
        fn = _PREPROCESS_STEPS.get(step)
        if fn is None:
            raise ConversionError(f"неизвестный шаг предобработки: {step}")
        img = fn(img)

    threshold = profile.get("threshold")
    if threshold is not None:
        gray = img.convert("L")
        bw = gray.point(lambda p: 255 if p > threshold else 0, mode="L")
        if profile.get("invert"):
            bw = ImageOps.invert(bw)
        img = bw.convert("RGB")

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    return img


_SVG_TAG_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
_WIDTH_ATTR_RE = re.compile(r'\swidth="[^"]*"')
_HEIGHT_ATTR_RE = re.compile(r'\sheight="[^"]*"')
_VIEWBOX_ATTR_RE = re.compile(r"\sviewBox=\"[^\"]*\"", re.IGNORECASE)
_DIM_VALUE_RE = re.compile(r"\d*\.?\d+")


def _parse_dim(raw: str) -> int | None:
    """'300.0' -> 300, '300px' -> 300, 'auto' -> None."""
    m = _DIM_VALUE_RE.search(raw or "")
    if not m:
        return None
    try:
        return int(round(float(m.group(0))))
    except ValueError:
        return None


def _ensure_attr(open_tag: str, pattern: re.Pattern, attr: str, value: str) -> str:
    """Заменить атрибут в открывающем теге <svg> или добавить его."""
    if pattern.search(open_tag):
        return pattern.sub(lambda _m: f' {attr}="{value}"', open_tag, count=1)
    return f'{open_tag} {attr}="{value}"'


def _normalize_svg(svg: str, w: int, h: int) -> str:
    """Привести тег <svg> к целым width/height и гарантировать viewBox."""
    m = _SVG_TAG_RE.search(svg)
    if not m:
        return svg

    open_tag = m.group(0)[:-1].rstrip()
    open_tag = _ensure_attr(open_tag, _WIDTH_ATTR_RE, "width", str(w))
    open_tag = _ensure_attr(open_tag, _HEIGHT_ATTR_RE, "height", str(h))
    open_tag = _ensure_attr(open_tag, _VIEWBOX_ATTR_RE, "viewBox", f"0 0 {w} {h}")

    return f"{svg[:m.start()]}{open_tag}>{svg[m.end():]}"


_PATH_TAG_RE = re.compile(r"<path\b[^>]*/>", re.IGNORECASE)
_D_ATTR_RE = re.compile(r'\sd="([^"]*)"')
_FILL_HEX_RE = re.compile(r'\sfill="#([0-9A-Fa-f]{6})"')
_TOKEN_RE = re.compile(r"[a-zA-Z]|-?\d*\.?\d+(?:[eE][+-]?\d+)?")


def _path_bbox(d: str) -> tuple[tuple[float, float, float, float], int] | None:
    """Минимальный bbox замкнутых контуров пути и число субпутей (Z).

    Возвращает ((x0, y0, x1, y1), n_subpaths) или None, если в d нет точек.
    """
    tokens: list[tuple[str, object]] = []
    for m in _TOKEN_RE.finditer(d):
        s = m.group(0)
        tokens.append(("c", s) if s[0].isalpha() else ("n", float(s)))

    if not tokens:
        return None

    xs: list[float] = []
    ys: list[float] = []
    cur_x = cur_y = 0.0
    n_sub = 0
    i = 0
    n = len(tokens)

    def take_num() -> float | None:
        nonlocal i
        if i < n and tokens[i][0] == "n":
            val = tokens[i][1]
            i += 1
            return val  # type: ignore[return-value]
        return None

    def add(x: float, y: float) -> None:
        xs.append(x)
        ys.append(y)

    while i < n:
        kind, raw = tokens[i]
        if kind != "c":
            i += 1
            continue
        cmd = str(raw)
        i += 1
        if cmd in ("M", "m"):
            first = True
            while i < n and tokens[i][0] == "n":
                raw_x, raw_y = take_num() or 0.0, take_num() or 0.0
                if cmd == "m":
                    x, y = cur_x + raw_x, cur_y + raw_y
                else:
                    x, y = raw_x, raw_y
                if first:
                    first = False
                cur_x, cur_y = x, y
                add(x, y)
        elif cmd in ("L", "l", "T", "t"):
            x, y = take_num() or 0.0, take_num() or 0.0
            if cmd in ("l", "t"):
                x, y = cur_x + x, cur_y + y
            cur_x, cur_y = x, y
            add(x, y)
        elif cmd in ("H", "h", "V", "v"):
            v = take_num() or 0.0
            if cmd in ("h", "v"):
                v = (cur_x if cmd == "h" else cur_y) + v
            if cmd in ("H", "h"):
                cur_x = v
            else:
                cur_y = v
            add(cur_x, cur_y)
        elif cmd in ("C", "c"):
            pts = [(take_num() or 0.0) for _ in range(6)]
            c1x, c1y, c2x, c2y, x, y = pts
            if cmd == "c":
                c1x, c1y = cur_x + c1x, cur_y + c1y
                c2x, c2y = cur_x + c2x, cur_y + c2y
                x, y = cur_x + x, cur_y + y
            add(c1x, c1y)
            add(c2x, c2y)
            cur_x, cur_y = x, y
            add(x, y)
        elif cmd in ("S", "s"):
            pts = [(take_num() or 0.0) for _ in range(4)]
            c2x, c2y, x, y = pts
            if cmd == "s":
                c2x, c2y = cur_x + c2x, cur_y + c2y
                x, y = cur_x + x, cur_y + y
            add(c2x, c2y)
            cur_x, cur_y = x, y
            add(x, y)
        elif cmd in ("Q", "q"):
            c1x, c1y, x, y = [(take_num() or 0.0) for _ in range(4)]
            if cmd == "q":
                c1x, c1y = cur_x + c1x, cur_y + c1y
                x, y = cur_x + x, cur_y + y
            add(c1x, c1y)
            cur_x, cur_y = x, y
            add(x, y)
        elif cmd in ("A", "a"):
            # rx ry x-axis-rot large-arc sweep x y
            take_num()
            take_num()
            take_num()
            take_num()
            take_num()
            x, y = take_num() or 0.0, take_num() or 0.0
            if cmd == "a":
                x, y = cur_x + x, cur_y + y
            cur_x, cur_y = x, y
            add(x, y)
        elif cmd == "Z":
            n_sub += 1

    if n_sub == 0 and tokens:
        n_sub = 1  # незакрытый контур — всё равно считаем единым объектом

    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys)), n_sub


def _is_near_white(fill_hex: str, floor: int = 240) -> bool:
    r, g, b = (int(fill_hex[i : i + 2], 16) for i in (0, 2, 4))
    return r >= floor and g >= floor and b >= floor


def _strip_white_background_paths(svg: str, w: int, h: int) -> str:
    """Убрать сплошные белые заливки во весь холст (фон-подложка VTracer)."""

    def keep(m: re.Match) -> str:
        tag = m.group(0)
        fm = _FILL_HEX_RE.search(tag)
        if not fm or not _is_near_white(fm.group(1)):
            return tag
        dm = _D_ATTR_RE.search(tag)
        if not dm:
            return tag
        parsed = _path_bbox(dm.group(1))
        if not parsed:
            return tag
        (x0, y0, x1, y1), n_sub = parsed
        full_canvas = x0 <= 1 and y0 <= 1 and x1 >= w - 1 and y1 >= h - 1
        if full_canvas and n_sub == 1:
            return ""
        return tag

    return _PATH_TAG_RE.sub(keep, svg)


def render_svg(data: bytes, profile: dict) -> str:
    """Полный пайплайн: байты изображения -> SVG-строка (без temp-файлов)."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ConversionError(f"не удалось прочитать изображение: {exc}") from exc

    img = prepare_image(img, profile)
    w, h = img.size

    buf = io.BytesIO()
    try:
        img.save(buf, "PNG")
    except Exception as exc:
        raise ConversionError(f"не удалось закодировать PNG: {exc}") from exc

    try:
        body = vtracer.convert_raw_image_to_svg(
            buf.getvalue(), "png", *to_engine_args(profile)
        )
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"ошибка трассировки: {exc}") from exc

    if not body or "<svg" not in body:
        raise ConversionError("движок вернул пустой результат")

    svg = _normalize_svg(body, w, h)
    return _strip_white_background_paths(svg, w, h)


def svg_size(svg: str) -> tuple[int, int]:
    """Достать ширину/высоту из тега <svg> (дробные значения допустимы)."""
    m = _SVG_TAG_RE.search(svg)
    if not m:
        return 0, 0
    tag = m.group(0)
    mw = re.search(r'\swidth="([^"]*)"', tag)
    mh = re.search(r'\sheight="([^"]*)"', tag)
    if not mw or not mh:
        return 0, 0
    w, h = _parse_dim(mw.group(1)), _parse_dim(mh.group(1))
    if w is None or h is None:
        return 0, 0
    return w, h
