"""Script class masks, namespace exports, and receiver mutation closure."""

from types import SimpleNamespace

import pytest

from atlas.metrics.adapters.javascript import JavaScriptResolution
from atlas.metrics.resolution_contract import ImportRequest
from tests.metrics.adapter_support import node, parsed, symbol, syntax


@pytest.mark.parametrize(
    "kind",
    [
        "field_definition",
        "computed",
        "getter",
        "signature",
        "implemented_signature",
        "other",
        "unnamed",
    ],
)
def test_script_own_noncallable_member_masks_method(kind):
    parent = symbol("Owner", kind="class")
    target = (
        node("computed_property_name", "[key]")
        if kind == "computed"
        else node(value="other" if kind == "other" else "run")
    )
    entry = node(
        "method_signature"
        if "signature" in kind
        else "method_definition"
        if kind == "getter"
        else "field_definition",
        **({} if kind == "unnamed" else {"name": target}),
        children=[node("get")] if kind == "getter" else [],
    )
    entries = [entry]
    if kind == "implemented_signature":
        entries.append(
            node(
                "method_definition",
                name=node(value="run"),
                body=node("statement_block"),
            )
        )
    declaration = node("class_declaration", body=node("class_body", children=entries))
    state = syntax(adapter=JavaScriptResolution(), declarations={(10, 20): declaration})
    assert state.adapter.member_overwritten(state, parent, "run") is (
        kind not in {"implemented_signature", "other", "unnamed"}
    )


@pytest.mark.parametrize(
    "target",
    [
        "Owner.prototype.run",
        "Owner.prototype[unknown]",
        "Owner.prototype.other",
        "other.run",
    ],
)
@pytest.mark.parametrize("reflective", [True, False])
def test_script_prototype_writes_require_matching_receiver_and_member(
    target, reflective
):
    parent = symbol("Owner", kind="class")
    mutation = (
        node(
            "call_expression",
            function=node(value="Object.assign"),
            arguments=node(
                "arguments",
                children=[
                    node(
                        value="Owner.prototype"
                        if target.startswith("Owner.prototype")
                        else "other"
                    )
                ],
            ),
        )
        if reflective
        else node("assignment_expression", left=node(value=target))
    )
    state = syntax(
        adapter=JavaScriptResolution(),
        nodes=[mutation],
        declarations={(10, 20): node("class_declaration")},
    )
    expected = (
        target.startswith("Owner.prototype")
        if reflective
        else target in {"Owner.prototype.run", "Owner.prototype[unknown]"}
    )
    assert state.adapter.member_overwritten(state, parent, "run") is expected


@pytest.mark.parametrize(
    "source",
    ["import * as tools from './tools'", "import type * as tools from './tools'"],
)
def test_script_namespace_import_retains_export_alias_map_not_private_names(source):
    exported = symbol("internal", path="src/tools.js")
    private = symbol("private", path="src/tools.js", start=30, end=40)
    target = parsed("src/tools.js", "javascript", symbols=[exported, private])
    specifier = node(
        "export_specifier", name=node(value="internal"), alias=node(value="public")
    )
    type_specifier = node(
        "export_specifier", "type private", name=node(value="private")
    )
    export = node(
        "export_statement",
        children=[node("export_clause", children=[specifier, type_specifier])],
    )
    ctx = SimpleNamespace(
        files=lambda file, path: [target],
        syntax={target.source.path: syntax(nodes=[export])},
    )
    query = ImportRequest(parsed(), "./tools", source=source)
    adapter = JavaScriptResolution()
    entries = adapter.import_item(ctx, query)
    assert entries == [("tools", [] if "import type" in source else [exported], True)]
    assert adapter.namespace_members(ctx, query, entries[0][1]) == (
        {} if "import type" in source else {"public": [exported]}
    )


@pytest.mark.parametrize("target_count", [0, 1, 2])
def test_script_member_lookup_requires_exactly_one_export_file(target_count):
    exported = symbol("run")
    file = parsed(symbols=[exported])
    export = node("export_statement", "export run", declaration=node(value="run"))
    ctx = SimpleNamespace(
        path_files=lambda file, path: [file] * target_count,
        syntax={file.source.path: syntax(nodes=[export])},
    )
    assert JavaScriptResolution().members(ctx, ImportRequest(file, "pkg"), "run") == (
        [exported] if target_count == 1 else []
    )
