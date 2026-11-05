"""Точка входа эмулятора оболочки третьего этапа."""
import sys

from src.config import Config, parse_args
from src.shell import ScriptError, Shell
from src.vfs import VFS, VFSError


def print_debug(config: Config) -> None:
    """Выводит все параметры запуска в отладочном режиме."""
    print("[DEBUG] Параметры запуска:", flush=True)
    print(f"[DEBUG]   --vfs = {config.vfs_path}", flush=True)
    print(f"[DEBUG]   --script = {config.script_path}", flush=True)


def load_vfs(config: Config) -> VFS:
    """Загружает VFS из указанного в конфигурации файла."""
    vfs = VFS()
    try:
        vfs.load_csv(config.vfs_path)
    except (OSError, VFSError) as error:
        print(f"Ошибка загрузки VFS: {error}", file=sys.stderr)
        sys.exit(1)
    return vfs


def main() -> None:
    """Загружает VFS, выполняет скрипт, затем запускает REPL."""
    config = parse_args()
    print_debug(config)
    shell = Shell(load_vfs(config))
    try:
        shell.run_script(config.script_path)
    except ScriptError as error:
        print(f"Ошибка запуска: {error}", file=sys.stderr)
        sys.exit(1)
    shell.run()


if __name__ == "__main__":
    main()
