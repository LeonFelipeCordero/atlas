"""Application imports belong to language policies; legacy fallbacks stay stable."""

from functools import cache
from unittest.mock import Mock, patch

import pytest

from atlas.metrics.adapters import get_resolution_adapter
from atlas.metrics.adapters.resolution import ImportBindings, _import_path, _namespace_binding
from atlas.metrics.adapters.resolution_paths import import_path, namespace_binding
from atlas.metrics.adapters.resolution_policy import ResolutionAdapter
from atlas.metrics.resolver import _import_connections
from atlas.metrics.resolution_contract import ImportRequest
from atlas.parsing.parser import parse_files
from tree_sitter_language_pack import get_parser
from tests.coffee_fixture import LANGUAGES, coffee_sources
from tests.variant_snapshot_support import VARIANT_ROOT


@cache
def application(language):
    return parse_files(coffee_sources(language))


@pytest.mark.parametrize("language", LANGUAGES)
def test_primary_import_paths_do_not_use_polyglot_fallback(language):
    repo = application(language)
    imports = [(file, item) for file in repo.files for item in file.imports]
    assert imports
    with patch("atlas.metrics.adapters.resolution_policy.import_path", side_effect=AssertionError):
        for file, item in imports:
            expected = import_path(item.source)
            assert expected
            assert get_resolution_adapter(file.source.language).import_path(item.source) == expected
            assert item.file_path == file.source.path
            text = file.source.source.decode()
            assert item.source.strip() in text
            assert item.source.strip().splitlines()[0] in text.splitlines()[item.line - 1]


@pytest.mark.parametrize("import_case", [
    ("python", "src/coffee/brewing/brewer.py", "from .recipe", ".recipe"),
    ("python", "src/coffee/brewing/brewer.py", "from ..reporting.report", "..reporting.report"),
    ("java", "orders/Scheduling.java", "import static", "coffee.brewing.Recipe.portions"),
    ("java", "orders/Scheduling.java", "java.util.*", "java.util."),
    ("kotlin", "orders/Order.kt", "as renderCoffee", "coffee.reporting.render"),
    ("rust", "main.rs", "mod brewing", "brewing"),
    ("rust", "brewing/scheduling.rs", "recipe::*", "crate::brewing::recipe::"),
    ("rust", "main.rs", "use crate::brewing::brewer;", "crate::brewing::brewer"),
    ("elixir", "brewing/scheduling.ex", "use GenServer", "GenServer"),
    ("elixir", "brewing/scheduling.ex", "require Logger", "Logger"),
    ("elixir", "brewing/scheduling.ex", "alias Coffee", "Coffee.Brewing.Recipe"),
    ("javascript", "ordering/Scheduling.js", "Recipe", "../brewing/Recipe.js"),
    ("javascript", "ordering/Scheduling.jsx", "scheduleDrink", "./Scheduling.js"),
    ("typescript", "ordering/Scheduling.ts", "Recipe", "../brewing/Recipe.ts"),
    ("tsx", "App.tsx", "import * as Cards", "./CoffeeCard"),
])
def test_application_import_paths_are_exact(import_case):
    language, path, needle, expected = import_case
    file = next(file for file in application(language).files if file.source.path == path)
    item, = [item for item in file.imports if needle in item.source]
    assert import_path(item.source) == expected
    with patch("atlas.metrics.adapters.resolution_policy.import_path", side_effect=AssertionError):
        assert get_resolution_adapter(file.source.language).import_path(item.source) == expected


@pytest.mark.parametrize("needle,path,expected", [
    ('"time"', "time", "time"), ('clock "fmt"', "fmt", "clock"),
    ('_ "net/http/pprof"', "net/http/pprof", "_"), ('. "math"', "math", None),
])
def test_go_namespace_rules_do_not_use_polyglot_fallback(needle, path, expected):
    file = next(file for file in application("go").files
                if file.source.path == "brewing/scheduling.go")
    item, = [item for item in file.imports if needle == item.source]
    source = item.source
    assert namespace_binding(source, path) == expected
    ctx = Mock()
    ctx.path_files.return_value = []
    with patch("atlas.metrics.adapters.resolution_policy.namespace_binding", side_effect=AssertionError):
        entries = get_resolution_adapter("go").import_item(ctx, ImportRequest(file, path, source=source))
    assert entries == ([(expected, [], True)] if expected else [])


