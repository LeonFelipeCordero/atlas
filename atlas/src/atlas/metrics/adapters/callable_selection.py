"""Conservative JVM call shapes, not compiler overload resolution.

Unknown signatures and argument types remain viable. Only a sole survivor
can become a semantic target; references have no invocation argument shape.
"""

from dataclasses import dataclass
import re

from tree_sitter import Node

from ...syntax import field, text
from ..receiver_syntax import child, type_name


@dataclass(frozen=True)
class Parameter:
    name: str
    annotation: str | None
    default: bool = False
    variadic: bool = False


@dataclass(frozen=True)
class Argument:
    value: Node
    name: str | None = None
    spread: bool = False


def select_callable(identity, request, matches):
    syntax = identity.syntax[request.file.source.path]
    call = syntax.node(request.call.start_byte, request.call.end_byte)
    arguments = call_arguments(call)
    if arguments is None:
        return matches if len(matches) == 1 else []
    if not hasattr(identity, "_jvm_type_names"):
        identity._jvm_type_names = {s.name for cached in identity.syntax.values() for s in cached.file.symbols}
    ambiguous = identity._jvm_type_names
    viable = []
    for symbol in matches:
        target_syntax = identity.syntax[symbol.file_path]
        declaration = target_syntax.node(symbol.start_byte, symbol.end_byte)
        parameters = callable_parameters(declaration)
        if parameters is None or accepts(syntax, parameters, arguments, target_syntax, declaration, ambiguous):
            viable.append(symbol)
    return viable if len(viable) == 1 else []


def call_arguments(node: Node | None) -> list[Argument] | None:
    if node is None or node.has_error:
        return None
    if node.type in {"method_invocation", "object_creation_expression"}:
        container = field(node, "arguments")
        return [Argument(c) for c in container.named_children] if container else None
    if node.type != "call_expression":
        return None
    suffix = child(node, {"call_suffix"})
    if suffix is None or child(suffix, {"annotated_lambda"}) is not None:
        return None
    container = child(suffix, {"value_arguments"})
    if container is None:
        return None
    result = []
    for entry in container.named_children:
        if entry.type != "value_argument" or not entry.named_children:
            return None
        named = any(c.type == "=" for c in entry.children)
        result.append(Argument(entry.named_children[-1],
                               text(entry.named_children[0]) if named else None,
                               any(c.type == "*" for c in entry.children)))
    return result


def callable_parameters(node: Node | None) -> list[Parameter] | None:
    if node is None or node.has_error:
        return None
    container = field(node, "parameters") or child(node, {"function_value_parameters"})
    if container is None or container.type not in {"formal_parameters", "function_value_parameters"}:
        return None
    result = []
    children = container.children
    for index, entry in enumerate(children):
        if entry.type in {"receiver_parameter", "ERROR"}:
            return None
        parameter = _parameter(children, index, entry)
        if parameter is not None:
            result.append(parameter)
    return result


def _parameter(children, index, entry):
    if entry.type in {"formal_parameter", "spread_parameter"}:
        name = field(entry, "name") or child(entry, {"variable_declarator"})
        annotation = field(entry, "type") or child(entry, {"integral_type", "floating_point_type", "type_identifier"})
        return Parameter(text(name), type_name(annotation), variadic=entry.type == "spread_parameter")
    if entry.type != "parameter":
        return None
    following = children[index + 1:]
    previous = children[index - 1] if index else None
    return Parameter(text(child(entry, {"simple_identifier"})),
                     type_name(child(entry, {"user_type", "nullable_type", "function_type"})),
                     bool(following and following[0].type == "="),
                     previous is not None and "vararg" in text(previous).split())


