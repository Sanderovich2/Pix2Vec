# Настройка репозитория на GitHub

Памятка мейнтейнера: что заполнить на GitHub и какими командами.

## Описание репозитория (About)

Поле **Description** на странице репозитория (шестерёнка справа от блока About). Уже заполнено (на английском):

```
Pix2Vec: convert raster images (PNG, JPEG, WEBP, BMP, GIF, TIFF, ICO) into vector SVG.
6 tracing profiles, batch processing, crash-isolated workers. Python CLI, Windows-first.
```

Сайт (Website) можно оставить пустым.

## Topics (теги)

Добавляются там же, в блоке About. Готовый список:

```
cli, converter, image-processing, image-tracing, jpeg, pillow, png, python,
raster-to-vector, svg, vectorization, visioncortex, vtracer, webp, windows,
batch-processing, graphics, desktop-tool
```

## Команды через gh CLI

Если gh не установлен: `winget install GitHub.cli`, затем `gh auth login`.

```bash
gh repo edit --add-topic cli,converter,image-processing,image-tracing,jpeg,pillow,png,python,raster-to-vector,svg,vectorization,visioncortex,vtracer,webp,windows,batch-processing,graphics,desktop-tool
```

Публикация релиза вручную (если не сработал авторелиз):

```bash
gh release create v1.0.0 --title "Pix2Vec v1.0.0" --notes-file .github/RELEASE_NOTES_v1.0.0.md
```

## Автоматические релизы

Воркфлоу `.github/workflows/release.yml` создаёт GitHub Release при пуше тега вида `v*`
и берёт текст из `.github/RELEASE_NOTES_<тег>.md` (если файла нет — генерирует список коммитов).

Порядок для следующего релиза:

1. Обновить версию в `pix2vec/__init__.py`.
2. Добавить раздел в `CHANGELOG.md`.
3. Положить заметки в `.github/RELEASE_NOTES_v1.1.0.md`.
4. `git tag -a v1.1.0 -m "Pix2Vec 1.1.0"` и `git push origin main --tags`.

## README

- `README.md` — английский (основной, его показывает GitHub).
- `README.ru.md` — русская версия, связаны взаимными ссылками.

При правках держи обе версии синхронными.

## CI-бейдж в README

Бейдж CI уже стоит в README проекта (репозиторий `Sanderovich2/Pix2Vec`):

```markdown
[![CI](https://github.com/Sanderovich2/Pix2Vec/actions/workflows/ci.yml/badge.svg)](https://github.com/Sanderovich2/Pix2Vec/actions/workflows/ci.yml)
```
