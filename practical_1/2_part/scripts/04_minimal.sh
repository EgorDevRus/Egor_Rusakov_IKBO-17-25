#!/usr/bin/env bash
# Минимальная VFS: один файл в корне.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

./run.sh --vfs data/vfs_minimal.csv \
    --script data/startup_minimal.txt
