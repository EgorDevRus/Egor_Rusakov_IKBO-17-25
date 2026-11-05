"""Tests for the minimal SemVer implementation."""

import unittest

from cargo_deps.semver import (
    SemverError,
    parse_requirement,
    parse_version,
)


class VersionParsingTest(unittest.TestCase):
    """Check parsing and rendering of versions."""

    def test_parses_release(self):
        """Check parses release."""
        version = parse_version("1.2.3")
        self.assertEqual((version.major, version.minor, version.patch),
                         (1, 2, 3))
        self.assertEqual(str(version), "1.2.3")

    def test_parses_prerelease(self):
        """Check parses prerelease."""
        version = parse_version("1.0.0-rc.1")
        self.assertTrue(version.is_prerelease)
        self.assertEqual(str(version), "1.0.0-rc.1")

    def test_rejects_incomplete_version(self):
        """Check rejects incomplete version."""
        with self.assertRaises(SemverError):
            parse_version("1.2")

    def test_orders_prereleases(self):
        """Check orders prereleases."""
        self.assertLess(parse_version("1.0.0-alpha"),
                        parse_version("1.0.0-beta"))
        self.assertLess(parse_version("1.0.0-beta.2"),
                        parse_version("1.0.0-beta.11"))
        self.assertLess(parse_version("1.0.0-rc.1"),
                        parse_version("1.0.0"))


class RequirementTest(unittest.TestCase):
    """Check Cargo requirement matching."""

    def matches(self, requirement: str, version: str) -> bool:
        """Check matches."""
        return parse_requirement(requirement).matches(parse_version(version))

    def test_caret(self):
        """Check caret."""
        self.assertTrue(self.matches("^1.2.3", "1.9.0"))
        self.assertFalse(self.matches("^1.2.3", "2.0.0"))
        self.assertTrue(self.matches("^0.2.3", "0.2.9"))
        self.assertFalse(self.matches("^0.2.3", "0.3.0"))

    def test_tilde(self):
        """Check tilde."""
        self.assertTrue(self.matches("~1.2.3", "1.2.9"))
        self.assertFalse(self.matches("~1.2.3", "1.3.0"))

    def test_wildcard(self):
        """Check wildcard."""
        self.assertTrue(self.matches("1.2.*", "1.2.9"))
        self.assertFalse(self.matches("1.2.*", "1.3.0"))
        self.assertTrue(self.matches("*", "42.0.0"))

    def test_comparison_range(self):
        """Check comparison range."""
        self.assertTrue(self.matches(">=1.0, <2.0", "1.9.9"))
        self.assertFalse(self.matches(">=1.0, <2.0", "2.0.0"))
        self.assertTrue(self.matches(">1.2", "1.3.0"))

    def test_exact(self):
        """Check exact."""
        self.assertTrue(self.matches("=1.2.3", "1.2.3"))
        self.assertFalse(self.matches("=1.2.3", "1.2.4"))

    def test_prerelease_policy(self):
        """Check prerelease policy."""
        self.assertFalse(self.matches("^1.0.0", "1.1.0-rc.1"))
        self.assertTrue(self.matches("^1.0.0-beta", "1.1.0-rc.1"))

    def test_alternatives(self):
        """Check alternatives."""
        requirement = parse_requirement("=1.0.0 || =2.0.0")
        self.assertTrue(requirement.matches(parse_version("2.0.0")))
        self.assertFalse(requirement.matches(parse_version("1.5.0")))

    def test_rejects_bad_requirement(self):
        """Check rejects bad requirement."""
        with self.assertRaises(SemverError):
            parse_requirement("not-a-version")
