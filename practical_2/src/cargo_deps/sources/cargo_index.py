"""Dependency source for the Cargo sparse registry index.

Cargo registries publish one JSON document per crate.  Each line of the
document describes a release and contains its dependency declarations,
so the tool needs one HTTP request per crate and never invokes Cargo or
a third-party package library.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from ..errors import SourceError
from ..models import EDGE_KINDS, NORMAL, Dependency, ResolvedPackage
from ..semver import SemverError, parse_requirement, parse_version
from .base import DependencySource

CRATES_IO_INDEX = "https://index.crates.io/"
CRATES_IO_HOSTS = frozenset({"crates.io", "www.crates.io", "index.crates.io"})
HTTP_TIMEOUT = 15
HTTP_NOT_FOUND = 404
USER_AGENT = "cargo-deps-graph/1.0 (educational dependency visualizer)"
_SHORT_NAME_ONE = 1
_SHORT_NAME_TWO = 2
_SHORT_NAME_THREE = 3


def normalize_index_url(repository: str) -> str:
    """Turn a registry or sparse index URL into an index base URL."""
    cleaned = repository.strip()
    if cleaned.startswith("sparse+"):
        cleaned = cleaned[len("sparse+"):]
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SourceError(
            f"repository must be an HTTP(S) URL, got {repository!r}"
        )
    if parsed.hostname in CRATES_IO_HOSTS:
        return CRATES_IO_INDEX
    if parsed.path.endswith(".git"):
        raise SourceError(
            "a git repository URL is not a Cargo sparse index; "
            "pass https://crates.io or an index base URL"
        )
    return cleaned.rstrip("/") + "/"


def crate_index_path(name: str) -> str:
    """Return the sparse-index path of a crate name."""
    lower = name.lower()
    size = len(lower)
    if size == _SHORT_NAME_ONE:
        return f"1/{lower}"
    if size == _SHORT_NAME_TWO:
        return f"2/{lower}"
    if size == _SHORT_NAME_THREE:
        return f"3/{lower[0]}/{lower}"
    return f"{lower[:2]}/{lower[2:4]}/{lower}"


@dataclass(frozen=True)
class _Release:
    """One release line parsed from a sparse index document."""

    name: str
    version: str
    yanked: bool
    dependencies: tuple[Dependency, ...]


def _parse_dependency(payload: object, context: str) -> Dependency:
    """Parse one dependency entry from an index record."""
    if not isinstance(payload, dict):
        raise SourceError(f"{context}: dependency entry is not an object")
    alias = payload.get("name")
    package = payload.get("package") or alias
    if not isinstance(package, str) or not package:
        raise SourceError(f"{context}: dependency without a package name")
    requirement = payload.get("req")
    if requirement is not None and not isinstance(requirement, str):
        raise SourceError(f"{context}: dependency requirement is not a string")
    kind = payload.get("kind") or NORMAL
    if kind not in EDGE_KINDS:
        kind = NORMAL
    return Dependency(
        name=package,
        requirement=requirement,
        kind=kind,
        optional=bool(payload.get("optional", False)),
        target=payload.get("target"),
        registry=payload.get("registry"),
    )


def _parse_release(payload: object, context: str) -> _Release:
    """Parse one release record from an index document."""
    if not isinstance(payload, dict):
        raise SourceError(f"{context}: release entry is not an object")
    name = payload.get("name")
    version = payload.get("vers")
    if not isinstance(name, str) or not isinstance(version, str):
        raise SourceError(f"{context}: release without name or version")
    raw_dependencies = payload.get("deps", [])
    if not isinstance(raw_dependencies, list):
        raise SourceError(f"{context}: 'deps' is not a list")
    dependencies = tuple(
        _parse_dependency(item, context) for item in raw_dependencies
    )
    return _Release(
        name=name,
        version=version,
        yanked=bool(payload.get("yanked", False)),
        dependencies=dependencies,
    )


def _parse_index(text: str, package: str, url: str) -> list[_Release]:
    """Parse all JSON lines of a sparse index document."""
    releases: list[_Release] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        context = f"{url}:{line_number}"
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SourceError(f"{context}: invalid JSON: {exc}") from exc
        release = _parse_release(payload, context)
        if release.name.lower() != package.lower():
            raise SourceError(
                f"{context}: expected crate {package!r}, "
                f"found {release.name!r}"
            )
        releases.append(release)
    if not releases:
        raise SourceError(f"no releases found for package {package!r}")
    return releases


class CargoIndexSource:
    """Read releases and dependencies from a Cargo sparse index."""

    def __init__(self, repository: str, timeout: int = HTTP_TIMEOUT) -> None:
        """Store the normalized index URL and prepare a request cache."""
        self._base = normalize_index_url(repository)
        self._timeout = timeout
        self._cache: dict[str, list[_Release]] = {}

    def resolve_root(
        self, name: str, version: str | None = None
    ) -> ResolvedPackage:
        """Select an explicit or the newest stable release."""
        releases = [release for release in self._releases(name)
                    if not release.yanked]
        if version is not None:
            return self._explicit_release(name, version, releases)
        if not releases:
            raise SourceError(f"package {name!r} has no usable releases")
        stable = [
            release for release in releases
            if not parse_version(release.version).is_prerelease
        ]
        pool = stable or releases
        best = max(pool, key=lambda item: parse_version(item.version))
        return ResolvedPackage(best.name, best.version)

    def _explicit_release(
        self, name: str, version: str, releases: list[_Release]
    ) -> ResolvedPackage:
        """Select an explicitly requested release by version."""
        for release in releases:
            if release.version == version:
                return ResolvedPackage(release.name, release.version)
        raise SourceError(f"package {name!r} has no release {version!r}")

    def resolve_dependency(self, dep: Dependency) -> ResolvedPackage | None:
        """Resolve a dependency to the newest matching release."""
        if dep.registry is not None:
            return None
        try:
            requirement = parse_requirement(dep.requirement or "*")
        except SemverError as exc:
            raise SourceError(
                f"invalid requirement {dep.requirement!r} for {dep.name!r}: "
                f"{exc}"
            ) from exc
        matches: list[_Release] = []
        for release in self._releases(dep.name):
            if release.yanked:
                continue
            try:
                version = parse_version(release.version)
            except SemverError:
                continue
            if requirement.matches(version):
                matches.append(release)
        if not matches:
            return None
        best = max(matches, key=lambda item: parse_version(item.version))
        return ResolvedPackage(best.name, best.version)

    def dependencies(self, package: ResolvedPackage) -> list[Dependency]:
        """Return direct dependencies of a resolved release."""
        for release in self._releases(package.name):
            if release.version == package.version:
                return list(release.dependencies)
        raise SourceError(
            f"release {package.name} {package.version} is not in the index"
        )

    def _releases(self, name: str) -> list[_Release]:
        """Download and cache all releases of a package."""
        if name in self._cache:
            return self._cache[name]
        url = self._base + crate_index_path(name)
        text = self._download(url, name)
        releases = _parse_index(text, name, url)
        self._cache[name] = releases
        return releases

    def _download(self, url: str, package: str) -> str:
        """Download one index document with friendly error messages."""
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout
            ) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == HTTP_NOT_FOUND:
                raise SourceError(
                    f"package {package!r} was not found at {self._base}"
                ) from exc
            raise SourceError(
                f"registry returned HTTP {exc.code} for {url}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceError(f"cannot download {url}: {exc}") from exc
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceError(f"registry response is not UTF-8: {url}") from exc
