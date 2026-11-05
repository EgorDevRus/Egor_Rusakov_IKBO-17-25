#!/usr/bin/env bash
# Запуск с абсолютными путями к VFS и стартовому скрипту.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/run.sh" \
    --vfs "$ROOT_DIR/data/vfs_minimal.csv" \
    --script "$ROOT_DIR/data/startup.txt"
