"""Path lookup must not turn duplicates or unrelated packages into targets."""

from types import SimpleNamespace

import pytest

from atlas.domain.models import ParsedRepository
from atlas.metrics.adapters import go, java, javascript, kotlin, python, rust
from atlas.metrics.resolution_contract import ImportRequest
from atlas.metrics.adapters.resolution_paths import (
    import_path,
    namespace_binding,
    package_targets,
    path_target_key,
    relative_targets,
)
from tests.metrics.adapter_support import node, parsed, symbol, syntax


@pytest.fixture
def path_files():
    def build(*paths, language="javascript"):
        return [parsed(path, language) for path in paths]

    return build


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["src/util.js", "src/util/index.js"], ["src/util.js"]),
        (["src/util.js", "src/util.ts", "src/util/index.js"], []),
        (["src/util/index.js", "src/util/helper.js"], ["src/util/index.js"]),
        (["src/util/helper.js"], []),
        ([], []),
    ],
)
def test_relative_script_import_prefers_unique_file_then_index(
    path_files, paths, expected
):
    files = path_files(*paths)
    result = javascript.JavaScriptResolution().paths(parsed(), "./util", files)
    assert [file.source.path for file in result] == expected


def test_relative_directory_policy_can_include_all_files(path_files):
    files = path_files("src/util/one.go", "src/util/two.go", "src/other.go")
    result = relative_targets(ImportRequest(parsed(), "./util"), files)
    assert result == files[:2]


@pytest.mark.parametrize(
    "case",
    [
        ("pkg.util", ["pkg/util.py", "other/pkg/util/x.py"], ["pkg/util.py"]),
        ("pkg::util", ["pkg/util.rs", "pkg/util.py"], []),
        (
            "pkg",
            ["src/pkg/a.go", "src/pkg/b.go", "src/pkgish/c.go", "src/apkg/d.go"],
            ["src/pkg/a.go", "src/pkg/b.go"],
        ),
        ("pkg", ["one/pkg/a.go", "two/pkg/b.go"], []),
        ("missing", ["pkg/a.go"], []),
    ],
)
def test_package_lookup_requires_one_logical_directory(
    path_files, case
):
    name, paths, expected = case
    result = package_targets(name, path_files(*paths))
    assert [file.source.path for file in result] == expected


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ([], None),
        (["pkg/a.go"], "file:pkg/a.go"),
        (["pkg/a.go", "pkg/b.go"], "module:pkg"),
        (["pkg/a.go", "other/b.go"], None),
    ],
)
def test_import_key_represents_only_one_file_or_package(path_files, paths, expected):
    assert path_target_key(path_files(*paths)) == expected


@pytest.mark.parametrize(
    ("source", "path", "expected"),
    [
        ("import * as tools from './tools'", "./tools", "tools"),
        ("import {run} from './tools'", "./tools", None),
        ("from pkg import run", "pkg", None),
        ("import Default from './tools'", "./tools", None),
        (". 'pkg/tools'", "pkg/tools", None),
        ("alias 'pkg/tools'", "pkg/tools", "alias"),
        ("import pkg.tools", "pkg.tools", "tools"),
    ],
)
def test_namespace_binding_excludes_member_and_side_effect_imports(
    source, path, expected
):
    assert namespace_binding(source, path) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("#include <sys/types.h>", "sys/types.h"),
        ("from ..pkg import run", "..pkg"),
        ("import static pkg.Type.run;", "pkg.Type.run"),
        ("use crate::tools;", "crate::tools"),
        ("require('first', 'last')", "last"),
        (" unknown ", "unknown"),
    ],
)
def test_shared_import_path_extracts_language_directives(source, expected):
    assert import_path(source) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (".util", ["src/pkg/util.py"]),
        ("..util", ["src/util.py"]),
        (".", ["src/pkg/__init__.py"]),
        ("missing", []),
    ],
)
def test_python_relative_paths_count_parent_dots(path_files, name, expected):
    files = path_files(
        "src/pkg/util.py", "src/util.py", "src/pkg/__init__.py", language="python"
    )
    result = python.PythonResolution().paths(parsed("src/pkg/main.py"), name, files)
    assert [file.source.path for file in result] == expected


def test_python_module_index_handles_src_layout_and_excludes_stubs(path_files):
    files = path_files(
        "src/pkg/__init__.py", "src/pkg/util.py", "src/pkg/util.pyi", language="python"
    )
    adapter = python.PythonResolution()
    index = adapter.module_index(ParsedRepository(files), {})
    assert index["pkg"] == [files[0]]
    assert index["pkg.util"] == [files[1]]
    assert all(files[2] not in entries for entries in index.values())


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["pkg/__init__.py", "pkg/util.py"], ["pkg/util.py"]),
        (["pkg.py", "pkg/util.py"], []),
        (["pkg/__init__.py", "pkg/util.py", "src/pkg/util.py"], []),
        ([], []),
    ],
)
def test_python_absolute_import_rejects_module_parent_and_duplicate_roots(
    path_files, paths, expected
):
    files = path_files(*paths, language="python")
    index = python.PythonResolution().module_index(ParsedRepository(files), {})
    ctx = SimpleNamespace(modules=SimpleNamespace(indexes={"python": index}))
    result = python.PythonResolution().import_files(
        ctx, ImportRequest(parsed(), "pkg.util")
    )
    assert [file.source.path for file in result] == expected


def test_go_same_package_requires_directory_package_clause_and_type_kind():
    files = [
        parsed(path, "go", symbols=[symbol("Thing", path=path, kind=kind)])
        for path, kind in [
            ("pkg/a.go", "type"),
            ("pkg/b.go", "type"),
            ("pkg/c.go", "function"),
            ("other/d.go", "type"),
            ("pkg/e.go", "type"),
        ]
    ]
    cache = {
        file.source.path: syntax(file=file, nodes=[node("package_clause", package)])
        for file, package in zip(files, ["package pkg"] * 4 + ["package other"])
    }
    result = go.GoResolution().same_package(
        SimpleNamespace(syntax=cache), files[0], "Thing"
    )
    assert result == [files[0].symbols[0], files[1].symbols[0]]


@pytest.mark.parametrize(
    ("adapter", "source", "expected"),
    [
        (java.JavaResolution(), "import static pkg.Type.run;", "pkg.Type.run"),
        (kotlin.KotlinResolution(), "import pkg.Type as Alias", "pkg.Type"),
        (rust.RustResolution(), "use crate::tools as alias;", "crate::tools"),
        (go.GoResolution(), 'alias "example.org/pkg"', "example.org/pkg"),
    ],
)
def test_language_import_paths_do_not_include_alias_or_keywords(
    adapter, source, expected
):
    assert adapter.import_path(source) == expected
