"""Minimal SemVer parsing and Cargo requirement matching.

Only the standard library is used.  The implementation covers the subset
of Cargo requirement syntax that is common in the public registry index:
caret, tilde, comparison and wildcard operators, comma-separated
conjunctions and ``||`` alternatives.  The full Cargo resolver also
considers features, lockfiles and yanked versions; those differences are
explained in ``docs/COMPARISON.md``.
"""

import re
from dataclasses import dataclass

_VERSION_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)
_PARTIAL_RE = re.compile(
    r"^(?P<major>\d+|[*xX])"
    r"(?:\.(?P<minor>\d+|[*xX]))?"
    r"(?:\.(?P<patch>\d+|[*xX]))?"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?$"
)
_COMPARATOR_RE = re.compile(
    r"^(?P<op>\^|~|>=|<=|=|>|<)?\s*(?P<version>.+)$"
)
_WILDCARDS = frozenset({"*", "x", "X"})
_ZERO = 0
_ONE = 1


class SemverError(ValueError):
    """Raised when a version or requirement cannot be parsed."""


def _compare_identifier(left: str, right: str) -> int:
    """Compare two prerelease identifiers."""
    if left == right:
        return _ZERO
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    if left_numeric and right_numeric:
        return -_ONE if int(left) < int(right) else _ONE
    if left_numeric:
        return -_ONE
    if right_numeric:
        return _ONE
    return -_ONE if left < right else _ONE


def _compare_length(left: int, right: int) -> int:
    """Compare prerelease identifier list lengths."""
    if left == right:
        return _ZERO
    return -_ONE if left < right else _ONE


@dataclass(frozen=True)
class Version:
    """A semantic version with prerelease identifiers."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        """Return true for versions such as ``1.0.0-rc.1``."""
        return bool(self.prerelease)

    def _compare_prerelease(self, other: "Version") -> int:
        """Compare prerelease identifiers according to SemVer."""
        if not self.prerelease and not other.prerelease:
            return _ZERO
        if not self.prerelease:
            return _ONE
        if not other.prerelease:
            return -_ONE
        for left, right in zip(self.prerelease, other.prerelease):
            result = _compare_identifier(left, right)
            if result != _ZERO:
                return result
        return _compare_length(
            len(self.prerelease), len(other.prerelease)
        )

    def __lt__(self, other: object) -> bool:
        """Compare versions according to the SemVer precedence rules."""
        if not isinstance(other, Version):
            return NotImplemented
        own_core = (self.major, self.minor, self.patch)
        other_core = (other.major, other.minor, other.patch)
        if own_core != other_core:
            return own_core < other_core
        return self._compare_prerelease(other) < _ZERO

    def __str__(self) -> str:
        """Render the version in canonical ``x.y.z[-pre]`` form."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            return f"{base}-{'.'.join(self.prerelease)}"
        return base


def parse_version(text: str) -> Version:
    """Parse a complete ``major.minor.patch`` version string."""
    match = _VERSION_RE.match(text.strip())
    if match is None:
        raise SemverError(f"invalid semantic version: {text!r}")
    major, minor, patch = (int(match.group(index)) for index in (1, 2, 3))
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    return Version(major, minor, patch, prerelease)


@dataclass(frozen=True)
class _Partial:
    """A version requirement component with optional missing parts."""

    major: int
    minor: int | None = None
    patch: int | None = None
    prerelease: tuple[str, ...] = ()
    wildcard: bool = False

    def lower(self) -> Version:
        """Return the lower bound implied by this partial version."""
        minor = _ZERO if self.minor is None else self.minor
        patch = _ZERO if self.patch is None else self.patch
        return Version(self.major, minor, patch, self.prerelease)


def _parse_partial(text: str) -> _Partial | None:
    """Parse a possibly partial or wildcard version."""
    if text in _WILDCARDS:
        return None
    match = _PARTIAL_RE.match(text)
    if match is None:
        raise SemverError(f"invalid version requirement part: {text!r}")
    values: list[int] = []
    wildcard = False
    for group in ("major", "minor", "patch"):
        raw = match.group(group)
        if raw in _WILDCARDS:
            wildcard = True
            break
        if raw is None:
            break
        values.append(int(raw))
    if not values:
        return None
    prerelease_raw = match.group("pre")
    prerelease = tuple(prerelease_raw.split(".")) if prerelease_raw else ()
    return _Partial(
        values[0],
        values[1] if len(values) > _ONE else None,
        values[2] if len(values) > 2 else None,
        prerelease,
        wildcard,
    )


def _next_major(partial: _Partial) -> Version:
    """Return the first version of the next major series."""
    return Version(partial.major + _ONE, _ZERO, _ZERO)


def _next_minor(partial: _Partial) -> Version:
    """Return the first version of the next minor series."""
    minor = _ZERO if partial.minor is None else partial.minor
    return Version(partial.major, minor + _ONE, _ZERO)


def _next_patch(partial: _Partial) -> Version:
    """Return the next patch release after a partial version."""
    minor = _ZERO if partial.minor is None else partial.minor
    patch = _ZERO if partial.patch is None else partial.patch
    return Version(partial.major, minor, patch + _ONE)


