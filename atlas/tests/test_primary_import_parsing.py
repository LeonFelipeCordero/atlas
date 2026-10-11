"""Primary import syntax belongs to language policies; legacy fallbacks stay stable."""

from tests.source_snapshot_fixture import case_text

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
        ("python", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-python', 'sample.py'), "pkg.tools"),
        ("python", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-python-2', 'sample.py'), "..pkg.tools"),
        ("java", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-java', 'sample.java'), "pkg.Tools.run"),
        ("java", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-java-2', 'sample.java'), "pkg.tools."),
        ("kotlin", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-kotlin', 'sample.kt'), "pkg.Tools"),
        ("go", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-go', 'sample.go'), "example.org/pkg/tools"),
        ("go", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-go-2', 'sample.go'), "example.org/pkg/tools"),
        ("go", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-go-3', 'sample.go'), "example.org/pkg/tools"),
        ("rust", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-rust', 'sample.rs'), "crate::tools::run"),
        ("rust", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-rust-2', 'sample.rs'), "crate::tools::"),
        ("rust", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-rust-3', 'sample.rs'), "tools"),
        ("elixir", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-elixir', 'sample.ex'), "Project.Tools"),
        ("elixir", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-elixir-2', 'sample.ex'), "Project.Tools"),
        ("elixir", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-elixir-3', 'sample.ex'), "Project.Tools"),
        ("javascript", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-javascript', 'sample.js'), "./tools"),
        ("jsx", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-jsx', 'sample.jsx'), "./tools"),
        ("typescript", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-typescript', 'sample.ts'), "./tools"),
        ("tsx", case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-tsx', 'sample.tsx'), "./tools"),
    ],
)
def test_primary_import_paths_do_not_use_polyglot_fallback(language, source, expected):
    assert import_path(source) == expected
    with patch("atlas.metrics.adapters.resolution_policy.import_path", side_effect=AssertionError):
        assert get_resolution_adapter(language).import_path(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (case_text('parsing', 'primary_import_parsing-go_namespace_rules_do_not_use_polyglot_fallback-python', 'sample.py'), "tools"),
        (case_text('parsing', 'primary_import_parsing-go_namespace_rules_do_not_use_polyglot_fallback-python-2', 'sample.py'), "tools"),
        (case_text('parsing', 'primary_import_parsing-go_namespace_rules_do_not_use_polyglot_fallback-python-3', 'sample.py'), "helpers"),
        (case_text('parsing', 'primary_import_parsing-go_namespace_rules_do_not_use_polyglot_fallback-python-4', 'sample.py'), "tools"),
        (case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-go-2', 'sample.go'), "_"),
        (case_text('parsing', 'primary_import_parsing-primary_import_paths_do_not_use_polyglot_fallback-go-3', 'sample.go'), None),
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
        (case_text('parsing', 'primary_import_parsing-legacy_import_path_fallback_and_reexport-python', 'sample.py'), "tools/header.h"),
        (case_text('parsing', 'primary_import_parsing-legacy_import_path_fallback_and_reexport-python-2', 'sample.py'), "tools"),
        (case_text('parsing', 'primary_import_parsing-legacy_import_path_fallback_and_reexport-python-3', 'sample.py'), "Tools::run"),
        (case_text('parsing', 'primary_import_parsing-legacy_import_path_fallback_and_reexport-python-4', 'sample.py'), "Tools.Run"),
        (case_text('parsing', 'primary_import_parsing-legacy_import_path_fallback_and_reexport-python-5', 'sample.py'), "tools"),
        (case_text('parsing', 'primary_import_parsing-legacy_import_path_fallback_and_reexport-python-6', 'sample.py'), "unknown syntax"),
    ],
)
def test_legacy_import_path_fallback_and_reexport(source, expected):
    assert import_path(source) == _import_path(source) == expected
    assert ResolutionAdapter().import_path(source) == expected


@pytest.mark.parametrize(
    ("source", "path", "expected"),
    [
        (case_text('parsing', 'primary_import_parsing-legacy_import_path_fallback_and_reexport-python-5', 'sample.py'), "tools", None),
        (case_text('parsing', 'primary_import_parsing-legacy_namespace_fallback_and_reexport-python', 'sample.py'), "tools", None),
        (case_text('parsing', 'primary_import_parsing-legacy_namespace_fallback_and_reexport-python-2', 'sample.py'), "pkg", None),
        (case_text('parsing', 'primary_import_parsing-legacy_namespace_fallback_and_reexport-python-3', 'sample.py'), "tools", "Helpers"),
        (case_text('parsing', 'primary_import_parsing-legacy_namespace_fallback_and_reexport-python-4', 'sample.py'), "pkg/tools", "tools"),
    ],
)
def test_legacy_namespace_fallback_and_reexport(source, path, expected):
    assert namespace_binding(source, path) == _namespace_binding(source, path) == expected


def test_default_import_methods_dispatch_to_adapter_path_hook():
    source = case_text('parsing', 'primary-import-hook-directive', 'directive.txt')
    adapter = ResolutionAdapter()
    adapter.import_path = Mock(return_value="owned/path")
    ctx = Mock()
    ctx.path_files.return_value = []
    request = ImportRequest(Mock(), adapter.import_path(source), source=source)
    assert adapter.import_targets(ctx, request) == [("owned/path", None)]
    adapter.import_path.assert_called_once_with(source)
    assert ctx.path_files.call_args.args[1] == "owned/path"


def test_directive_bindings_dispatch_to_adapter_path_hook():
    source = case_text('parsing', 'primary-import-hook-directive', 'directive.txt')
    adapter = Mock(require_import_node=False)
    adapter.import_path.return_value = "owned/path"
    adapter.import_item.return_value = []
    syntax = Mock(adapter=adapter)
    syntax.import_node.return_value = None
    syntax.import_scope.return_value = None
    ctx = Mock(syntax={"source": syntax})
    file = Mock()
    file.source.path = "source"
    item = Import("source", source, 1)
    assert ImportBindings._directive_bindings(ctx, file, item, 20) == []
    adapter.import_path.assert_called_once_with(source)
    adapter.import_item.assert_called_once_with(ctx, ImportRequest(file, "owned/path", source=source))


def test_missing_required_import_node_dispatches_to_adapter_path_hook():
    source = case_text('parsing', 'primary-import-hook-directive', 'directive.txt')
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
        connections = _import_connections(Import("source", source, 1), resolver, external)
    external.assert_called_once_with("rust", "module", "owned/path")
    assert connections[0].target_key == "external:owned/path"
