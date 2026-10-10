"""Primary import syntax belongs to language policies; legacy fallbacks stay stable."""

from unittest.mock import Mock, patch

import pytest

from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.adapters.resolution import ImportBindings, _import_path, _namespace_binding
from atlas.metrics.adapters.resolution_paths import import_path, namespace_binding
from atlas.metrics.adapters.resolution_policy import ResolutionAdapter
from atlas.domain.models import Import
from atlas.metrics.resolver import _import_connections
from atlas.metrics.resolution_contract import ImportRequest


@pytest.mark.parametrize(
    ("language", "source", "expected"),
    [
        ("python", "import pkg.tools as tools", "pkg.tools"),
        ("python", "from ..pkg.tools import run as execute", "..pkg.tools"),
        ("java", "import static pkg.Tools.run;", "pkg.Tools.run"),
        ("java", "import pkg.tools.*;", "pkg.tools."),
        ("kotlin", "import pkg.Tools as Helpers", "pkg.Tools"),
        ("go", 'tools "example.org/pkg/tools"', "example.org/pkg/tools"),
        ("go", '_ "example.org/pkg/tools"', "example.org/pkg/tools"),
        ("go", '. "example.org/pkg/tools"', "example.org/pkg/tools"),
        ("rust", "pub use crate::tools::run as execute;", "crate::tools::run"),
        ("rust", "use crate::tools::{run, stop};", "crate::tools::"),
        ("rust", "mod tools;", "tools"),
        ("elixir", "alias Project.Tools, as: Helpers", "Project.Tools"),
        ("elixir", "require Project.Tools", "Project.Tools"),
        ("elixir", "import Project.Tools", "Project.Tools"),
        ("javascript", "import {run as execute} from './tools';", "./tools"),
        ("jsx", "import * as Tools from './tools';", "./tools"),
        ("typescript", "import type {Tools} from './tools';", "./tools"),
        ("tsx", "import type * as Tools from './tools';", "./tools"),
    ],
)
def test_primary_import_paths_do_not_use_polyglot_fallback(language, source, expected):
    assert import_path(source) == expected
    with patch("atlas.metrics.adapters.resolution_policy.import_path", side_effect=AssertionError):
        assert get_resolution_adapter(language).import_path(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('"example.org/pkg/tools"', "tools"),
        ('import "example.org/pkg/tools"', "tools"),
        ('helpers "example.org/pkg/tools"', "helpers"),
        ('require "example.org/pkg/tools"', "tools"),
        ('_ "example.org/pkg/tools"', "_"),
        ('. "example.org/pkg/tools"', None),
    ],
)
def test_go_namespace_rules_do_not_use_polyglot_fallback(source, expected):
    path = "example.org/pkg/tools"
    assert namespace_binding(source, path) == expected
    ctx = Mock()
    ctx.path_files.return_value = []
    with patch("atlas.metrics.adapters.resolution_policy.namespace_binding", side_effect=AssertionError):
        entries = get_resolution_adapter("go").import_item(ctx, ImportRequest(Mock(), path, source=source))
    assert entries == ([(expected, [], True)] if expected else [])


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('#include <tools/header.h>', "tools/header.h"),
        ('require "tools"', "tools"),
        ("use Tools::run;", "Tools::run"),
        ("alias Tools.Run", "Tools.Run"),
        ("from tools import run", "tools"),
        ("  unknown syntax  ", "unknown syntax"),
    ],
)
def test_legacy_import_path_fallback_and_reexport(source, expected):
    assert import_path(source) == _import_path(source) == expected
    assert ResolutionAdapter().import_path(source) == expected


@pytest.mark.parametrize(
    ("source", "path", "expected"),
    [
        ("from tools import run", "tools", None),
        ("import {run} from 'tools'", "tools", None),
        ("import tools from 'pkg'", "pkg", None),
        ("use tools as Helpers", "tools", "Helpers"),
        ("require 'pkg/tools'", "pkg/tools", "tools"),
    ],
)
def test_legacy_namespace_fallback_and_reexport(source, path, expected):
    assert namespace_binding(source, path) == _namespace_binding(source, path) == expected


def test_default_import_methods_dispatch_to_adapter_path_hook():
    adapter = ResolutionAdapter()
    adapter.import_path = Mock(return_value="owned/path")
    ctx = Mock()
    ctx.path_files.return_value = []
    request = ImportRequest(Mock(), adapter.import_path("directive"), source="directive")
    assert adapter.import_targets(ctx, request) == [("owned/path", None)]
    adapter.import_path.assert_called_once_with("directive")
    assert ctx.path_files.call_args.args[1] == "owned/path"


def test_directive_bindings_dispatch_to_adapter_path_hook():
    adapter = Mock(require_import_node=False)
    adapter.import_path.return_value = "owned/path"
    adapter.import_item.return_value = []
    syntax = Mock(adapter=adapter)
    syntax.import_node.return_value = None
    syntax.import_scope.return_value = None
    ctx = Mock(syntax={"source": syntax})
    file = Mock()
    file.source.path = "source"
    item = Import("source", "directive", 1)
    assert ImportBindings._directive_bindings(ctx, file, item, 20) == []
    adapter.import_path.assert_called_once_with("directive")
    adapter.import_item.assert_called_once_with(ctx, ImportRequest(file, "owned/path", source="directive"))


def test_missing_required_import_node_dispatches_to_adapter_path_hook():
    adapter = Mock(require_import_node=True)
    adapter.import_path.return_value = "owned/path"
    adapter.import_targets.return_value = [("ignored", "ignored")]
    adapter.import_type_only.return_value = False
    syntax = Mock()
    syntax.import_node.return_value = None
    file = Mock()
    file.source.language = "rust"
    resolver = Mock(files={"source": file}, syntax={"source": syntax})
    external = Mock(return_value="external:owned/path")
    with patch("atlas.metrics.resolver.get_resolution_adapter", return_value=adapter):
        connections = _import_connections(Import("source", "directive", 1), resolver, external)
    external.assert_called_once_with("rust", "module", "owned/path")
    assert connections[0].target_key == "external:owned/path"
