"""Конфигурация приложения: пути, профили обработки, реестр форматов."""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT_DIR / "input"
OUTPUT_DIR = ROOT_DIR / "output"
LOG_DIR = ROOT_DIR / "logs"

SUPPORTED_FORMATS: dict[str, str] = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".bmp": "BMP",
    ".gif": "GIF",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".webp": "WEBP",
    ".ico": "ICO",
    ".ppm": "PPM",
    ".pgm": "PGM",
}

SVG_EXT = ".svg"
DEFAULT_MAX_DIM = 4096

PROFILES: dict[str, dict] = {
    "color": {
        "label": "Цветная трассировка",
        "description": "Баланс качества и размера для обычных картинок",
        "engine": ("color", "stacked", "spline", 4, 7, 16, 60, 4.0, 10, 45, 2),
        "background": "white",
        "threshold": None,
        "invert": False,
        "max_dim": DEFAULT_MAX_DIM,
        "preprocess": None,
    },
    "photo": {
        "label": "Фотография (лёгкий SVG)",
        "description": "Уменьшение + сглаживание, крупные заливки, файл поменьше",
        "engine": ("color", "stacked", "spline", 10, 5, 48, 75, 6.0, 3, 60, 1),
        "background": "white",
        "threshold": None,
        "invert": False,
        "max_dim": 1600,
        "preprocess": ("smooth",),
    },
    "logo": {
        "label": "Ч/Б логотип",
        "description": "Порог 160: тёмный рисунок превращается в ч/б вектор",
        "engine": ("binary", "stacked", "spline", 8, 3, 16, 60, 4.0, 10, 45, 2),
        "background": "white",
        "threshold": 160,
        "invert": False,
        "max_dim": DEFAULT_MAX_DIM,
        "preprocess": None,
    },
    "logo_inv": {
        "label": "Ч/Б логотип (инверсия)",
        "description": "Порог 96: светлый логотип на тёмном фоне",
        "engine": ("binary", "stacked", "spline", 8, 3, 16, 60, 4.0, 10, 45, 2),
        "background": "white",
        "threshold": 96,
        "invert": True,
        "max_dim": DEFAULT_MAX_DIM,
        "preprocess": None,
    },
    "detailed": {
        "label": "Максимальная детализация",
        "description": "Максимум контуров и цветов, большой SVG",
        "engine": ("color", "stacked", "spline", 2, 8, 8, 45, 3.5, 10, 30, 3),
        "background": "white",
        "threshold": None,
        "invert": False,
        "max_dim": 8192,
        "preprocess": None,
    },
    "sketch": {
        "label": "Эскиз (гладкие заливки)",
        "description": "Ч/б предобработка, крупные гладкие области",
        "engine": ("color", "cutout", "spline", 6, 4, 60, 90, 8.0, 1, 80, 1),
        "background": "white",
        "threshold": None,
        "invert": False,
        "max_dim": 1024,
        "preprocess": ("grayscale", "autocontrast"),
    },
}

DEFAULT_PROFILE = "color"

ENGINE_DOC = """Порядок engine-аргументов vtracer (передаются позиционно после
img_bytes/img_format): colormode ['color'|'binary'], hierarchical
['stacked'|'cutout'], mode ['spline'|'polygon'|'none'], filter_speckle,
color_precision, layer_difference, corner_threshold, length_threshold
[3.5..10], max_iterations, splice_threshold, path_precision.
Keyword-аргументы биндинга vtracer 0.6.15 роняют процесс, поэтому
используются только позиционные.
"""


def get_profile(name: str | None) -> dict:
    """Вернуть профиль по имени или профиль по умолчанию."""
    return PROFILES.get(name or DEFAULT_PROFILE) or PROFILES[DEFAULT_PROFILE]


def to_engine_args(profile: dict) -> tuple:
    """11 позиционных аргументов движка для распаковки в vtracer."""
    engine = tuple(profile["engine"])
    if len(engine) != 11:
        raise ValueError(
            f"engine должен содержать 11 позиционных аргументов, а не {len(engine)}"
        )
    return engine