def accepts(syntax, parameters: list[Parameter], arguments: list[Argument], target_syntax, declaration, ambiguous) -> bool:
    # A spread's length/type and named vararg array semantics need a compiler.
    if any(a.spread for a in arguments):
        return True
    assigned: set[int] = set()
    position = 0
    for argument in arguments:
        if argument.name is not None:
            indexes = [i for i, p in enumerate(parameters) if p.name == argument.name]
            if len(indexes) != 1:
                return False
            index = indexes[0]
        else:
            index = position
            if index >= len(parameters):
                return False
            if not parameters[index].variadic:
                position += 1
        parameter = parameters[index]
        if index in assigned and not parameter.variadic:
            return False
        assigned.add(index)
        actual = expression_type(syntax, argument.value, ambiguous)
        expected = proven_type(target_syntax, parameter.annotation, declaration, ambiguous)
        if not (argument.name and parameter.variadic) and incompatible(actual, expected, syntax.adapter.family):
            return False
    return all(i in assigned or p.default or p.variadic for i, p in enumerate(parameters))


def expression_type(syntax, node: Node, ambiguous) -> str | None:
    kind = node.type
    if kind in {"string_literal", "multiline_string_literal"}:
        return "String"
    if kind in {"character_literal"}:
        return "Char" if syntax.adapter.family == "kotlin" else "char"
    if kind in {"boolean_literal", "true", "false"}:
        return "Boolean" if syntax.adapter.family == "kotlin" else "boolean"
    if kind in {"decimal_integer_literal", "hex_integer_literal", "octal_integer_literal", "binary_integer_literal", "integer_literal"}:
        return _integer_type(text(node), syntax.adapter.family)
    if kind not in {"identifier", "simple_identifier"}:
        return None
    return _identifier_type(syntax, node, ambiguous)


def _integer_type(value, family):
    if re.search(r"[uU]", value):
        return None
    annotation = "long" if value.lower().endswith("l") else "int"
    return annotation.capitalize() if family == "kotlin" else annotation


def _identifier_type(syntax, node, ambiguous):
    # Reuse lexical scope information, but not inferred receiver annotations:
    # initializer classes may have subtypes, aliases, or unstable bindings.
    bindings = [b for n in syntax.nodes for b in syntax.adapter.receiver_bindings(syntax, n)
                if b.name == text(node) and not b.member and not b.inferred
                and syntax._visible(b.scope, node.start_byte)]
    if not bindings:
        return None
    width = min(b.scope.end_byte - b.scope.start_byte for b in bindings)
    nearest = [b for b in bindings if b.scope.end_byte - b.scope.start_byte == width]
    return proven_type(syntax, nearest[0].annotation, nearest[0].node, ambiguous) if len(nearest) == 1 else None


def proven_type(syntax, annotation, node, ambiguous):
    """Receiver names erase nullable/generic syntax; they are not type proofs."""
    if annotation is None or node is None:
        return None
    # Primitive Java names cannot be shadowed. Reference/Kotlin names can.
    if syntax.adapter.family == "java" and annotation in {
        "byte", "short", "int", "long", "float", "double", "char", "boolean"
    }:
        return annotation
    if annotation in ambiguous:
        return None
    if syntax.imports or any(n.type in {"type_parameter", "type_parameters"}
                             and re.search(r"\b" + re.escape(annotation) + r"\b", text(n))
                             for n in syntax.nodes):
        return None
    # Inspect original annotations, not the lossy receiver normalization.
    types = [n for n in syntax.nodes if node.start_byte <= n.start_byte < node.end_byte
             and n.type in {"nullable_type", "generic_type", "user_type"}]
    if any("?" in text(n) or "<" in text(n) for n in types):
        return None
    return annotation


def incompatible(actual: str | None, expected: str | None, family: str) -> bool:
    """Only closed built-in domains prove incompatibility; nominal subtyping is unknown."""
    if actual is None or expected is None or actual == expected:
        return False
    if family == "kotlin":
        closed = {"String", "Char", "Boolean", "Int", "Long", "Float", "Double", "Byte", "Short"}
        # Integer literals can be contextually typed as smaller integral types.
        if actual == "Int" and expected in {"Byte", "Short", "Long"}:
            return False
        return actual in closed and expected in closed
    numeric = {"byte", "short", "int", "long", "float", "double", "char"}
    # Widening, boxing and reference supertypes remain candidates.
    if actual in numeric and expected in numeric:
        return False
    closed = numeric | {"boolean", "String", "java.lang.String"}
    if actual in {"String", "java.lang.String"} and expected in {"String", "java.lang.String"}:
        return False
    return actual in closed and expected in closed
