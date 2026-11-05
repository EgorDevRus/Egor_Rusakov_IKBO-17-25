"""Виртуальная файловая система, загружаемая из CSV-файла."""
import base64
import binascii
import csv
import getpass
from pathlib import Path
from typing import Dict, List, Optional, TextIO

REQUIRED_COLUMNS = ("path", "type", "content")
DIR_TYPE = "dir"
FILE_TYPE = "file"
ROOT_NAME = "/"
HOME_PREFIX = "~"
PATH_SEPARATOR = "/"
CURRENT_DIR = "."
PARENT_DIR = ".."
MIN_PATH_PARTS = 1
HOME_CANDIDATES = ("/home/{user}", "/home/user", "/root")


class VFSError(Exception):
    """Базовая ошибка виртуальной файловой системы."""


class VFSFormatError(VFSError):
    """Ошибка формата CSV-описания виртуальной файловой системы."""


class VFSNode:
    """Узел дерева виртуальной файловой системы."""

    def __init__(
        self,
        name: str,
        is_dir: bool,
        content: bytes = b"",
        parent: Optional["VFSNode"] = None,
    ) -> None:
        """Создаёт узел с именем, типом, содержимым и родителем."""
        self.name = name
        self.is_dir = is_dir
        self.content = content
        self.parent = parent
        self.children: Dict[str, "VFSNode"] = {}


