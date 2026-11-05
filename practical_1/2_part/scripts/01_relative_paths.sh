#!/usr/bin/env bash
# Полная VFS и относительные пути к файлам данных.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

./run.sh --vfs data/vfs_full.csv --script data/startup.txt
