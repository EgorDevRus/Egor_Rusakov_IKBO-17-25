"""Тесты источника данных из sparse-индекса Cargo."""

import json
import unittest

from cargo_deps.errors import SourceError
from cargo_deps.models import DEV, Dependency
from cargo_deps.sources.cargo_index import (
    CRATES_IO_INDEX,
    CargoIndexSource,
    crate_index_path,
    normalize_index_url,
)


def make_dependency(**values) -> dict:
    """Создаёт запись зависимости для тестового индекса."""
    payload = {
        "name": values.get("name", "dep"),
        "req": values.get("req", "^1.0"),
        "kind": values.get("kind"),
        "optional": values.get("optional", False),
        "target": values.get("target"),
        "package": values.get("package"),
        "registry": values.get("registry"),
    }
    return payload


def make_release(name: str, version: str, **values) -> str:
    """Создаёт JSON-строку релиза для тестового индекса."""
    payload = {
        "name": name,
        "vers": version,
        "yanked": values.get("yanked", False),
        "deps": values.get("deps", []),
    }
    return json.dumps(payload)


class FakeCargoSource(CargoIndexSource):
    """Источник Cargo с реестром в памяти."""

    def __init__(self, payloads: dict[str, str]) -> None:
        """Сохраняет тестовые документы индекса."""
        super().__init__("https://example.test/index")
        self.payloads = payloads

    def _download(self, url: str, package: str) -> str:
        """Возвращает тестовый документ вместо сетевого запроса."""
        if package not in self.payloads:
            raise SourceError(f"нет тестовых данных для {package}")
        return self.payloads[package]


class CargoUrlTest(unittest.TestCase):
    """Проверяет нормализацию URL и пути sparse-индекса."""

    def test_crates_io_is_normalized(self):
        """Проверяет нормализацию адреса crates.io."""
        self.assertEqual(normalize_index_url("https://crates.io"),
                         CRATES_IO_INDEX)

    def test_custom_index_gets_trailing_slash(self):
        """Проверяет добавление завершающего слэша."""
        self.assertEqual(
            normalize_index_url("https://example.test/index"),
            "https://example.test/index/",
        )

    def test_sparse_prefix_is_removed(self):
        """Проверяет удаление префикса sparse+."""
        self.assertEqual(
            normalize_index_url("sparse+https://example.test/index/"),
            "https://example.test/index/",
        )

    def test_rejects_git_url(self):
        """Проверяет отказ при URL git-репозитория."""
        with self.assertRaises(SourceError):
            normalize_index_url("https://example.test/repo.git")

    def test_rejects_non_http_url(self):
        """Проверяет отказ при не-HTTP адресе."""
        with self.assertRaises(SourceError):
            normalize_index_url("ftp://example.test/index")

    def test_index_paths(self):
        """Проверяет пути пакетов в индексе."""
        self.assertEqual(crate_index_path("a"), "1/a")
        self.assertEqual(crate_index_path("ab"), "2/ab")
        self.assertEqual(crate_index_path("abc"), "3/a/abc")
        self.assertEqual(crate_index_path("serde"), "se/rd/serde")


class CargoResolutionTest(unittest.TestCase):
    """Проверяет выбор релизов и разбор зависимостей."""

    def source(self, package: str, payload: str) -> FakeCargoSource:
        """Создаёт источник с одним тестовым пакетом."""
        return FakeCargoSource({package: payload})

    def test_latest_stable_release(self):
        """Проверяет выбор последнего стабильного релиза."""
        payload = "\n".join([
            make_release("root", "1.0.0"),
            make_release("root", "1.1.0"),
            make_release("root", "2.0.0-beta.1"),
            make_release("root", "1.2.0", yanked=True),
        ])
        source = self.source("root", payload)
        self.assertEqual(source.resolve_root("root").version, "1.1.0")

    def test_explicit_version(self):
        """Проверяет выбор явно указанной версии."""
        payload = "\n".join([
            make_release("root", "1.0.0"),
            make_release("root", "1.1.0"),
        ])
        source = self.source("root", payload)
        root = source.resolve_root("root", "1.0.0")
        self.assertEqual(root.version, "1.0.0")

    def test_missing_explicit_version(self):
        """Проверяет ошибку при отсутствии явной версии."""
        source = self.source("root", make_release("root", "1.0.0"))
        with self.assertRaises(SourceError):
            source.resolve_root("root", "9.9.9")

    def test_prerelease_fallback(self):
        """Проверяет переход на pre-release при отсутствии стабильных."""
        payload = "\n".join([
            make_release("root", "2.0.0-alpha"),
            make_release("root", "2.0.0-beta"),
        ])
        source = self.source("root", payload)
        self.assertEqual(source.resolve_root("root").version, "2.0.0-beta")

    def test_requirement_selects_newest_match(self):
        """Проверяет выбор новейшей подходящей версии."""
        payload = "\n".join([
            make_release("dep", "1.0.0"),
            make_release("dep", "1.5.0"),
            make_release("dep", "2.0.0"),
        ])
        source = self.source("dep", payload)
        resolved = source.resolve_dependency(
            Dependency("dep", requirement="^1.0")
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.version, "1.5.0")

    def test_no_matching_requirement(self):
        """Проверяет отсутствие подходящей версии."""
        source = self.source("dep", make_release("dep", "1.0.0"))
        self.assertIsNone(source.resolve_dependency(
            Dependency("dep", requirement="^2.0"),
        ))

    def test_foreign_registry_is_not_resolved(self):
        """Проверяет, что зависимость из чужого реестра не разрешается."""
        source = self.source("dep", make_release("dep", "1.0.0"))
        self.assertIsNone(source.resolve_dependency(
            Dependency("dep", requirement="^1.0", registry="other"),
        ))

    def test_invalid_requirement(self):
        """Проверяет ошибку при некорректном требовании."""
        source = self.source("dep", make_release("dep", "1.0.0"))
        with self.assertRaises(SourceError):
            source.resolve_dependency(
                Dependency("dep", requirement="not-a-version")
            )

    def test_dependencies_are_parsed(self):
        """Проверяет разбор зависимостей."""
        dependency = make_dependency(
            name="alias", package="real", kind="dev", optional=True,
            target="cfg(unix)", registry="other",
        )
        payload = make_release("root", "1.0.0", deps=[dependency])
        source = self.source("root", payload)
        root = source.resolve_root("root")
        dependencies = source.dependencies(root)
        self.assertEqual(len(dependencies), 1)
        parsed = dependencies[0]
        self.assertEqual(parsed.name, "real")
        self.assertEqual(parsed.kind, DEV)
        self.assertTrue(parsed.optional)
        self.assertEqual(parsed.target, "cfg(unix)")
        self.assertEqual(parsed.registry, "other")

    def test_invalid_json_is_reported(self):
        """Проверяет сообщение о некорректном JSON."""
        source = self.source("root", "{not json")
        with self.assertRaises(SourceError):
            source.resolve_root("root")

    def test_mismatched_name_is_reported(self):
        """Проверяет сообщение о несовпадении имени пакета."""
        source = self.source("root", make_release("other", "1.0.0"))
        with self.assertRaises(SourceError):
            source.resolve_root("root")

    def test_empty_index_is_reported(self):
        """Проверяет сообщение о пустом индексе."""
        source = self.source("root", "\n")
        with self.assertRaises(SourceError):
            source.resolve_root("root")
