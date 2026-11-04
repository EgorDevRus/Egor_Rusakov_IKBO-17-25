"""Точка входа эмулятора оболочки."""
from src.shell import Shell


def main() -> None:
    """Запускает интерактивный режим."""
    Shell().run()


if __name__ == "__main__":
    main()
