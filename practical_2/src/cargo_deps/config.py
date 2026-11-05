"""Validation and the immutable command line configuration."""

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import ConfigError
from .graph import MAX_DEPTH, UNLIMITED_DEPTH
from .semver import SemverError, parse_version

MODES = ("cargo", "test")
ASCII_MODES = ("off", "tree")
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
TEST_PACKAGE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
MAX_NAME_LENGTH = 100
MAX_FILTER_LENGTH = 80
CONTROL_LIMIT = 32
SVG_SUFFIX = ".svg"
NONE_TEXT = "<none>"
LATEST_TEXT = "<latest>"
UNLIMITED_TEXT = "unlimited"


@dataclass(frozen=True)
class Config:
    """Validated settings of one program run."""

    package: str
    repository: str
    mode: str
    output: Path
    ascii_mode: str
    filter_text: str
    load_order: bool
    package_version: str | None
    include_dev: bool
    include_optional: bool
    max_depth: int
    no_config: bool

    @property
    def dot_output(self) -> Path:
        """Return the DOT file path next to the SVG image."""
        return self.output.with_suffix(".dot")

    def as_pairs(self) -> list[tuple[str, str]]:
        """Return all user-configurable values as key-value pairs."""
        depth = (
            UNLIMITED_TEXT
            if self.max_depth == UNLIMITED_DEPTH
            else str(self.max_depth)
        )
        return [
            ("package", self.package),
            ("repository", self.repository),
            ("mode", self.mode),
            ("output", str(self.output)),
            ("ascii", self.ascii_mode),
            ("filter", self.filter_text or NONE_TEXT),
            ("load_order", _bool_text(self.load_order)),
            ("package_version", self.package_version or LATEST_TEXT),
            ("include_dev", _bool_text(self.include_dev)),
            ("include_optional", _bool_text(self.include_optional)),
            ("max_depth", depth),
        ]


def _bool_text(value: bool) -> str:
    """Return a lowercase textual boolean."""
    return "true" if value else "false"


def _ensure_text(value: str, option: str) -> str:
    """Reject control characters in a user value."""
    if any(ord(character) < CONTROL_LIMIT for character in value):
        raise ConfigError(f"{option} must not contain control characters")
    return value


def _validate_mode(value: str) -> str:
    """Validate the repository mode choice."""
    if value not in MODES:
        choices = ", ".join(MODES)
        raise ConfigError(f"--mode must be one of: {choices}")
    return value


def _validate_package(package: str, mode: str) -> str:
    """Validate the package name for the selected mode."""
    value = _ensure_text(package, "--package").strip()
    if not value:
        raise ConfigError("--package must not be empty")
    if len(value) > MAX_NAME_LENGTH:
        raise ConfigError(
            f"--package must be at most {MAX_NAME_LENGTH} characters"
        )
    pattern = TEST_PACKAGE_RE if mode == "test" else PACKAGE_RE
    if pattern.match(value) is None:
        if mode == "test":
            raise ConfigError(
                "--package in test mode must consist of capital Latin "
                "letters, digits and underscores"
            )
        raise ConfigError(
            "--package must start with a letter or digit and contain "
            "only letters, digits, '-' and '_'"
        )
    return value


def _validate_test_repository(value: str) -> str:
    """Validate a test repository file path."""
    path = Path(value).expanduser()
    if not path.exists():
        raise ConfigError(f"test repository does not exist: {path}")
    if not path.is_file():
        raise ConfigError(f"test repository is not a file: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ConfigError(f"cannot stat test repository {path}: {exc}") from exc
    if size == 0:
        raise ConfigError(f"test repository is empty: {path}")
    if not os.access(path, os.R_OK):
        raise ConfigError(f"test repository is not readable: {path}")
    return str(path)


def _validate_cargo_repository(value: str) -> str:
    """Validate a Cargo registry URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(
            "--repository in cargo mode must be an HTTP(S) registry URL"
        )
    if parsed.path.endswith(".git"):
        raise ConfigError(
            "--repository must be a Cargo sparse index URL, not a git URL"
        )
    return value


def _validate_repository(repository: str, mode: str) -> str:
    """Validate the repository argument."""
    value = _ensure_text(repository, "--repository").strip()
    if not value:
        raise ConfigError("--repository must not be empty")
    if mode == "test":
        return _validate_test_repository(value)
    return _validate_cargo_repository(value)


def _validate_output(output: str) -> Path:
    """Validate the SVG output path and its directory."""
    value = _ensure_text(output, "--output").strip()
    if not value:
        raise ConfigError("--output must not be empty")
    path = Path(value).expanduser()
    if path.suffix.lower() != SVG_SUFFIX:
        raise ConfigError("--output must have the .svg extension")
    if path.exists() and path.is_dir():
        raise ConfigError(f"--output points to a directory: {path}")
    parent = path.parent
    if not parent.exists():
        raise ConfigError(f"output directory does not exist: {parent}")
    if not parent.is_dir():
        raise ConfigError(f"output parent is not a directory: {parent}")
    if not os.access(parent, os.W_OK):
        raise ConfigError(f"output directory is not writable: {parent}")
    return path


def _validate_ascii(value: str) -> str:
    """Validate the ASCII tree mode choice."""
    if value not in ASCII_MODES:
        choices = ", ".join(ASCII_MODES)
        raise ConfigError(f"--ascii must be one of: {choices}")
    return value


def _validate_filter(value: str) -> str:
    """Validate the dependency filter substring."""
    _ensure_text(value, "--filter")
    if len(value) > MAX_FILTER_LENGTH:
        raise ConfigError(
            f"--filter must be at most {MAX_FILTER_LENGTH} characters"
        )
    return value


def _validate_version(value: str | None) -> str | None:
    """Validate an optional explicit package version."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        raise ConfigError("--package-version must not be empty")
    try:
        parse_version(cleaned)
    except SemverError as exc:
        raise ConfigError(f"--package-version is invalid: {exc}") from exc
    return cleaned


def _validate_depth(value: int) -> int:
    """Validate the traversal depth limit."""
    if value < UNLIMITED_DEPTH or value > MAX_DEPTH:
        raise ConfigError(
            f"--max-depth must be between {UNLIMITED_DEPTH} and {MAX_DEPTH}"
        )
    return value


def config_from_namespace(namespace: argparse.Namespace) -> Config:
    """Validate a parsed argument namespace and build a Config."""
    mode = _validate_mode(namespace.mode)
    package = _validate_package(namespace.package, mode)
    repository = _validate_repository(namespace.repository, mode)
    output = _validate_output(namespace.output)
    ascii_mode = _validate_ascii(namespace.ascii_mode)
    filter_text = _validate_filter(namespace.filter_text)
    package_version = _validate_version(namespace.package_version)
    max_depth = _validate_depth(namespace.max_depth)
    if mode == "test" and package_version is not None:
        raise ConfigError(
            "--package-version is only supported in cargo mode"
        )
    return Config(
        package=package,
        repository=repository,
        mode=mode,
        output=output,
        ascii_mode=ascii_mode,
        filter_text=filter_text,
        load_order=bool(namespace.load_order),
        package_version=package_version,
        include_dev=bool(namespace.include_dev),
        include_optional=bool(namespace.include_optional),
        max_depth=max_depth,
        no_config=bool(namespace.no_config),
    )


def format_config(config: Config) -> str:
    """Return the stage-one key-value parameter listing."""
    lines = ["Configuration:"]
    lines.extend(f"  {key} = {value}" for key, value in config.as_pairs())
    return "\n".join(lines)
