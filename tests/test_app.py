"""Тесты Pix2Vec: профили, предобработка, трассировка, батч-конвертация.

Запуск из корня проекта:
    .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import sys
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pix2vec.config import DEFAULT_PROFILE, PROFILES, get_profile, to_engine_args  # noqa: E402
from pix2vec.converter import convert_directory, find_images  # noqa: E402
from pix2vec.tracer import ConversionError, prepare_image, render_svg, svg_size  # noqa: E402


def _make_png_bytes(w: int = 60, h: int = 40, two_colors: bool = True) -> bytes:
    """Маленькая RGB-плашка как PNG-байты."""
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([5, 5, w // 2, h - 5], fill=(200, 30, 30))
    if two_colors:
        d.rectangle([w // 2 + 2, 5, w - 5, h - 5], fill=(30, 60, 200))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class FindImagesTests(unittest.TestCase):
    def test_finds_supported_recursively(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.png").write_bytes(b"x")
            (root / "b.jpg").write_bytes(b"x")
            (root / "note.txt").write_bytes(b"x")
            sub = root / "sub"
            sub.mkdir()
            (sub / "c.webp").write_bytes(b"x")
            found = find_images(root)
            names = [p.name for p, _ in found]
            self.assertEqual(sorted(names), ["a.png", "b.jpg", "c.webp"])

    def test_missing_dir_empty(self):
        self.assertEqual(find_images(Path("Z:/definitely/not/here")), [])


class ProfileTests(unittest.TestCase):
    def test_profiles_complete(self):
        for key, prof in PROFILES.items():
            with self.subTest(profile=key):
                self.assertTrue(prof.get("label"))
                self.assertTrue(prof.get("description"))
                self.assertIn("engine", prof)

    def test_to_engine_args_types(self):
        for key, prof in PROFILES.items():
            with self.subTest(profile=key):
                args = to_engine_args(prof)
                self.assertEqual(len(args), 11)
                colormode, hier, mode, fs, cp, ld, ct, lt, mi, st, pp = args
                self.assertIsInstance(colormode, str)
                self.assertIn(colormode, ("color", "binary"))
                self.assertIn(hier, ("stacked", "cutout"))
                self.assertIn(mode, ("spline", "polygon", "none"))
                for v in (fs, cp, ld, ct, mi, st, pp):
                    self.assertIsInstance(v, int)
                self.assertIsInstance(lt, float)
                self.assertGreaterEqual(lt, 3.5)
                self.assertLessEqual(lt, 10.0)

    def test_get_profile_default_and_fallback(self):
        self.assertEqual(get_profile(None), PROFILES[DEFAULT_PROFILE])
        self.assertEqual(get_profile("несуществующий"), PROFILES[DEFAULT_PROFILE])


class PrepareImageTests(unittest.TestCase):
    def test_alpha_composited_on_white(self):
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 0))  # полностью прозрачный
        out = prepare_image(img, get_profile("color"))
        self.assertIn(out.mode, ("RGB", "RGBA"))  # цветной профиль допускает RGBA
        px = out.getpixel((5, 5))
        self.assertGreater(min(px[:3]), 240)  # стал белым
        if out.mode == "RGBA":
            self.assertEqual(px[3], 255)  # и непрозрачным

    def test_threshold_binarizes(self):
        img = Image.new("RGB", (10, 10), (10, 10, 10))
        d = ImageDraw.Draw(img)
        d.rectangle([5, 0, 9, 9], fill=(240, 240, 240))
        out = prepare_image(img, get_profile("logo"))
        self.assertEqual(out.getpixel((2, 5)), (0, 0, 0))
        self.assertEqual(out.getpixel((7, 5)), (255, 255, 255))

    def test_invert(self):
        img = Image.new("RGB", (10, 10), (240, 240, 240))
        out = prepare_image(img, get_profile("logo_inv"))
        self.assertEqual(out.getpixel((5, 5)), (0, 0, 0))

    def test_downscale_by_max_dim(self):
        img = Image.new("RGB", (1000, 500), (120, 120, 120))
        prof = dict(get_profile("color"), max_dim=200)
        out = prepare_image(img, prof)
        self.assertEqual(max(out.size), 200)

    def test_unknown_preprocess_step_raises(self):
        img = Image.new("RGB", (10, 10), (0, 0, 0))
        prof = dict(get_profile("color"), preprocess=("magick",))
        with self.assertRaises(ConversionError):
            prepare_image(img, prof)


class RenderSvgTests(unittest.TestCase):
    def test_render_basic(self):
        data = _make_png_bytes()
        svg = render_svg(data, get_profile("color"))
        self.assertTrue(svg.lstrip().startswith(("<?xml", "<svg")))
        self.assertIn('viewBox="0 0 60 40"', svg)
        self.assertIn('width="60"', svg)
        self.assertIn('height="40"', svg)
        self.assertEqual(svg_size(svg), (60, 40))

    def test_svg_size_fractional_and_garbage(self):
        # round() в Python округляет 150.5 до чётного (150)
        self.assertEqual(svg_size('<svg width="300.0" height="150.5"></svg>'), (300, 150))
        self.assertEqual(svg_size('<svg width="300.0" height="150.6"></svg>'), (300, 151))
        self.assertEqual(svg_size("не svg вообще"), (0, 0))
        self.assertEqual(svg_size('<svg width="auto" height="auto"></svg>'), (0, 0))

    def test_render_bad_data_raises(self):
        with self.assertRaises(ConversionError):
            render_svg("это не изображение".encode("utf-8"), get_profile("color"))


class ConvertDirectoryTests(unittest.TestCase):
    def _make_src(self, src: Path) -> None:
        src.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (80, 60), (255, 255, 255)).save(src / "test_pic.png")

    def test_e2e_ok_then_skip_then_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            dst = Path(td) / "dst"
            self._make_src(src)

            report = convert_directory(src, dst, profile_name="color", overwrite=False)
            self.assertEqual(report.ok, 1)
            self.assertEqual(report.errors, 0)
            svg_path = dst / "test_pic.svg"
            self.assertTrue(svg_path.exists())
            text = svg_path.read_text(encoding="utf-8")
            self.assertTrue(text.lstrip().startswith(("<?xml", "<svg")))

            # повторный запуск без overwrite -> skip, новых файлов нет
            time.sleep(0.02)  # чтобы mtime успел отличаться
            report2 = convert_directory(src, dst, profile_name="color", overwrite=False)
            self.assertEqual(report2.skipped, 1)
            self.assertEqual([p.name for p in dst.iterdir()], ["test_pic.svg"])

            # с overwrite -> перезапись того же файла, список не растёт
            report3 = convert_directory(src, dst, profile_name="color", overwrite=True)
            self.assertEqual(report3.ok, 1)
            self.assertEqual([p.name for p in dst.iterdir()], ["test_pic.svg"])


if __name__ == "__main__":
    unittest.main()
