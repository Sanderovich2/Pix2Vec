"""Изолированный воркер: трассировка одного файла.

Запуск: python -m pix2vec.worker <src> <out> <profile-name>
Коды выхода: 0 = успех, 1 = ошибка (детали в stderr), 2 = неверные аргументы.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) < 3:
        print("usage: python -m pix2vec.worker <src> <out> <profile>", file=sys.stderr)
        return 2

    src, out, profile_name = args[0], args[1], args[2]

    from .config import get_profile
    from .tracer import render_svg

    try:
        data = Path(src).read_bytes()
        svg = render_svg(data, get_profile(profile_name))
        Path(out).write_text(svg, encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
