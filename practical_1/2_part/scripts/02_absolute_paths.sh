#!/usr/bin/env bash
# Полная VFS и абсолютные пути к файлам данных.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/run.sh" \
    --vfs "$ROOT_DIR/data/vfs_full.csv" \
    --script "$ROOT_DIR/data/startup.txt"
