"""Источник данных из sparse-индекса реестра Cargo.

Реестры Cargo публикуют по одному JSON-документу на пакет. Каждая
строка документа описывает релиз и содержит объявления зависимостей,
поэтому инструменту нужен один HTTP-запрос на пакет; Cargo и сторонние
библиотеки для получения зависимостей не вызываются.
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
    """Превращает URL реестра или sparse-индекса в базовый URL индекса."""
    cleaned = repository.strip()
    if cleaned.startswith("sparse+"):
        cleaned = cleaned[len("sparse+"):]
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SourceError(
            f"URL реестра должен быть HTTP(S)-адресом, получено "
            f"{repository!r}"
        )
    if parsed.hostname in CRATES_IO_HOSTS:
        return CRATES_IO_INDEX
    if parsed.path.endswith(".git"):
        raise SourceError(
            "URL git-репозитория не является sparse-индексом Cargo; "
            "укажите https://crates.io или базовый URL индекса"
        )
    return cleaned.rstrip("/") + "/"


def crate_index_path(name: str) -> str:
    """Возвращает путь пакета в sparse-индексе."""
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
class Release:
    """Один релиз, разобранный из документа sparse-индекса."""

    name: str
    version: str
    yanked: bool
    dependencies: tuple[Dependency, ...]


def _parse_dependency(payload: object, context: str) -> Dependency:
    """Разбирает одну запись зависимости из индекса."""
    if not isinstance(payload, dict):
        raise SourceError(
            f"{context}: запись зависимости не является объектом"
        )
    alias = payload.get("name")
    package = payload.get("package") or alias
    if not isinstance(package, str) or not package:
        raise SourceError(f"{context}: у зависимости нет имени пакета")
    requirement = payload.get("req")
    if requirement is not None and not isinstance(requirement, str):
        raise SourceError(
            f"{context}: требование зависимости не является строкой"
        )
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


def _parse_release(payload: object, context: str) -> Release:
    """Разбирает одну запись релиза из документа индекса."""
    if not isinstance(payload, dict):
        raise SourceError(
            f"{context}: запись релиза не является объектом"
        )
    name = payload.get("name")
    version = payload.get("vers")
    if not isinstance(name, str) or not isinstance(version, str):
        raise SourceError(f"{context}: у релиза нет имени или версии")
    raw_dependencies = payload.get("deps", [])
    if not isinstance(raw_dependencies, list):
        raise SourceError(f"{context}: поле 'deps' не является списком")
    dependencies = tuple(
        _parse_dependency(item, context) for item in raw_dependencies
    )
    return Release(
        name=name,
        version=version,
        yanked=bool(payload.get("yanked", False)),
        dependencies=dependencies,
    )


def _parse_index(text: str, package: str, url: str) -> list[Release]:
    """Разбирает все JSON-строки документа sparse-индекса."""
    releases: list[Release] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        context = f"{url}:{line_number}"
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SourceError(
                f"{context}: некорректный JSON: {exc}"
            ) from exc
        release = _parse_release(payload, context)
        if release.name.lower() != package.lower():
            raise SourceError(
                f"{context}: ожидался пакет {package!r}, "
                f"найден {release.name!r}"
            )
        releases.append(release)
    if not releases:
        raise SourceError(f"для пакета {package!r} не найдено релизов")
    return releases


class CargoIndexSource:
    """Читает релизы и зависимости из sparse-индекса Cargo."""

    def __init__(self, repository: str, timeout: int = HTTP_TIMEOUT) -> None:
        """Сохраняет нормализованный URL индекса и создаёт кэш."""
        self._base = normalize_index_url(repository)
        self._timeout = timeout
        self._cache: dict[str, list[Release]] = {}

    def resolve_root(
        self, name: str, version: str | None = None
    ) -> ResolvedPackage:
        """Выбирает явную или самую новую стабильную версию."""
        releases = [release for release in self._releases(name)
                    if not release.yanked]
        if version is not None:
            return self._explicit_release(name, version, releases)
        if not releases:
            raise SourceError(
                f"для пакета {name!r} нет подходящих релизов"
            )
        stable = [
            release for release in releases
            if not parse_version(release.version).is_prerelease
        ]
        pool = stable or releases
        best = max(pool, key=lambda item: parse_version(item.version))
        return ResolvedPackage(best.name, best.version)

    def _explicit_release(
        self, name: str, version: str, releases: list[Release]
    ) -> ResolvedPackage:
        """Выбирает явно указанную версию релиза."""
        for release in releases:
            if release.version == version:
                return ResolvedPackage(release.name, release.version)
        raise SourceError(
            f"у пакета {name!r} нет релиза {version!r}"
        )

    def resolve_dependency(self, dep: Dependency) -> ResolvedPackage | None:
        """Выбирает самую новую версию, подходящую под требование."""
        if dep.registry is not None:
            return None
        try:
            requirement = parse_requirement(dep.requirement or "*")
        except SemverError as exc:
            raise SourceError(
                f"некорректное требование {dep.requirement!r} "
                f"для {dep.name!r}: {exc}"
            ) from exc
        matches: list[Release] = []
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
        """Возвращает прямые зависимости выбранного релиза."""
        for release in self._releases(package.name):
            if release.version == package.version:
                return list(release.dependencies)
        raise SourceError(
            f"релиз {package.name} {package.version} отсутствует в индексе"
        )

    def _releases(self, name: str) -> list[Release]:
        """Скачивает и кэширует все релизы пакета."""
        if name in self._cache:
            return self._cache[name]
        url = self._base + crate_index_path(name)
        text = self._download(url, name)
        releases = _parse_index(text, name, url)
        self._cache[name] = releases
        return releases

    def _download(self, url: str, package: str) -> str:
        """Скачивает документ индекса с понятными сообщениями об ошибках."""
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
                    f"пакет {package!r} не найден по адресу {self._base}"
                ) from exc
            raise SourceError(
                f"реестр вернул HTTP {exc.code} для {url}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceError(
                f"не удалось скачать {url}: {exc}"
            ) from exc
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceError(
                f"ответ реестра не является UTF-8: {url}"
            ) from exc
