"""Инициализация пакета тестов.

Добавляет ``src`` в ``sys.path``, чтобы приложение импортировалось без
установки. Запуск тестов: ``python -m unittest discover -s tests -t .``
(или просто ``make test``).
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
