#!/usr/bin/env bash
# Запуск эмулятора оболочки из любой текущей директории.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

exec python3 -m src.main "$@"
