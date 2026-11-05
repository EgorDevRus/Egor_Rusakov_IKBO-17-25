"""Оболочка с REPL, виртуальной ФС и командами ls, cd, exit."""
import getpass
import socket
import sys
from typing import Callable, Dict, List

from src.parser import Command, ParseError, parse_input
from src.vfs import VFS, VFSNode

HOME_PREFIX = "~"
PATH_SEPARATOR = "/"
COMMENT_PREFIX = "#"
DEFAULT_LS_PATH = "."
MAX_LS_ARGUMENTS = 1
MAX_CD_ARGUMENTS = 1


class ScriptError(OSError):
    """Ошибка чтения стартового скрипта."""


class Shell:
    """Интерактивная оболочка над виртуальной файловой системой."""

    def __init__(self, vfs: VFS) -> None:
        """Запоминает VFS и данные реальной ОС для приглашения."""
        self.vfs = vfs
        self.running = True
        self.user = getpass.getuser()
        self.host = socket.gethostname()

    def get_prompt(self) -> str:
        """Формирует приглашение с реальными пользователем и хостом."""
        return f"{self.user}@{self.host}:{self.get_display_path()}$ "

    def get_display_path(self) -> str:
        """Сокращает путь текущего каталога VFS до ~, если возможно."""
        current = self.vfs.path_of(self.vfs.cwd)
        home = self.vfs.path_of(self.vfs.home)
        if current == home:
            return HOME_PREFIX
        if home == PATH_SEPARATOR:
            return current
        prefix = home.rstrip(PATH_SEPARATOR) + PATH_SEPARATOR
        if current.startswith(prefix):
            return HOME_PREFIX + current[len(home):]
        return current

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
        """Выполняет строку скрипта, пропуская пустые и комментарии."""
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
        """Показывает содержимое каталога или имя файла."""
        if len(args) > MAX_LS_ARGUMENTS:
            self._error("ls: слишком много аргументов")
            return
        target = args[0] if args else DEFAULT_LS_PATH
        try:
            node = self.vfs.resolve(target)
        except (FileNotFoundError, NotADirectoryError) as error:
            self._error(f"ls: {error}")
            return
        if not node.is_dir:
            print(node.name)
            return
        self._print_children(node)

    def _print_children(self, node: VFSNode) -> None:
        """Печатает отсортированное содержимое каталога."""
        for name in sorted(node.children):
            child = node.children[name]
            suffix = PATH_SEPARATOR if child.is_dir else ""
            print(f"{name}{suffix}")

    def _cmd_cd(self, args: List[str]) -> None:
        """Меняет текущий каталог VFS."""
        if len(args) > MAX_CD_ARGUMENTS:
            self._error("cd: слишком много аргументов")
            return
        target = args[0] if args else HOME_PREFIX
        try:
            node = self.vfs.resolve(target)
        except (FileNotFoundError, NotADirectoryError) as error:
            self._error(f"cd: {error}")
            return
        if not node.is_dir:
            self._error(f"cd: не является каталогом: {target}")
            return
        self.vfs.cwd = node

    def _cmd_exit(self, args: List[str]) -> None:
        """Завершает работу оболочки."""
        if args:
            self._error("exit: аргументы не поддерживаются")
            return
        self.running = False

    def _error(self, message: str) -> None:
        """Выводит ошибку в поток ошибок."""
        print(message, file=sys.stderr)

    def _print_exit(self) -> None:
        """Сообщает о завершении по EOF или Ctrl+C."""
        print("\nВыход.")
