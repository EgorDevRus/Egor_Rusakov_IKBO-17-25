"""Application error hierarchy.

Every error carries a short human-readable message and the process exit
code that the CLI should return.  Usage and configuration errors use the
traditional exit code 2, while runtime failures use 1.
"""


class CargoDepsError(Exception):
    """Base class for all expected application errors."""

    exit_code = 1

    def __init__(self, message: str) -> None:
        """Store the message for the CLI error printer."""
        super().__init__(message)
        self.message = message


class ConfigError(CargoDepsError):
    """Raised when a user-supplied command line value is invalid."""

    exit_code = 2


class SourceError(CargoDepsError):
    """Raised when dependency data cannot be read or parsed."""

    exit_code = 1


class RenderError(CargoDepsError):
    """Raised when the graph image cannot be written."""

    exit_code = 1
