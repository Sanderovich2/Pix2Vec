# Pix2Vec

[![CI](https://github.com/Sanderovich2/Pix2Vec/actions/workflows/ci.yml/badge.svg)](https://github.com/Sanderovich2/Pix2Vec/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-2ea44f.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-informational.svg)

English version: [README.md](README.md)

**Pix2Vec** — консольный конвертер растровых изображений (PNG, JPEG, WEBP, BMP, GIF, TIFF, ICO и др.) в векторный SVG с пакетной обработкой и профилями качества. Из пикселей в векторы одной командой. Работает офлайн.

Основан на движке [visioncortex VTracer](https://github.com/visioncortex/vtracer) (через Python-биндинг `vtracer`) и Pillow.

## Возможности

- **Пакетная конвертация** папки с изображениями, включая подпапки
- **6 профилей трассировки** под разные задачи — от фото до ч/б логотипов
- **Изолированный воркер-процесс** на каждый файл: падение движка на одной картинке не рушит пакет
- Прогресс-бар и итоговая таблица (размер до/после, время)
- Прозрачность сводится на белый фон, корректный `viewBox` и целые размеры в каждом SVG
- Цветной вывод, который сам отключается в пайпах и старых консолях
- Windows-first (готовый `run.bat`), работает и на Linux/macOS

## Профили

| Профиль | Назначение |
|---|---|
| `color` | Цветная трассировка — баланс качества и размера (по умолчанию) |
| `photo` | Фотографии — сглаживание и крупные заливки, лёгкий SVG |
| `logo` | Ч/Б логотип — тёмный рисунок на светлом фоне |
| `logo_inv` | Ч/Б логотип — светлый рисунок на тёмном фоне |
| `detailed` | Максимальная детализация (большой SVG) |
| `sketch` | Эскиз — ч/б предобработка, гладкие крупные области |

## Быстрый старт (Windows)

1. Установи [Python 3.10+](https://www.python.org/downloads/) с галочкой «Add python.exe to PATH».
2. Дважды щёлкни `run.bat` — он сам найдёт Python, создаст venv, поставит зависимости и запустит конвертер.
3. Кинь картинки в папку `input/` (или перетащи папку на `run.bat`), выбери режим — готово, SVG появятся в `output/` и откроются в Проводнике.

## CLI

```bash
python -m pix2vec.main [ПАПКА] [-p ПРОФИЛЬ] [-o ВЫХОД] [--overwrite] [--no-menu] [--no-open]
```

| Аргумент | Описание |
|---|---|
| `ПАПКА` | входная папка (по умолчанию `input/`) |
| `-p, --profile` | профиль трассировки (по умолчанию `color`) |
| `-o, --output` | выходная папка (по умолчанию `output/`) |
| `--overwrite` | перезаписывать существующие SVG (без него они пропускаются) |
| `--no-menu` | не показывать интерактивное меню |
| `--no-open` | не открывать папку результата в Проводнике |
| `--version` | версия программы |

Примеры:

```bash
python -m pix2vec.main                          # input/ -> output/, меню
python -m pix2vec.main C:\фото -p photo         # своя папка, профиль photo
python -m pix2vec.main --overwrite --no-open    # перезапись без вопросов
```

## Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pix2vec.main
```

## Тесты

```bash
python -m unittest discover -s tests -v
```

## Структура проекта

```
pix2vec/
  config.py     # пути, реестр форматов, профили трассировки
  tracer.py     # предобработка пикселей + вызов движка vtracer
  converter.py  # пакетная обработка, воркер-процессы, логи
  worker.py     # изолированный воркер одного файла
  main.py       # CLI, меню, прогресс, сводка
tests/          # unittest-тесты
docs/           # памятка по сопровождению репозитория
input/          # исходные картинки (создаётся автоматически)
output/         # готовые SVG
logs/           # логи запусков
run.bat         # запуск в один клик на Windows
```

## Известные особенности

- В `vtracer` 0.6.15 вызов движка с **keyword-аргументами роняет процесс Python** (segfault). Pix2Vec вызывает его строго позиционными аргументами. Если правишь профили в `pix2vec/config.py`, сохраняй порядок кортежа `engine` — он описан в `ENGINE_DOC` в том же файле.
- Анимированные GIF/TIFF конвертируются по первому кадру.
- Два файла в одной папке с одинаковым именем и разными расширениями дают один SVG (второй пропускается без `--overwrite`).

## Лицензия

MIT. См. [LICENSE](LICENSE).
