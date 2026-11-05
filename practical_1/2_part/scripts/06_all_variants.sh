#!/usr/bin/env bash
# Последовательный запуск на всех вариантах VFS.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_variant() {
    local name="$1"
    local script="$2"
    echo "=== VFS: ${name} ==="
    ./run.sh --vfs "data/vfs_${name}.csv" --script "$script"
    echo
}

run_variant minimal data/startup_minimal.txt
run_variant full data/startup.txt
run_variant deep data/startup_deep.txt
