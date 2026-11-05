"""End-to-end tests of the command line interface."""

import io
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cargo_deps.cli import run


class CliTest(unittest.TestCase):
    """Run the CLI against temporary test repositories."""

    def setUp(self):
        """Prepare the test fixture."""
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.repository = self.directory / "repository.txt"
        self.repository.write_text(
            "A: B C\nB: D\nC: D E\nD: F\nE: F\nF:\n",
            encoding="utf-8",
        )
        self.output = self.directory / "graph.svg"

    def invoke(self, *arguments):
        """Check invoke."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = run(list(arguments))
        return code, stdout.getvalue(), stderr.getvalue()

    def base_args(self, *extra):
        """Check base args."""
        return [
            "-p", "A",
            "-r", str(self.repository),
            "-m", "test",
            "-o", str(self.output),
            *extra,
        ]

    def test_successful_run(self):
        """Check successful run."""
        code, stdout, stderr = self.invoke(*self.base_args())
        self.assertEqual(code, 0, stderr)
        self.assertTrue(self.output.exists())
        self.assertTrue(self.output.with_suffix(".dot").exists())
        ET.parse(self.output)
        self.assertIn("Configuration:", stdout)
        self.assertIn("Graph: 6 packages", stdout)

    def test_no_config_suppresses_block(self):
        """Check no config suppresses block."""
        code, stdout, _ = self.invoke(*self.base_args("--no-config"))
        self.assertEqual(code, 0)
        self.assertNotIn("Configuration:", stdout)

    def test_ascii_and_load_order(self):
        """Check ascii and load order."""
        code, stdout, _ = self.invoke(
            *self.base_args("--ascii", "tree", "--load-order"),
        )
        self.assertEqual(code, 0)
        self.assertIn("├── B", stdout)
        self.assertIn("Load order for A", stdout)
        self.assertIn("A (root)", stdout)

    def test_max_depth_one(self):
        """Check max depth one."""
        code, stdout, _ = self.invoke(
            *self.base_args("--ascii", "tree", "--max-depth", "1"),
        )
        self.assertEqual(code, 0)
        self.assertIn("Graph: 3 packages", stdout)
        self.assertNotIn("└── D", stdout)

    def test_filter_skips_branch(self):
        """Check filter skips branch."""
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
        self.assertIn("Graph: 4 packages", stdout)

    def test_invalid_configuration_exit_code(self):
        """Check invalid configuration exit code."""
        code, _, stderr = self.invoke(
            "-p", "A", "-r", str(self.directory / "missing.txt"),
            "-m", "test", "-o", str(self.output),
        )
        self.assertEqual(code, 2)
        self.assertIn("error:", stderr)

    def test_runtime_error_exit_code(self):
        """Check runtime error exit code."""
        code, _, stderr = self.invoke(
            "-p", "Z", "-r", str(self.repository), "-m", "test",
            "-o", str(self.output), "--no-config",
        )
        self.assertEqual(code, 1)
        self.assertIn("error:", stderr)

    def test_version_in_test_mode_is_rejected(self):
        """Check version in test mode is rejected."""
        code, _, stderr = self.invoke(
            *self.base_args("--package-version", "1.0.0"),
        )
        self.assertEqual(code, 2)
        self.assertIn("package-version", stderr)

    def test_output_error_is_reported(self):
        """Check output error is reported."""
        code, _, stderr = self.invoke(
            "-p", "A", "-r", str(self.repository), "-m", "test",
            "-o", str(self.directory / "missing" / "x.svg"),
        )
        self.assertEqual(code, 2)
        self.assertIn("output directory", stderr)

    def test_missing_required_argument(self):
        """Check missing required argument."""
        with self.assertRaises(SystemExit) as raised:
            run(["-r", str(self.repository)])
        self.assertEqual(raised.exception.code, 2)

    def test_invalid_mode_choice(self):
        """Check invalid mode choice."""
        with self.assertRaises(SystemExit) as raised:
            run(["-p", "A", "-r", str(self.repository), "-m", "bad"])
        self.assertEqual(raised.exception.code, 2)
