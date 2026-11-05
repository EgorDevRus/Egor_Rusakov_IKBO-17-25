"""Инициализация пакета тестов.

Добавляет ``src`` в ``sys.path``, чтобы приложение импортировалось без
установки. Запуск тестов: ``python -m unittest discover -s tests -t .``
(или просто ``make test``).
"""

import os
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _ensure_usable_tempdir() -> None:
    """Выбирает рабочий временный каталог для тестов."""
    candidate = os.environ.get("TMPDIR")
    if candidate and not Path(candidate).is_dir():
        os.environ.pop("TMPDIR", None)
        tempfile.tempdir = None
    try:
        tempfile.gettempdir()
    except FileNotFoundError:
        fallback = Path(__file__).resolve().parents[1] / ".test-tmp"
        fallback.mkdir(exist_ok=True)
        os.environ["TMPDIR"] = str(fallback)
        tempfile.tempdir = str(fallback)


_ensure_usable_tempdir()