class VFS:
    """Виртуальная файловая система в памяти."""

    def __init__(self) -> None:
        """Создаёт пустую VFS с корневым каталогом."""
        self.root = VFSNode(ROOT_NAME, True)
        self.cwd = self.root
        self.home = self.root

    def load_csv(self, file_path: str) -> None:
        """Загружает дерево VFS из CSV-файла, не изменяя файл."""
        source = Path(file_path)
        if not source.is_file():
            raise FileNotFoundError(f"файл VFS не найден: {file_path}")
        try:
            with source.open(
                "r", encoding="utf-8", newline=""
            ) as stream:
                root = self._build_tree(stream)
        except UnicodeError as error:
            raise VFSFormatError(
                f"файл VFS не является UTF-8: {file_path}"
            ) from error
        except csv.Error as error:
            raise VFSFormatError(f"ошибка CSV: {error}") from error
        self.root = root
        self.cwd = root
        self.home = self._detect_home()

    def _build_tree(self, stream: TextIO) -> VFSNode:
        """Читает строки CSV и собирает из них дерево каталогов."""
        reader = csv.DictReader(stream)
        self._check_header(reader.fieldnames)
        root = VFSNode(ROOT_NAME, True)
        for line_number, row in enumerate(reader, start=2):
            self._add_row(root, row, line_number)
        return root

    def _check_header(self, fieldnames: Optional[List[str]]) -> None:
        """Проверяет наличие обязательных колонок CSV."""
        names = fieldnames or []
        missing = [name for name in REQUIRED_COLUMNS if name not in names]
        if missing:
            joined = ", ".join(missing)
            raise VFSFormatError(f"в CSV нет колонок: {joined}")

    def _add_row(
        self,
        root: VFSNode,
        row: Dict[str, str],
        line_number: int,
    ) -> None:
        """Добавляет в дерево один файл или каталог из строки CSV."""
        raw_path = (row.get("path") or "").strip()
        node_type = (row.get("type") or "").strip()
        content = row.get("content") or ""
        if not raw_path:
            raise VFSFormatError(f"строка {line_number}: пустой path")
        if node_type not in (DIR_TYPE, FILE_TYPE):
            raise VFSFormatError(
                f"строка {line_number}: неверный type {node_type!r}"
            )
        parts = self._split_path(raw_path, line_number)
        parent = self._ensure_parents(root, parts[:-1], raw_path)
        name = parts[-1]
        if name in parent.children:
            raise VFSFormatError(f"дубликат пути: {raw_path}")
        node = self._make_node(name, node_type, content, raw_path, parent)
        parent.children[name] = node

    def _split_path(
        self, raw_path: str, line_number: int
    ) -> List[str]:
        """Преобразует путь из CSV в список нормальных компонентов."""
        if not raw_path.startswith(PATH_SEPARATOR):
            raise VFSFormatError(
                f"строка {line_number}: путь должен быть абсолютным"
            )
        parts = [
            part
            for part in raw_path.split(PATH_SEPARATOR)
            if part not in ("", CURRENT_DIR)
        ]
        if PARENT_DIR in parts:
            raise VFSFormatError(
                f"строка {line_number}: путь не должен содержать .."
            )
        if len(parts) < MIN_PATH_PARTS:
            raise VFSFormatError(
                f"строка {line_number}: нельзя добавить корень"
            )
        return parts

    def _ensure_parents(
        self,
        root: VFSNode,
        names: List[str],
        raw_path: str,
    ) -> VFSNode:
        """Создаёт отсутствующие родительские каталоги."""
        current = root
        for name in names:
            child = current.children.get(name)
            if child is None:
                child = VFSNode(name, True, b"", current)
                current.children[name] = child
            elif not child.is_dir:
                raise VFSFormatError(
                    f"{raw_path}: {name} не является каталогом"
                )
            current = child
        return current

    def _make_node(
        self,
        name: str,
        node_type: str,
        content: str,
        raw_path: str,
        parent: VFSNode,
    ) -> VFSNode:
        """Создаёт узел, проверяя содержимое каталога и base64."""
        if node_type == DIR_TYPE:
            if content.strip():
                raise VFSFormatError(
                    f"{raw_path}: у каталога не должно быть содержимого"
                )
            return VFSNode(name, True, b"", parent)
        data = self._decode_content(content, raw_path)
        return VFSNode(name, False, data, parent)

    def _decode_content(self, content: str, raw_path: str) -> bytes:
        """Декодирует содержимое файла из base64."""
        try:
            return base64.b64decode(content.strip(), validate=True)
        except (binascii.Error, ValueError) as error:
            raise VFSFormatError(
                f"{raw_path}: содержимое не является base64"
            ) from error

    def _detect_home(self) -> VFSNode:
        """Находит домашний каталог VFS для текущего пользователя."""
        user = getpass.getuser()
        for template in HOME_CANDIDATES:
            candidate = template.format(user=user)
            try:
                node = self.resolve(candidate)
            except (FileNotFoundError, NotADirectoryError):
                continue
            if node.is_dir:
                return node
        return self.root

    def resolve(self, path: str) -> VFSNode:
        """Возвращает узел по абсолютному, относительному или ~ пути."""
        if not path:
            return self.cwd
        node = self.cwd
        remainder = path
        if path == HOME_PREFIX or path.startswith(
            HOME_PREFIX + PATH_SEPARATOR
        ):
            node = self.home
            remainder = path[len(HOME_PREFIX):]
        elif path.startswith(PATH_SEPARATOR):
            node = self.root
        parts = [
            part
            for part in remainder.split(PATH_SEPARATOR)
            if part not in ("", CURRENT_DIR)
        ]
        for part in parts:
            node = self._step(node, part, path)
        return node

    def _step(self, node: VFSNode, part: str, path: str) -> VFSNode:
        """Переходит к одному компоненту пути."""
        if not node.is_dir:
            raise NotADirectoryError(f"не является каталогом: {path}")
        if part == PARENT_DIR:
            if node.parent is None:
                return node
            return node.parent
        child = node.children.get(part)
        if child is None:
            raise FileNotFoundError(f"путь не найден: {path}")
        return child

    def path_of(self, node: VFSNode) -> str:
        """Строит абсолютный путь для узла дерева."""
        names: List[str] = []
        current = node
        while current.parent is not None:
            names.append(current.name)
            current = current.parent
        if not names:
            return ROOT_NAME
        return ROOT_NAME + PATH_SEPARATOR.join(reversed(names))
