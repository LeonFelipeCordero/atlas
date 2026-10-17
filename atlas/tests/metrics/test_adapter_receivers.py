"""Receiver policies reject rebinding, trait methods and non-mutating syntax."""

from types import SimpleNamespace

import pytest

from atlas.domain.models import Inheritance
from atlas.metrics.adapters import javascript, kotlin, python, rust
from atlas.metrics.adapters.script_resolution import (
    inherited_members,
    member_mutation,
    member_write,
)
from tests.metrics.adapter_support import node, parsed, request, symbol, syntax


@pytest.mark.parametrize(
    ("rebound", "descriptor", "expected"),
    [
        (False, None, True),
        (True, None, False),
        (False, "staticmethod", False),
        (False, "classmethod", False),
    ],
)
def test_python_self_call_requires_bound_instance_without_reassignment(
    rebound, descriptor, expected
):
    adapter = python.PythonResolution()
    call = node("call", start=50, end=60)
    assignment = node(
        "assignment",
        start=40,
        end=45,
        left=node(value="self"),
        right=node(value="other"),
    )
    method = node(
        "function_definition",
        start=10,
        end=90,
        parameters=node("parameters", children=[node(value="self: Owner")]),
        body=node("block", children=[call] + ([assignment] if rebound else [])),
    )
    owner = (
        node(
            "decorated_definition",
            children=[node("decorator", "@" + descriptor), method],
        )
        if descriptor
        else method
    )
    node("class_definition", body=node("block", children=[owner]))
    cache = syntax(
        adapter=adapter,
        nodes=[assignment] if rebound else [],
        declarations={(50, 60): call},
    )
    identity = SimpleNamespace(syntax={"src/main.py": cache})
    candidate = symbol()
    assert adapter.select(identity, request(qualifier="self"), [candidate]) == (
        [candidate] if expected else []
    )


@pytest.mark.parametrize(
    ("operator", "expected"), [("++", True), ("--", True), ("!", False), ("-", False)]
)
@pytest.mark.parametrize("kind", ["prefix_expression", "postfix_expression"])
def test_kotlin_only_increment_and_decrement_write_receiver(kind, operator, expected):
    target = node(value="receiver")
    expression = node(kind, children=[node(operator)], operand=target)
    assert kotlin.KotlinResolution().write_target(expression) is (
        target if expected else None
    )


@pytest.mark.parametrize(
    ("trait", "ambiguous", "expected"),
    [
        (False, False, True),
        (True, False, False),
        (False, True, False),
    ],
)
def test_rust_instance_members_include_only_uniquely_owned_inherent_impls(
    trait, ambiguous, expected
):
    adapter = rust.RustResolution()
    parent = symbol("Owner", path="lib.rs", language="rust", kind="struct")
    implementation = symbol(
        "Owner", path="lib.rs", language="rust", kind="impl", start=30, end=90
    )
    method = symbol(
        "run",
        path="lib.rs",
        language="rust",
        parent=implementation.key,
        start=40,
        end=60,
    )
    declaration = node(
        "impl_item",
        type=node("type_identifier", "Owner"),
        **({"trait": node("type_identifier", "Trait")} if trait else {}),
    )
    cache = syntax(adapter=adapter, declarations={(30, 90): declaration})
    types = (
        [parent, symbol("Owner", path="other.rs", kind="struct")]
        if ambiguous
        else [parent]
    )
    resolver = SimpleNamespace(
        symbols={s.key: s for s in [parent, implementation, method]},
        files={"lib.rs": parsed("lib.rs", "rust")},
        syntax={"lib.rs": cache},
        named=lambda request: types,
        lexical=lambda file, name, owner: [],
        imports=SimpleNamespace(get=lambda *args: None),
        _member_declarations=lambda parent, name: [],
    )
    assert adapter.instance_members(resolver, parent, "run") == (
        [method] if expected else []
    )


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("self.run", True),
        (" self . run ", True),
        ("self[dynamic]", True),
        ("self", True),
        ("other.run", False),
        ("self.runner", False),
    ],
)
def test_member_writes_match_receiver_boundaries_and_unknown_computed_names(
    target, expected
):
    assert member_write(target, {"self"}, "run") is expected


@pytest.mark.parametrize(
    ("function", "receiver", "expected"),
    [
        ("Object.assign", "this", True),
        ("Reflect.deleteProperty", "this", True),
        ("setattr", "self", True),
        ("helper", "self", False),
        ("setattr", "other", False),
    ],
)
def test_known_reflective_mutation_requires_receiver_as_first_argument(
    function, receiver, expected
):
    call = node(
        "call",
        function=node(value=function),
        arguments=node("arguments", children=[node(value=receiver)]),
    )
    assert member_mutation(call, {"this", "self"}) is expected


@pytest.fixture
def inheritance_case():
    def build(*, cycle=False, masked=False, multiple=False):
        adapter = javascript.JavaScriptResolution()
        base = symbol("Base", kind="class", start=10, end=40)
        child = symbol("Child", kind="class", start=50, end=90)
        method = symbol("run", parent=base.key, kind="method", start=20, end=30)
        file = parsed(symbols=[base, child, method])
        file.inheritances = [
            Inheritance(child.key, file.source.path, "javascript", "Base", 1, "")
        ]
        if cycle:
            file.inheritances.append(
                Inheritance(base.key, file.source.path, "javascript", "Child", 1, "")
            )
        if multiple:
            file.inheritances.append(
                Inheritance(child.key, file.source.path, "javascript", "Other", 1, "")
            )
        declarations = {
            (50, 90): node(
                "class_declaration",
                superclasses=node("argument_list", children=[node(value="Base")]),
            ),
            (10, 40): node(
                "class_declaration",
                **(
                    {
                        "superclasses": node(
                            "argument_list", children=[node(value="Child")]
                        )
                    }
                    if cycle
                    else {}
                ),
            ),
        }
        cache = syntax(
            adapter=adapter,
            file=file,
            declarations=declarations,
            member_rebound=lambda name, member: masked and name == "Child",
        )
        symbols = [base, child, method]
        resolver = SimpleNamespace(
            syntax={file.source.path: cache},
            files={file.source.path: file},
            symbols={s.key: s for s in symbols},
            named=lambda request: [s for s in [base, child] if s.name == request.name],
            _member_declarations=lambda owner, name: (
                [method] if owner is base and not cycle else []
            ),
        )
        return resolver, child, method

    return build


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, True),
        ({"cycle": True}, False),
        ({"masked": True}, False),
        ({"multiple": True}, False),
    ],
)
def test_script_inheritance_requires_single_unmasked_acyclic_base(
    inheritance_case, options, expected
):
    resolver, child, method = inheritance_case(**options)
    assert inherited_members(resolver, child, "run") == ([method] if expected else [])
