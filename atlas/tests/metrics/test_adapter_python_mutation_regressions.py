"""Python adapter regressions for mutation survivors and lexical binding bugs."""

from pathlib import PurePosixPath
from types import SimpleNamespace

import pytest

from atlas.metrics.adapters import python
from atlas.metrics.adapters.script_python_selection import bound_self, typing_overload
from atlas.metrics.resolution_syntax import Syntax
from atlas.syntax import field, text
from tests.metrics.adapter_support import node, parsed, request, symbol, syntax


def python_syntax(source):
    file = parsed("example.py")
    file.source.source = source.encode()
    return Syntax(file, python.PythonResolution())


def method_selection(state, name="run"):
    method = next(n for n in state.nodes if n.type == "function_definition"
                  and text(field(n, "name")) == name)
    candidate = symbol(name, path=state.file.source.path,
                       start=method.start_byte, end=method.end_byte)
    call = next(n for n in state.nodes if n.type == "call")
    identity = SimpleNamespace(syntax={state.file.source.path: state})
    return state.adapter.select(identity, request(state.file, qualifier="self",
                                start=call.start_byte, end=call.end_byte), [candidate])


@pytest.mark.parametrize("descriptor", ["staticmethod", "classmethod"])
@pytest.mark.parametrize("location", ["unrelated", "later", "visible", "other_module"])
def test_descriptor_aliases_require_prior_visible_builtins_import(descriptor, location):
    imports = {
        "unrelated": f"def unrelated():\n    from builtins import {descriptor} as marker\n",
        "later": "",
        "visible": f"from builtins import {descriptor} as marker\n",
        "other_module": f"from vendor import {descriptor} as marker\n",
    }
    source = "def marker(function):\n    return function\n" + imports[location] + (
        "class Owner:\n    @marker\n    def run(self):\n        self.target()\n"
    )
    if location == "later":
        source += f"from builtins import {descriptor} as marker\n"
    result = method_selection(python_syntax(source))
    assert bool(result) is (location != "visible")


@pytest.mark.parametrize("write", ["self = other", "self += other", "(self := other)"])
@pytest.mark.parametrize("location", ["nested", "method", "unrelated"])
def test_bound_self_only_rejects_writes_in_method_scope(write, location):
    body = {
        "nested": f"        def inner(self):\n            {write}\n",
        "method": f"        {write}\n",
        "unrelated": "        unrelated = other\n",
    }[location]
    state = python_syntax("class Owner:\n    def run(self):\n" + body + "        self.target()\n")
    assert bool(method_selection(state)) is (location != "method")


@pytest.mark.parametrize(
    ("pattern", "irrefutable"),
    [("_", True), ("capture", True), ("pkg.value", False), ("_ as name", True),
     ("1 as name", False), ("1 | _", True), ("1 | 2", False),
     ("(capture)", True), ("(capture,)", False), ("[capture]", False)],
)
def test_match_patterns_count_only_refutable_cases(pattern, irrefutable):
    state = python_syntax(f"match value:\n    case {pattern}:\n        pass\n")
    case = next(n for n in state.nodes if n.type == "case_clause")
    assert python.case_decision(case) is not irrefutable


@pytest.mark.parametrize("parameters", ["self: Owner, value: int", "self: Owner", ""])
def test_typed_self_and_empty_parameters_are_counted(parameters):
    state = python_syntax(f"class Owner:\n    def run({parameters}):\n        pass\n")
    method = next(n for n in state.nodes if n.type == "function_definition")
    assert python.parameter_count(method) == int("value" in parameters)


@pytest.mark.parametrize("location", ["prior", "later", "unrelated", "ordinary"])
def test_typing_overload_import_scope_and_order(location):
    prefix = {
        "prior": "import typing as t\n", "later": "",
        "unrelated": "def unrelated():\n    import typing as t\n",
        "ordinary": "import vendor as t\n",
    }[location]
    source = prefix + "@t.overload\ndef run(value: int): ...\n"
    if location == "later":
        source += "import typing as t\n"
    state = python_syntax(source)
    method = next(n for n in state.nodes if n.type == "function_definition"
                  and text(field(n, "name")) == "run")
    candidate = symbol(start=method.start_byte, end=method.end_byte)
    assert typing_overload(state, candidate) is (location == "prior")


def test_bound_self_rejects_missing_function_and_empty_parameters():
    assert not bound_self(syntax(), None)
    assert not bound_self(syntax(), node("function_definition"))
    assert not bound_self(syntax(), node("function_definition", parameters=node("parameters")))


def test_nested_nonlocal_self_write_still_invalidates_outer_receiver():
    state = python_syntax("class Owner:\n    def run(self):\n        def inner():\n"
                          "            nonlocal self\n            self = other\n        self.target()\n")
    assert not method_selection(state)


def test_comprehension_walrus_self_write_still_invalidates_receiver():
    state = python_syntax("class Owner:\n    def run(self):\n"
                          "        [(self := value) for value in values]\n        self.target()\n")
    assert not method_selection(state)


def test_top_level_self_parameter_is_not_an_instance_receiver():
    assert not method_selection(python_syntax("def run(self):\n    self.target()\n"))


@pytest.mark.parametrize("parameters", ["", "other", "value: Owner"])
def test_class_method_without_first_self_cannot_bind_self(parameters):
    state = python_syntax(f"class Owner:\n    def run({parameters}):\n        self.target()\n")
    assert not method_selection(state)


def test_empty_nested_body_does_not_hide_class_scope():
    assert not python._hides_class_scope(syntax(), node("function_definition"), 20)


def test_package_markers_not_ordinary_files_determine_source_roots():
    files = [parsed("lib/pkg/__init__.py"), parsed("other/tools.py")]
    assert python._source_roots(files) == {PurePosixPath("."), PurePosixPath("lib")}


@pytest.mark.parametrize("declaration", [None, node("function_definition")])
def test_static_fallback_handles_missing_and_undecorated_syntax(declaration):
    state = syntax(declarations={(10, 20): declaration})
    assert not python.PythonResolution().static(state, symbol())


@pytest.mark.parametrize("position, expected", [(19, False), (20, True), (39, True), (40, False)])
def test_class_visibility_uses_half_open_body(position, expected):
    body = node("block", start=20, end=40)
    scope = node("class_definition", start=10, end=50, body=body)
    root = SimpleNamespace(descendant_for_byte_range=lambda start, end: scope)
    assert python.PythonResolution().visible(syntax(root=root), scope, position) is expected


@pytest.mark.parametrize("kind", ["function_definition", "lambda", "class_definition"])
@pytest.mark.parametrize("position, expected", [(20, True), (39, True), (40, False), (19, False)])
def test_nested_bodies_hide_class_scope_only_inside_body(kind, position, expected):
    parent = node(kind, body=node("block", start=20, end=40))
    assert python._hides_class_scope(syntax(), parent, position) is expected


def test_python_select_accepts_one_plain_function_without_overload_group():
    candidate = symbol()
    identity = SimpleNamespace(syntax={candidate.file_path: syntax()})
    assert python.PythonResolution().select(identity, request(), [candidate]) == [candidate]
    assert python.PythonResolution().select(identity, request(), []) == []
