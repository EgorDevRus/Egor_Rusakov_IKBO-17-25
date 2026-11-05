"""Тесты минимальной реализации SemVer."""

import unittest

from cargo_deps.semver import (
    SemverError,
    parse_requirement,
    parse_version,
)


class VersionParsingTest(unittest.TestCase):
    """Проверяет разбор и вывод версий."""

    def test_parses_release(self):
        """Проверяет разбор обычного релиза."""
        version = parse_version("1.2.3")
        self.assertEqual((version.major, version.minor, version.patch),
                         (1, 2, 3))
        self.assertEqual(str(version), "1.2.3")

    def test_parses_prerelease(self):
        """Проверяет разбор pre-release-версии."""
        version = parse_version("1.0.0-rc.1")
        self.assertTrue(version.is_prerelease)
        self.assertEqual(str(version), "1.0.0-rc.1")

    def test_rejects_incomplete_version(self):
        """Проверяет отказ при неполной версии."""
        with self.assertRaises(SemverError):
            parse_version("1.2")

    def test_orders_prereleases(self):
        """Проверяет порядок pre-release-версий."""
        self.assertLess(parse_version("1.0.0-alpha"),
                        parse_version("1.0.0-beta"))
        self.assertLess(parse_version("1.0.0-beta.2"),
                        parse_version("1.0.0-beta.11"))
        self.assertLess(parse_version("1.0.0-rc.1"),
                        parse_version("1.0.0"))


class RequirementTest(unittest.TestCase):
    """Проверяет сопоставление требований Cargo."""

    def matches(self, requirement: str, version: str) -> bool:
        """Проверяет соответствие версии требованию."""
        return parse_requirement(requirement).matches(parse_version(version))

    def test_caret(self):
        """Проверяет оператор ``^``."""
        self.assertTrue(self.matches("^1.2.3", "1.9.0"))
        self.assertFalse(self.matches("^1.2.3", "2.0.0"))
        self.assertTrue(self.matches("^0.2.3", "0.2.9"))
        self.assertFalse(self.matches("^0.2.3", "0.3.0"))

    def test_tilde(self):
        """Проверяет оператор ``~``."""
        self.assertTrue(self.matches("~1.2.3", "1.2.9"))
        self.assertFalse(self.matches("~1.2.3", "1.3.0"))

    def test_wildcard(self):
        """Проверяет шаблоны версий."""
        self.assertTrue(self.matches("1.2.*", "1.2.9"))
        self.assertFalse(self.matches("1.2.*", "1.3.0"))
        self.assertTrue(self.matches("*", "42.0.0"))

    def test_comparison_range(self):
        """Проверяет диапазон сравнений."""
        self.assertTrue(self.matches(">=1.0, <2.0", "1.9.9"))
        self.assertFalse(self.matches(">=1.0, <2.0", "2.0.0"))
        self.assertTrue(self.matches(">1.2", "1.3.0"))

    def test_exact(self):
        """Проверяет точное совпадение версии."""
        self.assertTrue(self.matches("=1.2.3", "1.2.3"))
        self.assertFalse(self.matches("=1.2.3", "1.2.4"))

    def test_prerelease_policy(self):
        """Проверяет правила для pre-release-версий."""
        self.assertFalse(self.matches("^1.0.0", "1.1.0-rc.1"))
        self.assertTrue(self.matches("^1.0.0-beta", "1.1.0-rc.1"))

    def test_alternatives(self):
        """Проверяет альтернативы через ``||``."""
        requirement = parse_requirement("=1.0.0 || =2.0.0")
        self.assertTrue(requirement.matches(parse_version("2.0.0")))
        self.assertFalse(requirement.matches(parse_version("1.5.0")))

    def test_rejects_bad_requirement(self):
        """Проверяет отказ при некорректном требовании."""
        with self.assertRaises(SemverError):
            parse_requirement("not-a-version")
