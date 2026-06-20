# Contributing

Contributions are welcome when they keep the project local, ethical, and easy
to maintain.

## Guidelines

- Keep the tool focused on local CLI/web usage.
- Do not add login bypassing, DRM bypassing, scraping behind authorization, or
  public downloader-service behavior.
- Prefer small, readable Python functions with type hints.
- Avoid heavy frameworks unless there is a clear maintenance benefit.
- Preserve `shell=False` subprocess usage.

## Development setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r requirements-dev.txt
brew install yt-dlp aria2 ffmpeg
```

## Tests

Run before opening a pull request:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m py_compile app.py downloader.py extractor.py finder.py jobs.py utils.py
node --check static/app.js
.venv/bin/python -m ruff check .
```

Do not include downloaded videos, partial downloads, logs, `.venv`, `.idea`, or
`__pycache__` files in commits.