def assert_legacy_import_fallbacks(file):
    for item in file.imports:
        source = item.source
        assert import_path(source) == _import_path(source) == ResolutionAdapter().import_path(source)
        path = import_path(source)
        assert namespace_binding(source, path) == _namespace_binding(source, path)


@pytest.mark.parametrize("language", LANGUAGES)
def test_legacy_import_path_fallback_and_reexport(language):
    for file in application(language).files:
        assert_legacy_import_fallbacks(file)


@pytest.mark.parametrize("import_case", [
    ("python", "src/coffee/orders/scheduling.py", "from .models", None),
    ("javascript", "ordering/Scheduling.js", "import { Recipe }", None),
    ("javascript", "ordering/Scheduling.jsx", "import scheduleDrink", None),
    ("rust", "brewing/brewer.rs", "as render_order", "render_order"),
    ("tsx", "App.tsx", "import * as Cards", "Cards"),
])
def test_legacy_namespace_fallback_and_reexport(import_case):
    language, path, needle, expected = import_case
    file = next(file for file in application(language).files if file.source.path == path)
    item, = [item for item in file.imports if needle in item.source]
    assert namespace_binding(item.source, import_path(item.source)) == expected
    assert _namespace_binding(item.source, import_path(item.source)) == expected


def test_jsx_alias_import_policy_uses_owned_hook():
    file = next(file for file in application("javascript").files
                if file.source.path == "ordering/Scheduling.jsx")
    item, = file.imports
    with patch("atlas.metrics.adapters.resolution_policy.import_path", side_effect=AssertionError):
        assert get_resolution_adapter("jsx").import_path(item.source) == "./Scheduling.js"


@pytest.mark.parametrize("language,path,expected", [
    ("c", VARIANT_ROOT / "c/legacy-scheduling-include/scheduling.h", "time.h"),
])
def test_legacy_include_paths(language, path, expected):
    source = path.read_text()
    root = get_parser(language).parse(source.encode()).root_node
    assert not root.has_error
    assert import_path(source) == _import_path(source) == expected
    assert ResolutionAdapter().import_path(source) == expected


def test_legacy_unknown_import_path_is_preserved():
    assert ResolutionAdapter().import_path("  malformed scheduling directive  ") == "malformed scheduling directive"


@pytest.fixture
def directive():
    file = next(file for file in application("python").files
                if file.source.path.endswith("/scheduling.py"))
    item, = file.imports
    return file, item


def test_default_import_methods_dispatch_to_adapter_path_hook(directive):
    file, item = directive
    adapter = ResolutionAdapter()
    adapter.import_path = Mock(return_value="owned/path")
    ctx = Mock()
    ctx.path_files.return_value = []
    request = ImportRequest(file, adapter.import_path(item.source), source=item.source)
    assert adapter.import_targets(ctx, request) == [("owned/path", None)]
    adapter.import_path.assert_called_once_with(item.source)
    assert ctx.path_files.call_args.args[1] == "owned/path"


def test_directive_bindings_dispatch_to_adapter_path_hook(directive):
    file, item = directive
    adapter = Mock(require_import_node=False)
    adapter.import_path.return_value = "owned/path"
    adapter.import_item.return_value = []
    syntax = Mock(adapter=adapter)
    syntax.import_node.return_value = None
    syntax.import_scope.return_value = None
    ctx = Mock(syntax={file.source.path: syntax})
    assert ImportBindings._directive_bindings(ctx, file, item, 20) == []
    adapter.import_path.assert_called_once_with(item.source)
    adapter.import_item.assert_called_once_with(ctx, ImportRequest(file, "owned/path", source=item.source))


def test_missing_required_import_node_dispatches_to_adapter_path_hook(directive):
    file, item = directive
    adapter = Mock(require_import_node=True)
    adapter.import_path.return_value = "owned/path"
    adapter.import_targets.return_value = [("ignored", "ignored")]
    adapter.import_type_only.return_value = False
    syntax = Mock()
    syntax.import_node.return_value = None
    resolver = Mock(files={file.source.path: file}, syntax={file.source.path: syntax})
    external = Mock(return_value="external:owned/path")
    with patch("atlas.metrics.resolver.get_resolution_adapter", return_value=adapter):
        connections = _import_connections(item, resolver, external)
    assert adapter.import_path.call_count == 2
    assert all(call.args == (item.source,) for call in adapter.import_path.call_args_list)
    adapter.import_targets.assert_called_once()
    external.assert_called_once_with("python", "module", "owned/path")
    assert len(connections) == 1
    assert connections[0].target_key == "external:owned/path"
