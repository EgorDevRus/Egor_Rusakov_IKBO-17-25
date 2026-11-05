"""Точка входа эмулятора оболочки второго этапа."""
import sys

from src.config import Config, parse_args
from src.shell import ScriptError, Shell


def print_debug(config: Config) -> None:
    """Выводит все параметры запуска в отладочном режиме."""
    print("[DEBUG] Параметры запуска:", flush=True)
    print(f"[DEBUG]   --vfs = {config.vfs_path}", flush=True)
    print(f"[DEBUG]   --script = {config.script_path}", flush=True)


def main() -> None:
    """Выполняет стартовый скрипт, затем запускает REPL."""
    config = parse_args()
    print_debug(config)
    shell = Shell()
    try:
        shell.run_script(config.script_path)
    except ScriptError as error:
        print(f"Ошибка запуска: {error}", file=sys.stderr)
        sys.exit(1)
    shell.run()


if __name__ == "__main__":
    main()
