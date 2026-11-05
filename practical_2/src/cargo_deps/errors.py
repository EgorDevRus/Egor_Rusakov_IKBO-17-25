"""Иерархия ошибок приложения.

Каждая ошибка содержит короткое понятное сообщение и код возврата,
который должен вернуть интерфейс командной строки. Ошибки использования
и конфигурации завершаются кодом 2, ошибки выполнения — кодом 1.
"""


class CargoDepsError(Exception):
    """Базовый класс ожидаемых ошибок приложения."""

    exit_code = 1

    def __init__(self, message: str) -> None:
        """Сохраняет сообщение для вывода в CLI."""
        super().__init__(message)
        self.message = message


class ConfigError(CargoDepsError):
    """Ошибка в значении параметра командной строки."""

    exit_code = 2


class SourceError(CargoDepsError):
    """Ошибка чтения или разбора данных о зависимостях."""

    exit_code = 1


class RenderError(CargoDepsError):
    """Ошибка записи изображения графа."""

    exit_code = 1
