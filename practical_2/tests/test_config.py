"""Tests for configuration validation."""

import argparse
import shutil
import tempfile
import unittest
from pathlib import Path

from cargo_deps.config import (
    MAX_DEPTH,
    MAX_FILTER_LENGTH,
    Config,
    config_from_namespace,
    format_config,
)
from cargo_deps.errors import ConfigError


class ConfigValidationTest(unittest.TestCase):
    """Check every user-facing parameter."""

    def setUp(self):
        """Prepare the test fixture."""
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.repository = self.directory / "repository.txt"
        self.repository.write_text("A: B\nB:\n", encoding="utf-8")
        self.output = self.directory / "graph.svg"

    def namespace(self, **changes) -> argparse.Namespace:
        """Check namespace."""
        values = {
            "package": "A",
            "repository": str(self.repository),
            "mode": "test",
            "output": str(self.output),
            "ascii_mode": "off",
            "filter_text": "",
            "load_order": False,
            "package_version": None,
            "include_dev": False,
            "include_optional": False,
            "max_depth": 0,
            "no_config": False,
        }
        values.update(changes)
        return argparse.Namespace(**values)

    def test_valid_config(self):
        """Check valid config."""
        config = config_from_namespace(self.namespace())
        self.assertIsInstance(config, Config)
        self.assertEqual(config.package, "A")
        self.assertEqual(config.output, self.output)
        self.assertEqual(config.dot_output, self.directory / "graph.dot")

    def test_cargo_valid_url(self):
        """Check cargo valid url."""
        config = config_from_namespace(self.namespace(
            mode="cargo", repository="https://crates.io",
        ))
        self.assertEqual(config.mode, "cargo")

    def test_all_required_parameters_are_printed(self):
        """Check all required parameters are printed."""
        config = config_from_namespace(self.namespace())
        text = format_config(config)
        for key in (
            "package", "repository", "mode", "output", "ascii", "filter",
            "load_order", "package_version", "include_dev",
            "include_optional", "max_depth",
        ):
            self.assertIn(f"{key} =", text)

    def test_rejects_empty_package(self):
        """Check rejects empty package."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(package="  "))

    def test_rejects_lowercase_test_package(self):
        """Check rejects lowercase test package."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(package="a"))

    def test_rejects_invalid_mode(self):
        """Check rejects invalid mode."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(mode="git"))

    def test_rejects_missing_repository(self):
        """Check rejects missing repository."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(
                repository=str(self.directory / "missing.txt"),
            ))

    def test_rejects_directory_repository(self):
        """Check rejects directory repository."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(
                repository=str(self.directory),
            ))

    def test_rejects_git_repository(self):
        """Check rejects git repository."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(
                mode="cargo",
                repository="https://example.com/repo.git",
            ))

    def test_rejects_non_http_repository(self):
        """Check rejects non http repository."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(
                mode="cargo", repository="ftp://example.com/index",
            ))

    def test_rejects_non_svg_output(self):
        """Check rejects non svg output."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(
                output=str(self.directory / "graph.png"),
            ))

    def test_rejects_missing_output_directory(self):
        """Check rejects missing output directory."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(
                output=str(self.directory / "missing" / "graph.svg"),
            ))

    def test_rejects_directory_as_output(self):
        """Check rejects directory as output."""
        target = self.directory / "directory.svg"
        target.mkdir()
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(output=str(target)))

    def test_rejects_invalid_ascii_mode(self):
        """Check rejects invalid ascii mode."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(ascii_mode="full"))

    def test_rejects_control_characters_in_filter(self):
        """Check rejects control characters in filter."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(filter_text="A\nB"))

    def test_rejects_long_filter(self):
        """Check rejects long filter."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(
                filter_text="X" * (MAX_FILTER_LENGTH + 1),
            ))

    def test_rejects_invalid_version(self):
        """Check rejects invalid version."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(
                mode="cargo",
                repository="https://crates.io",
                package_version="1.2",
            ))

    def test_rejects_version_in_test_mode(self):
        """Check rejects version in test mode."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(package_version="1.2.3"))

    def test_rejects_negative_depth(self):
        """Check rejects negative depth."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(max_depth=-1))

    def test_rejects_excessive_depth(self):
        """Check rejects excessive depth."""
        with self.assertRaises(ConfigError):
            config_from_namespace(self.namespace(max_depth=MAX_DEPTH + 1))