def _caret_upper(partial: _Partial) -> Version:
    """Return the exclusive upper bound of a caret requirement."""
    if partial.minor is None:
        if partial.major > _ZERO:
            return _next_major(partial)
        return Version(_ONE, _ZERO, _ZERO)
    if partial.patch is None:
        if partial.major > _ZERO:
            return _next_major(partial)
        return _next_minor(partial)
    if partial.major > _ZERO:
        return _next_major(partial)
    if partial.minor > _ZERO:
        return _next_minor(partial)
    return _next_patch(partial)


def _tilde_upper(partial: _Partial) -> Version:
    """Return the exclusive upper bound of a tilde requirement."""
    if partial.minor is None:
        return _next_major(partial)
    return _next_minor(partial)


def _eq_upper(partial: _Partial) -> Version | None:
    """Return the upper bound of an equality or wildcard requirement."""
    if partial.patch is not None:
        return None
    if partial.minor is not None:
        return _next_minor(partial)
    return _next_major(partial)


@dataclass(frozen=True)
class _Bounds:
    """Inclusive and exclusive bounds of one requirement comparator."""

    lower: Version | None = None
    lower_inclusive: bool = True
    upper: Version | None = None
    upper_inclusive: bool = False

    def matches(self, version: Version) -> bool:
        """Check whether the version lies inside these bounds."""
        if self.lower is not None:
            if version < self.lower:
                return False
            if version == self.lower and not self.lower_inclusive:
                return False
        if self.upper is not None:
            if self.upper < version:
                return False
            if version == self.upper and not self.upper_inclusive:
                return False
        return True


def _caret_bounds(partial: _Partial) -> _Bounds:
    """Build bounds for a caret requirement."""
    return _Bounds(
        partial.lower(), True, _caret_upper(partial), False
    )


def _tilde_bounds(partial: _Partial) -> _Bounds:
    """Build bounds for a tilde requirement."""
    return _Bounds(
        partial.lower(), True, _tilde_upper(partial), False
    )


def _equality_bounds(partial: _Partial) -> _Bounds:
    """Build bounds for an equality or explicit wildcard requirement."""
    upper = _eq_upper(partial)
    if upper is None:
        return _Bounds(partial.lower(), True, partial.lower(), True)
    return _Bounds(partial.lower(), True, upper, False)


def _greater_equal_bounds(partial: _Partial) -> _Bounds:
    """Build bounds for the ``>=`` operator."""
    return _Bounds(partial.lower(), True)


def _greater_bounds(partial: _Partial) -> _Bounds:
    """Build bounds for the ``>`` operator."""
    if partial.patch is not None:
        return _Bounds(partial.lower(), False)
    return _Bounds(_eq_upper(partial), True)


def _less_bounds(partial: _Partial) -> _Bounds:
    """Build bounds for the ``<`` operator."""
    return _Bounds(upper=partial.lower())


def _less_equal_bounds(partial: _Partial) -> _Bounds:
    """Build bounds for the ``<=`` operator."""
    upper = _eq_upper(partial)
    if upper is None:
        return _Bounds(upper=partial.lower(), upper_inclusive=True)
    return _Bounds(upper=upper)


_BOUND_BUILDERS = {
    "^": _caret_bounds,
    "~": _tilde_bounds,
    "=": _equality_bounds,
    "": _equality_bounds,
    ">=": _greater_equal_bounds,
    ">": _greater_bounds,
    "<": _less_bounds,
    "<=": _less_equal_bounds,
}


def _comparator_bounds(op: str, partial: _Partial | None) -> _Bounds:
    """Expand one requirement comparator into concrete bounds."""
    if partial is None:
        if op not in {"^", "~", "=", ">=", "<="}:
            raise SemverError("wildcard cannot be used with a strict operator")
        return _Bounds()
    if partial.wildcard:
        return _equality_bounds(partial)
    builder = _BOUND_BUILDERS.get(op)
    if builder is None:
        raise SemverError(f"unsupported requirement operator: {op!r}")
    return builder(partial)


def _split_alternatives(text: str) -> list[str]:
    """Split a requirement on ``||`` and drop empty alternatives."""
    return [part for part in text.split("||") if part.strip()]


@dataclass(frozen=True)
class Requirement:
    """A parsed Cargo version requirement."""

    alternatives: tuple[tuple[_Bounds, ...], ...]
    allow_prerelease: bool = False

    def matches(self, version: Version) -> bool:
        """Return true when the version satisfies any alternative."""
        if version.is_prerelease and not self.allow_prerelease:
            return False
        return any(
            all(bound.matches(version) for bound in alternative)
            for alternative in self.alternatives
        )


def parse_requirement(text: str) -> Requirement:
    """Parse a Cargo requirement into a matcher object."""
    stripped = text.strip()
    if not stripped:
        raise SemverError("empty version requirement")
    alternatives: list[tuple[_Bounds, ...]] = []
    allow_prerelease = False
    for part in _split_alternatives(stripped):
        bounds: list[_Bounds] = []
        for token in part.split(","):
            token = token.strip()
            if not token:
                continue
            match = _COMPARATOR_RE.match(token)
            if match is None:
                raise SemverError(f"invalid requirement: {token!r}")
            op = match.group("op") or "^"
            partial = _parse_partial(match.group("version").strip())
            if partial is not None and partial.prerelease:
                allow_prerelease = True
            bounds.append(_comparator_bounds(op, partial))
        if not bounds:
            raise SemverError(f"invalid requirement: {text!r}")
        alternatives.append(tuple(bounds))
    return Requirement(tuple(alternatives), allow_prerelease)
