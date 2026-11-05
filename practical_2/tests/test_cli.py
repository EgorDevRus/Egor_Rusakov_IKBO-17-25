"""Сквозные тесты интерфейса командной строки."""

import io
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cargo_deps.cli import run
from tests.support import snake_case_setup


@snake_case_setup
class CliTest(unittest.TestCase):
    """Запускает CLI на временных тестовых репозиториях."""

    def set_up(self):
        """Готовит тестовую среду."""
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.repository = self.directory / "repository.txt"
        self.repository.write_text(
            "A: B C\nB: D\nC: D E\nD: F\nE: F\nF:\n",
            encoding="utf-8",
        )
        self.output = self.directory / "graph.svg"

    def invoke(self, *arguments):
        """Запускает CLI и перехватывает вывод."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = run(list(arguments))
        return code, stdout.getvalue(), stderr.getvalue()

    def base_args(self, *extra):
        """Возвращает базовый набор аргументов."""
        return [
            "-p", "A",
            "-r", str(self.repository),
            "-m", "test",
            "-o", str(self.output),
            *extra,
        ]

    def test_successful_run(self):
        """Проверяет успешный запуск."""
        code, stdout, stderr = self.invoke(*self.base_args())
        self.assertEqual(code, 0, stderr)
        self.assertTrue(self.output.exists())
        self.assertTrue(self.output.with_suffix(".dot").exists())
        ET.parse(self.output)
        self.assertIn("Параметры запуска:", stdout)
        self.assertIn("Граф: пакетов — 6", stdout)

    def test_no_config_suppresses_block(self):
        """Проверяет, что --no-config скрывает блок параметров."""
        code, stdout, _ = self.invoke(*self.base_args("--no-config"))
        self.assertEqual(code, 0)
        self.assertNotIn("Параметры запуска:", stdout)

    def test_ascii_and_load_order(self):
        """Проверяет ASCII-дерево и порядок загрузки."""
        code, stdout, _ = self.invoke(
            *self.base_args("--ascii", "tree", "--load-order"),
        )
        self.assertEqual(code, 0)
        self.assertIn("├── B", stdout)
        self.assertIn("Порядок загрузки для A", stdout)
        self.assertIn("A (корень)", stdout)

    def test_max_depth_one(self):
        """Проверяет ограничение глубины, равное единице."""
        code, stdout, _ = self.invoke(
            *self.base_args("--ascii", "tree", "--max-depth", "1"),
        )
        self.assertEqual(code, 0)
        self.assertIn("Граф: пакетов — 3", stdout)
        self.assertNotIn("└── D", stdout)

    def test_filter_skips_branch(self):
        """Проверяет, что фильтр пропускает ветку."""
        filtered = self.directory / "filter.txt"
        filtered.write_text(
            "A: B X1\nB: C\nC: D\nX1: X2\nX2: D\nD:\n",
            encoding="utf-8",
        )
        code, stdout, _ = self.invoke(
            "-p", "A", "-r", str(filtered), "-m", "test",
            "-o", str(self.output), "--no-config", "--ascii", "tree",
            "--filter", "X",
        )
        self.assertEqual(code, 0)
        self.assertNotIn("X1", stdout)
        self.assertIn("Граф: пакетов — 4", stdout)

    def test_invalid_configuration_exit_code(self):
        """Проверяет код возврата при неверной конфигурации."""
        code, _, stderr = self.invoke(
            "-p", "A", "-r", str(self.directory / "missing.txt"),
            "-m", "test", "-o", str(self.output),
        )
        self.assertEqual(code, 2)
        self.assertIn("ошибка:", stderr)

    def test_runtime_error_exit_code(self):
        """Проверяет код возврата при ошибке выполнения."""
        code, _, stderr = self.invoke(
            "-p", "Z", "-r", str(self.repository), "-m", "test",
            "-o", str(self.output), "--no-config",
        )
        self.assertEqual(code, 1)
        self.assertIn("ошибка:", stderr)

    def test_version_in_test_mode_is_rejected(self):
        """Проверяет отказ от версии в тестовом режиме."""
        code, _, stderr = self.invoke(
            *self.base_args("--package-version", "1.0.0"),
        )
        self.assertEqual(code, 2)
        self.assertIn("package-version", stderr)

    def test_output_error_is_reported(self):
        """Проверяет сообщение об ошибке каталога вывода."""
        code, _, stderr = self.invoke(
            "-p", "A", "-r", str(self.repository), "-m", "test",
            "-o", str(self.directory / "missing" / "x.svg"),
        )
        self.assertEqual(code, 2)
        self.assertIn("каталог вывода", stderr)

    def test_missing_required_argument(self):
        """Проверяет отсутствие обязательного аргумента."""
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                run(["-r", str(self.repository)])
        self.assertEqual(raised.exception.code, 2)

    def test_invalid_mode_choice(self):
        """Проверяет неверный выбор режима."""
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                run(["-p", "A", "-r", str(self.repository), "-m", "bad"])
        self.assertEqual(raised.exception.code, 2)
