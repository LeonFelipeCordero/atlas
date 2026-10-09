"""Shared conservative path and namespace matching, without syntax-cache imports."""

import re
from pathlib import PurePosixPath

from ...domain.models import ParsedFile, Symbol, file_key


def top_symbols(file: ParsedFile) -> list[Symbol]:
    return [s for s in file.symbols if s.parent_key == file_key(file.source.path)]


def quoted_path(source: str) -> str | None:
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", source)
    return quoted[-1] if quoted else None


def import_path(source: str) -> str:
    include = re.search(r'#\s*include\s*[<"]([^>"]+)[>"]', source)
    if include:
        return include[1]
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", source)
    if quoted:
        return quoted[-1]
    match = re.search(
        r"\bfrom\s+([\w.]+)|\b(?:import\s+(?:static\s+)?|(?:use|alias|require|mod)\s+)([\w.:/]+)",
        source,
    )
    return (
        next((part for part in match.groups() if part), "") if match else source.strip()
    )


def _relative_match(file: ParsedFile, base) -> bool:
    path = file.source.absolute_path.resolve()
    return path == base or path.with_suffix("") == base


def relative_targets(
    source: ParsedFile, name: str, files: list[ParsedFile], index_only: bool = False
) -> list[ParsedFile]:
    base = (source.source.absolute_path.parent / name).resolve()
    matches = [file for file in files if _relative_match(file, base)]
    if matches:
        return matches if len(matches) == 1 else []
    return _relative_directory(base, files, index_only)


def _relative_directory(
    base, files: list[ParsedFile], index_only: bool
) -> list[ParsedFile]:
    directory = [
        file for file in files if file.source.absolute_path.resolve().parent == base
    ]
    return (
        [file for file in directory if file.source.absolute_path.stem == "index"]
        if index_only
        else directory
    )


def _package_match(file: ParsedFile, path: str) -> bool:
    return (
        str(PurePosixPath(file.source.path).with_suffix("")) == path
        or file.source.path == path
    )


def _package_directory(file: ParsedFile) -> str:
    return str(PurePosixPath(file.source.path).parent)


def _package_directories(path: str, files: list[ParsedFile]) -> set[str]:
    parents = {_package_directory(file) for file in files}
    return {
        parent for parent in parents if parent == path or parent.endswith("/" + path)
    }


def _package_path(name: str) -> str:
    path = name.replace("::", "/")
    return (path if "/" in path else path.replace(".", "/")).strip("/")


def package_targets(name: str, files: list[ParsedFile]) -> list[ParsedFile]:
    path = _package_path(name)
    exact = [file for file in files if _package_match(file, path)]
    if exact:
        return exact if len(exact) == 1 else []
    directories = _package_directories(path, files)
    if len(directories) != 1:
        return []
    return [file for file in files if _package_directory(file) in directories]


def path_target_key(files: list[ParsedFile]) -> str | None:
    if len(files) == 1:
        return file_key(files[0].source.path)
    parents = {_package_directory(file) for file in files}
    return "module:" + parents.pop() if len(parents) == 1 else None


def namespace_binding(source: str, path: str) -> str | None:
    if "{" in source or re.match(r"\s*from\b", source):
        return None
    alias = re.search(r"\bas\s+([A-Za-z_$][\w$]*)", source)
    if alias:
        return alias[1]
    prefix = re.match(r"\s*([A-Za-z_$][\w$]*)\s+['\"]", source)
    if prefix and prefix[1] not in {"import", "require"}:
        return prefix[1]
    if re.match(r"\s*(?:_|\.)\s+['\"]", source):
        return None
    if re.match(r"\s*import\s+\w+\s+from\b", source):
        return None
    return path.replace("::", "/").replace(".", "/").rstrip("/").rsplit("/", 1)[-1]
