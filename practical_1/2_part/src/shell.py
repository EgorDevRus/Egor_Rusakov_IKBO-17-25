"""Оболочка с REPL, заглушками ls/cd и стартовым скриптом."""
import getpass
import os
import socket
import sys
from typing import Callable, Dict, List

from src.parser import Command, ParseError, parse_input

HOME_PREFIX = "~"
NO_ARGUMENTS = "аргументов нет"
COMMENT_PREFIX = "#"


class ScriptError(OSError):
    """Ошибка чтения стартового скрипта."""


class Shell:
    """Интерактивная оболочка второго этапа."""

    def __init__(self) -> None:
        """Запоминает данные реальной ОС для приглашения."""
        self.running = True
        self.user = getpass.getuser()
        self.host = socket.gethostname()

    def get_prompt(self) -> str:
        """Формирует приглашение на основе данных реальной ОС."""
        current = os.getcwd()
        home = os.path.expanduser("~")
        if current == home:
            current = HOME_PREFIX
        elif current.startswith(home + os.sep):
            current = HOME_PREFIX + current[len(home):]
        return f"{self.user}@{self.host}:{current}$ "

    def run(self) -> None:
        """Запускает цикл чтения, разбора и выполнения команд."""
        while self.running:
            try:
                line = input(self.get_prompt())
            except (EOFError, KeyboardInterrupt):
                self._print_exit()
                break
            self.execute_line(line)

    def run_script(self, script_path: str) -> None:
        """Выполняет стартовый скрипт, имитируя диалог с пользователем."""
        try:
            with open(script_path, "r", encoding="utf-8") as stream:
                lines = stream.readlines()
        except OSError as error:
            raise ScriptError(
                f"не удалось прочитать {script_path}: {error}"
            ) from error
        for line in lines:
            if not self.running:
                break
            self._run_script_line(line)

    def _run_script_line(self, line: str) -> None:
        """Выполняет одну строку скрипта, пропуская пустые и комментарии."""
        command = line.rstrip("\r\n")
        if not command.strip():
            return
        if command.lstrip().startswith(COMMENT_PREFIX):
            return
        print(f"{self.get_prompt()}{command}", flush=True)
        self.execute_line(command)

    def execute_line(self, line: str) -> None:
        """Разбирает и выполняет одну строку ввода."""
        try:
            command = parse_input(line)
        except ParseError as error:
            self._error(f"ошибка разбора: {error}")
            return
        if command is None:
            return
        self._dispatch(command)

    def _dispatch(self, command: Command) -> None:
        """Передаёт команду соответствующему обработчику."""
        handlers: Dict[str, Callable[[List[str]], None]] = {
            "ls": self._cmd_ls,
            "cd": self._cmd_cd,
            "exit": self._cmd_exit,
        }
        handler = handlers.get(command.name)
        if handler is None:
            self._error(f"команда не найдена: {command.name}")
            return
        handler(command.args)

    def _cmd_ls(self, args: List[str]) -> None:
        """Заглушка ls: выводит имя команды и аргументы."""
        self._print_stub("ls", args)

    def _cmd_cd(self, args: List[str]) -> None:
        """Заглушка cd: выводит имя команды и аргументы."""
        self._print_stub("cd", args)

    def _cmd_exit(self, args: List[str]) -> None:
        """Завершает работу оболочки."""
        if args:
            self._error("exit: аргументы не поддерживаются")
            return
        self.running = False

    def _print_stub(self, name: str, args: List[str]) -> None:
        """Печатает имя команды и разобранные аргументы."""
        if not args:
            print(f"{name}: {NO_ARGUMENTS}")
            return
        print(f"{name}: аргументы: {args}")

    def _error(self, message: str) -> None:
        """Выводит ошибку в поток ошибок."""
        print(message, file=sys.stderr)

    def _print_exit(self) -> None:
        """Сообщает о завершении по EOF или Ctrl+C."""
        print("\nВыход.")
