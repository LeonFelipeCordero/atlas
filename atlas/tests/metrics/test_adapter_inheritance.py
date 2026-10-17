"""Inheritance rejects masks, receiver aliases, and unproven base expressions."""

from types import SimpleNamespace

import pytest

from atlas.domain.models import Inheritance
from atlas.metrics.adapters import javascript, python
from atlas.metrics.adapters.script_resolution import inherited_members
from tests.metrics.adapter_support import node, parsed, symbol, syntax


def base_syntax(language, mutation, field_kind):
    receiver = "me" if language == "python" else "this"
    statements = [
        node(
            "assignment",
            left=node(value="second"),
            right=node(value="first"),
            start=12,
            end=15,
        ),
        node(
            "assignment",
            left=node(value="first"),
            right=node(value=receiver),
            start=16,
            end=19,
        ),
    ]
    assignment = "assignment" if language == "python" else "assignment_expression"
    if mutation in {"alias", "receiver", "unrelated"}:
        target = {
            "alias": "second.run",
            "receiver": receiver,
            "unrelated": "other.run",
        }[mutation]
        statements.append(node(assignment, left=node(value=target), start=20, end=25))
    elif mutation == "reflective":
        statements.append(
            node(
                "call",
                function=node(value="setattr"),
                arguments=node("arguments", children=[node(value=receiver)]),
                start=20,
                end=25,
            )
        )
    constructor = node(
        "function_definition" if language == "python" else "method_definition",
        parameters=node("parameters", children=[node(value="me: Base")]),
        body=node("block", children=statements, start=11, end=39),
        start=10,
        end=40,
    )
    fields = []
    if field_kind:
        target = (
            node("computed_property_name", "[dynamic]")
            if field_kind == "computed"
            else node(value="run")
        )
        fields = [
            node(
                "field_definition",
                name=target,
                children=[node("static")] if field_kind == "static" else [],
            )
        ]
    declaration = node(
        "class_definition" if language == "python" else "class_declaration",
        start=0,
        end=80,
        body=node("block", children=[constructor, *fields], start=1, end=79),
    )
    return statements, declaration


@pytest.fixture
def hierarchy():
    def build(
        *,
        language="javascript",
        mutation="none",
        own=False,
        field_kind=None,
        base_shape="plain",
    ):
        adapter = (
            python.PythonResolution()
            if language == "python"
            else javascript.JavaScriptResolution()
        )
        base = symbol("Base", kind="class", start=0, end=80)
        child = symbol("Child", kind="class", start=100, end=190)
        method = symbol(
            "run",
            parent=child.key if own else base.key,
            kind="method",
            start=150 if own else 50,
            end=160 if own else 60,
        )
        file = parsed(language=language, symbols=[base, child, method])
        file.inheritances = [
            Inheritance(child.key, file.source.path, language, "Base", 1, "")
        ]
        statements, base_node = base_syntax(language, mutation, field_kind)
        base_value = node(value="makeBase()" if base_shape == "dynamic" else "Base")
        if base_shape == "dynamic":
            file.inheritances[0].target_name = "makeBase()"
        child_node = node(
            "class_definition" if language == "python" else "class_declaration",
            start=100,
            end=190,
            body=node("block"),
            **(
                {"superclasses": node("argument_list", children=[base_value])}
                if base_shape != "heritage"
                else {}
            ),
        )
        if base_shape == "heritage":
            clause = node("extends_clause", children=[base_value])
            clause.child_by_field_name = lambda name: (
                base_value if name == "value" else None
            )
            child_node.named_children.append(node("class_heritage", children=[clause]))
        if mutation == "decorated":
            node("decorated_definition", children=[base_node])
        if mutation == "noncallable":
            file.symbols.append(
                symbol("run", parent=child.key, kind="field", start=170, end=175)
            )
        state = syntax(
            adapter=adapter,
            file=file,
            nodes=statements,
            declarations={(0, 80): base_node, (100, 190): child_node},
        )
        resolver = SimpleNamespace(
            syntax={file.source.path: state},
            files={file.source.path: file},
            symbols={s.key: s for s in file.symbols},
            named=lambda request: [base],
            _member_declarations=lambda parent, name: (
                [method] if parent.key == method.parent_key else []
            ),
        )
        return resolver, child, method, state

    return build


@pytest.mark.parametrize("language", ["python", "javascript"])
@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "alias",
        "receiver",
        "reflective",
        "unrelated",
        "decorated",
        "noncallable",
    ],
)
@pytest.mark.parametrize("own", [True, False])
def test_inherited_method_masks_respect_instance_aliases_and_base_writes(
    hierarchy, language, mutation, own
):
    resolver, child, method, _ = hierarchy(
        language=language, mutation=mutation, own=own
    )
    result = inherited_members(resolver, child, "run")
    allowed = mutation in {"none", "receiver", "unrelated"} or (
        own and mutation == "noncallable"
    )
    assert result == ([method] if allowed else [])


@pytest.mark.parametrize("field_kind", ["named", "computed", "static"])
def test_base_instance_fields_mask_even_child_method_implementations(
    hierarchy, field_kind
):
    resolver, child, method, _ = hierarchy(own=True, field_kind=field_kind)
    assert inherited_members(resolver, child, "run") == (
        [method] if field_kind == "static" else []
    )


@pytest.mark.parametrize("base_shape", ["plain", "dynamic", "heritage"])
def test_only_plain_single_base_expressions_support_inheritance(hierarchy, base_shape):
    resolver, child, method, _ = hierarchy(base_shape=base_shape)
    assert inherited_members(resolver, child, "run") == (
        [] if base_shape == "dynamic" else [method]
    )


def test_receiver_scope_cache_preserves_method_local_aliases(hierarchy):
    resolver, child, method, state = hierarchy(language="python", mutation="alias")
    assert inherited_members(resolver, child, "run") == []
    # A second resolution must reuse the populated immutable-syntax scope cache.
    state.nodes = []
    assert inherited_members(resolver, child, "run") == []
