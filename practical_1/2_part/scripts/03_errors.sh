#!/usr/bin/env bash
# Проверка ошибок параметров, загрузки VFS и запуска скрипта.
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

failures=0

check_failure() {
    local title="$1"
    shift
    echo "=== Проверка: $title ==="
    if "$@"; then
        echo "FAIL: ожидался ненулевой код возврата"
        failures=$((failures + 1))
    else
        echo "OK: ошибка обработана"
    fi
    echo
}

check_failure "не передан --vfs" \
    ./run.sh --script data/startup.txt
check_failure "не передан --script" \
    ./run.sh --vfs data/vfs_full.csv
check_failure "неизвестный параметр" \
    ./run.sh --vfs data/vfs_full.csv \
    --script data/startup.txt --bad
check_failure "файл VFS не найден" \
    ./run.sh --vfs data/missing.csv --script data/startup.txt
check_failure "неверный формат VFS" \
    ./run.sh --vfs data/vfs_invalid.csv --script data/startup.txt
check_failure "скрипт не найден" \
    ./run.sh --vfs data/vfs_full.csv --script data/missing.txt

echo "=== Проверка: корректный запуск ==="
if ./run.sh --vfs data/vfs_full.csv --script data/startup.txt \
        > /dev/null 2>&1; then
    echo "OK: корректные параметры приняты"
else
    echo "FAIL: корректный запуск завершился ошибкой"
    failures=$((failures + 1))
fi

echo
if [ "$failures" -ne 0 ]; then
    echo "Провалено проверок: $failures"
    exit 1
fi
echo "Все проверки пройдены"
