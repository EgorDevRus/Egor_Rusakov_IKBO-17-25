"""Test package bootstrap.

Adds ``src`` to ``sys.path`` so the application can be imported without
being installed.  Run tests with ``python -m unittest discover -s tests
-t .`` (or simply ``make test``).
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
