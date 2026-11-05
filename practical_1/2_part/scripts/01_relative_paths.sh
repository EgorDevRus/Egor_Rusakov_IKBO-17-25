#!/usr/bin/env bash
# Запуск с относительными путями к VFS и стартовому скрипту.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

./run.sh --vfs data/vfs_full.csv --script data/startup.txt
