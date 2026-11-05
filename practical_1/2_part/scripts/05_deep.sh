#!/usr/bin/env bash
# VFS с глубиной более трёх уровней.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

./run.sh --vfs data/vfs_deep.csv --script data/startup_deep.txt
