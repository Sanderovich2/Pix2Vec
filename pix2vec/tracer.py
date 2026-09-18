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

    background = profile.get("background")
    if background:
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

    return _normalize_svg(body, w, h)


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
