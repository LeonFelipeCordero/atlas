"""Grammar-backed input counts; unsupported or ambiguous headers stay unknown."""

from tree_sitter import Node

from ..extraction.syntax import field, text
from . import elixir

COMMENTS = frozenset({"comment", "line_comment", "block_comment"})


def _children(node: Node) -> list[Node]:
    return [child for child in node.named_children if child.type not in COMMENTS]


def _parameters(node: Node, *types: str) -> Node | None:
    return field(node, "parameters", "parameter") or next(
        (child for child in node.named_children if child.type in types), None
    )


def _count(
    parameters: Node | None, excluded: frozenset[str] = frozenset()
) -> int | None:
    if parameters is None or parameters.has_error:
        return None
    return sum(child.type not in excluded for child in _children(parameters))


def python_count(node: Node) -> int | None:
    parameters = _parameters(node)
    if parameters is None:
        return 0 if node.type == "lambda" else None
    count = _count(parameters, frozenset({"positional_separator", "keyword_separator"}))
    entries = _children(parameters)
    if count is None or not entries:
        return count
    return count - int(_python_method(node) and _python_receiver(entries[0]))


def _python_owner(node: Node) -> tuple[Node | None, list[Node]]:
    owner = node.parent
    decorators: list[Node] = []
    if owner is not None and owner.type == "decorated_definition":
        decorators = [
            child for child in owner.named_children if child.type == "decorator"
        ]
        owner = owner.parent
    return owner, decorators


def _python_method(node: Node) -> bool:
    owner, decorators = _python_owner(node)
    if any(_python_static(decorator) for decorator in decorators):
        return False
    return (
        owner is not None
        and owner.type == "block"
        and owner.parent is not None
        and owner.parent.type == "class_definition"
    )


def _python_static(decorator: Node) -> bool:
    expression = next(iter(_children(decorator)), None)
    return text(expression) == "staticmethod"


def _python_receiver(first: Node) -> bool:
    if first.type == "typed_parameter":
        first = next(iter(first.named_children), first)
    return first.type in {
        "identifier",
        "default_parameter",
        "typed_default_parameter",
    }


def _script_callable(node: Node) -> Node | None:
    if node.type != "property_signature":
        return node
    annotation = field(node, "type")
    while annotation is not None and annotation.type in {
        "type_annotation", "parenthesized_type",
    }:
        annotation = next(iter(annotation.named_children), None)
    if annotation is None or annotation.type != "function_type":
        return None
    return annotation


def script_count(node: Node) -> int | None:
    callable_node = _script_callable(node)
    if callable_node is None:
        return None
    parameters = _parameters(callable_node)
    if parameters is None or parameters.has_error:
        return None
    if parameters.type == "identifier":
        return 1
    return sum(
        child.type != "this" and (field(child, "pattern") or child).type != "this"
        for child in _children(parameters)
    )


def go_count(node: Node) -> int | None:
    parameters = _parameters(node)
    if parameters is None or parameters.has_error:
        return None
    entries = _children(parameters)
    if any(
        child.type not in {"parameter_declaration", "variadic_parameter_declaration"}
        for child in entries
    ):
        return None
    return sum(max(1, len(child.children_by_field_name("name"))) for child in entries)


def rust_count(node: Node) -> int | None:
    parameters = _parameters(node)
    if parameters is None or parameters.has_error:
        return None
    return sum(
        child.type not in {"self_parameter", "attribute_item"}
        and (field(child, "pattern") or child).type != "self"
        for child in _children(parameters)
    )


def java_count(node: Node) -> int | None:
    parameters = _parameters(node)
    if parameters is not None and parameters.type == "identifier":
        return 1
    return _count(parameters, frozenset({"receiver_parameter"}))


def kotlin_count(node: Node) -> int | None:
    parameters = _parameters(node, "function_value_parameters", "lambda_parameters")
    if parameters is None:
        # An implicit lambda input (it) cannot be inferred without type resolution.
        return (
            0
            if node.type == "lambda_literal"
            and any(child.type == "->" for child in node.children)
            else None
        )
    if parameters.has_error:
        return None
    entries = _children(parameters)
    return sum(
        child.type
        in {"parameter", "variable_declaration", "multi_variable_declaration"}
        for child in entries
    )


def elixir_count(node: Node) -> int | None:
    if node.type == "anonymous_function":
        return _elixir_anonymous_count(node)
    if node.type != "call" or elixir.target(node) not in elixir.DECLARATIONS:
        return None
    head = elixir._declaration_head(node)
    if head is None or head.has_error:
        return None
    return _elixir_head_count(head)


def _elixir_head_count(head: Node) -> int | None:
    if head.type == "identifier":
        return 0
    return _count(elixir.arguments(head)) if head.type == "call" else None


def _elixir_anonymous_count(node: Node) -> int | None:
    clauses = [child for child in node.named_children if child.type == "stab_clause"]
    counts = {_elixir_clause_count(clause) for clause in clauses}
    return counts.pop() if len(counts) == 1 else None


def _elixir_clause_count(clause: Node) -> int | None:
    inputs = field(clause, "left")
    if inputs is None:
        return 0
    if inputs.type == "binary_operator":
        inputs = field(inputs, "left")
    return _count(inputs) if inputs is not None and inputs.type == "arguments" else None
