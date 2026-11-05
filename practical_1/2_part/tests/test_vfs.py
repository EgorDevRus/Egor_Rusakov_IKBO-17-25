"""Тесты загрузки и обхода виртуальной файловой системы."""
import tempfile
import unittest
from pathlib import Path

from src.vfs import VFS, VFSFormatError


def write_csv(directory: str, text: str) -> str:
    """Записывает CSV во временный каталог и возвращает путь."""
    path = Path(directory) / "vfs.csv"
    path.write_text(text, encoding="utf-8")
    return str(path)


class VFSTestCase(unittest.TestCase):
    """Проверяет CSV-загрузку, вложенность и ошибки формата."""

    def test_load_minimal_vfs(self) -> None:
        """Минимальная VFS загружает файл и декодирует base64."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vfs = VFS()
            vfs.load_csv(write_csv(
                temp_dir,
                "path,type,content\n"
                "/readme.txt,file,SGVsbG8=\n",
            ))
        node = vfs.resolve("/readme.txt")
        self.assertFalse(node.is_dir)
        self.assertEqual(node.content, b"Hello")

    def test_nested_directories(self) -> None:
        """Полный путь создаёт все промежуточные каталоги."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vfs = VFS()
            vfs.load_csv(write_csv(
                temp_dir,
                "path,type,content\n"
                "/a/b/file.txt,file,WA==\n",
            ))
        self.assertTrue(vfs.resolve("/a").is_dir)
        self.assertTrue(vfs.resolve("/a/b").is_dir)

    def test_resolve_relative_path(self) -> None:
        """Относительный путь считается от текущего каталога."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vfs = VFS()
            vfs.load_csv(write_csv(
                temp_dir,
                "path,type,content\n"
                "/home/user/docs,dir,\n",
            ))
        vfs.cwd = vfs.resolve("/home/user")
        self.assertEqual(vfs.path_of(vfs.resolve("docs")),
                         "/home/user/docs")

    def test_missing_file(self) -> None:
        """Отсутствующий CSV даёт FileNotFoundError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.csv"
            with self.assertRaises(FileNotFoundError):
                VFS().load_csv(str(missing))

    def test_invalid_base64(self) -> None:
        """Неверный base64 отклоняется как ошибка формата."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(VFSFormatError):
                VFS().load_csv(write_csv(
                    temp_dir,
                    "path,type,content\n"
                    "/a.txt,file,***not-base64***\n",
                ))


if __name__ == "__main__":
    unittest.main()
