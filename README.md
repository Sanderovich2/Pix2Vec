# Pix2Vec

[![CI](https://github.com/Sanderovich2/Pix2Vec/actions/workflows/ci.yml/badge.svg)](https://github.com/Sanderovich2/Pix2Vec/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-2ea44f.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-informational.svg)

**Pix2Vec** is a command-line converter that turns raster images (PNG, JPEG, WEBP, BMP, GIF, TIFF, ICO and more) into vector SVG, with batch processing and quality profiles. From pixels to vectors in one command. Runs fully offline.

Русская версия: [README.ru.md](README.ru.md)

Powered by [visioncortex VTracer](https://github.com/visioncortex/vtracer) (through the `vtracer` Python binding) and Pillow.

## Features

- **Batch conversion** of a whole folder, including subfolders
- **6 tracing profiles** for different jobs, from photos to black-and-white logos
- **Isolated worker process** per file: if the engine crashes on one image, the batch survives
- Progress bar and a result table (size before/after, elapsed time)
- Transparency is flattened onto white; every SVG gets a proper `viewBox` and integer dimensions
- Colored output that disables itself in pipes and legacy consoles
- Windows-first (one-click `run.bat`), also works on Linux and macOS

## Profiles

| Profile | Purpose |
|---|---|
| `color` | Color tracing: balance between quality and size (default) |
| `photo` | Photographs: smoothing and large fills, lighter SVG |
| `logo` | Black-and-white logo: dark artwork on a light background |
| `logo_inv` | Black-and-white logo: light artwork on a dark background |
| `detailed` | Maximum detail (larger SVG) |
| `sketch` | Sketch: grayscale preprocessing, large smooth areas |

## Quick start (Windows)

1. Install [Python 3.10+](https://www.python.org/downloads/) and tick "Add python.exe to PATH".
2. Double-click `run.bat`. It locates Python, creates a virtual environment, installs dependencies and starts the converter.
3. Drop images into `input/` (or drag a folder onto `run.bat`), pick a mode. The SVG files land in `output/` and the folder opens in Explorer.

## CLI

```bash
python -m pix2vec.main [FOLDER] [-p PROFILE] [-o OUTPUT] [--overwrite] [--no-menu] [--no-open]
```

| Argument | Description |
|---|---|
| `FOLDER` | input folder (defaults to `input/`) |
| `-p, --profile` | tracing profile (defaults to `color`) |
| `-o, --output` | output folder (defaults to `output/`) |
| `--overwrite` | overwrite existing SVGs (otherwise they are skipped) |
| `--no-menu` | skip the interactive menu |
| `--no-open` | do not open the output folder in the file manager |
| `--version` | print the version |

Examples:

```bash
python -m pix2vec.main                          # input/ -> output/, interactive menu
python -m pix2vec.main C:\photos -p photo       # custom folder, photo profile
python -m pix2vec.main --overwrite --no-open    # overwrite without prompts
```

## Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pix2vec.main
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## Project layout

```
pix2vec/
  config.py     # paths, supported formats, tracing profiles
  tracer.py     # pixel preprocessing + vtracer engine call
  converter.py  # batch processing, worker processes, logs
  worker.py     # isolated single-file worker
  main.py       # CLI, menu, progress, summary
tests/          # unittest suite
docs/           # repository maintenance notes
input/          # source images (created automatically)
output/         # generated SVG files
logs/           # run logs
run.bat         # one-click launcher for Windows
```

## Known quirks

- In `vtracer` 0.6.15, calling the engine with **keyword arguments crashes the Python process** (segfault). Pix2Vec calls it with positional arguments only. If you edit profiles in `pix2vec/config.py`, keep the order of the `engine` tuple documented in `ENGINE_DOC` in the same file.
- Animated GIF/TIFF files are converted from their first frame only.
- Two files in one folder with the same name but different extensions produce a single SVG (the second one is skipped unless `--overwrite` is used).

## License

MIT. See [LICENSE](LICENSE).
