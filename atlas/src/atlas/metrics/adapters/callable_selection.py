"""Conservative JVM call shapes, not compiler overload resolution.

Unknown signatures and argument types remain viable. Only a sole survivor
can become a semantic target; references have no invocation argument shape.
"""

from dataclasses import dataclass, field as dataclass_field
import re
from typing import Any

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


@dataclass(frozen=True)
class TypeContext:
    syntax: Any
    ambiguous: set[str]


@dataclass(frozen=True)
class CallContext:
    source: TypeContext
    target: TypeContext
    declaration: Node | None


@dataclass
class Assignment:
    parameters: list[Parameter]
    assigned: set[int] = dataclass_field(default_factory=set)
    position: int = 0

    def index(self, argument: Argument) -> int | None:
        """Locate a named or positional parameter; advance past non-variadic positions.

        Return None for an unknown/duplicate name or excess positional input.
        """
        if argument.name is not None:
            indexes = [i for i, p in enumerate(self.parameters) if p.name == argument.name]
            return indexes[0] if len(indexes) == 1 else None
        index = self.position
        if index >= len(self.parameters):
            return None
        if not self.parameters[index].variadic:
            self.position += 1
        return index

    def assign(self, index: int) -> bool:
        """Record a parameter assignment; reject repeats except for variadic inputs."""
        if index in self.assigned and not self.parameters[index].variadic:
            return False
        self.assigned.add(index)
        return True

    def complete(self) -> bool:
        """Test whether every required, non-variadic parameter has an assignment."""
        return all(i in self.assigned or p.default or p.variadic for i, p in enumerate(self.parameters))


def _sole(matches):
    return matches if len(matches) == 1 else []


def _type_names(identity):
    if not hasattr(identity, "_jvm_type_names"):
        symbols = (s for cached in identity.syntax.values() for s in cached.file.symbols)
        identity._jvm_type_names = {s.name for s in symbols}
    return identity._jvm_type_names


def select_callable(identity, request, matches):
    """Return only a sole viable JVM callable, retaining candidates with unknown types.

    If invocation arguments are unavailable, accept only an already unique match.
    Cache repository type names on identity for conservative shadowing checks.
    """
    syntax = identity.syntax[request.file.source.path]
    call = syntax.node(request.call.start_byte, request.call.end_byte)
    arguments = call_arguments(call)
    if arguments is None:
        return _sole(matches)
    source = TypeContext(syntax, _type_names(identity))
    viable = [symbol for symbol in matches if _viable(identity, (source, arguments), symbol)]
    return _sole(viable)


def _viable(identity, invocation, symbol):
    source, arguments = invocation
    target_syntax = identity.syntax[symbol.file_path]
    declaration = target_syntax.node(symbol.start_byte, symbol.end_byte)
    parameters = callable_parameters(declaration)
    context = CallContext(source, TypeContext(target_syntax, source.ambiguous), declaration)
    return parameters is None or accepts(context, parameters, arguments)


def call_arguments(node: Node | None) -> list[Argument] | None:
    """Read Java/Kotlin invocation arguments, or None for unsupported/error syntax.

    Kotlin names and spreads are retained; trailing lambdas remain unknown.
    """
    if node is None or node.has_error:
        return None
    if node.type in {"method_invocation", "object_creation_expression"}:
        container = field(node, "arguments")
        return [Argument(c) for c in container.named_children] if container else None
    if node.type != "call_expression":
        return None
    return _kotlin_arguments(node)


def _kotlin_arguments(node: Node) -> list[Argument] | None:
    suffix = child(node, {"call_suffix"})
    if suffix is None or child(suffix, {"annotated_lambda"}) is not None:
        return None
    container = child(suffix, {"value_arguments"})
    if container is None:
        return None
    result = []
    for entry in container.named_children:
        argument = _argument(entry)
        if argument is None:
            return None
        result.append(argument)
    return result


def _argument(entry: Node) -> Argument | None:
    if entry.type != "value_argument" or not entry.named_children:
        return None
    named = any(c.type == "=" for c in entry.children)
    return Argument(entry.named_children[-1],
                    text(entry.named_children[0]) if named else None,
                    any(c.type == "*" for c in entry.children))


def _parameter_container(node: Node | None) -> Node | None:
    if node is None or node.has_error:
        return None
    container = field(node, "parameters") or child(node, {"function_value_parameters"})
    if container is None or container.type not in {"formal_parameters", "function_value_parameters"}:
        return None
    return container


def callable_parameters(node: Node | None) -> list[Parameter] | None:
    """Read JVM parameter names, types, defaults and variadic flags.

    Return None for missing/error headers or explicit receiver parameters.
    """
    container = _parameter_container(node)
    if container is None:
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


def accepts(context: CallContext, parameters: list[Parameter], arguments: list[Argument]) -> bool:
    """Test argument assignment and proven type compatibility, not compiler validity.

    Spreads remain viable without checks. Otherwise reject missing required
    inputs and proven type conflicts, but retain unknown types.
    """
    # A spread's length/type and named vararg array semantics need a compiler.
    if any(a.spread for a in arguments):
        return True
    assignment = Assignment(parameters)
    for argument in arguments:
        if not _accept_argument(context, assignment, argument):
            return False
    return assignment.complete()


def _accept_argument(context: CallContext, assignment: Assignment, argument: Argument) -> bool:
    index = assignment.index(argument)
    if index is None or not assignment.assign(index):
        return False
    parameter = assignment.parameters[index]
    actual = expression_type(context.source, argument.value)
    expected = proven_type(context.target, parameter.annotation, context.declaration)
    if argument.name and parameter.variadic:
        return True
    return not incompatible(actual, expected, context.source.syntax.adapter.family)


def expression_type(context: TypeContext, node: Node) -> str | None:
    """Infer a supported literal or explicit lexical binding type; otherwise return None."""
    kind = node.type
    if kind in {"string_literal", "multiline_string_literal"}:
        return "String"
    if kind in {"character_literal"}:
        return "Char" if context.syntax.adapter.family == "kotlin" else "char"
    if kind in {"boolean_literal", "true", "false"}:
        return "Boolean" if context.syntax.adapter.family == "kotlin" else "boolean"
    if kind in {"decimal_integer_literal", "hex_integer_literal", "octal_integer_literal", "binary_integer_literal", "integer_literal"}:
        return _integer_type(text(node), context.syntax.adapter.family)
    if kind not in {"identifier", "simple_identifier"}:
        return None
    return _identifier_type(context, node)


def _integer_type(value, family):
    if re.search(r"[uU]", value):
        return None
    annotation = "long" if value.lower().endswith("l") else "int"
    return annotation.capitalize() if family == "kotlin" else annotation


def _visible_binding(syntax, binding, node):
    return (binding.name == text(node) and not binding.member and not binding.inferred
            and syntax._visible(binding.scope, node.start_byte))


def _scope_width(binding):
    return binding.scope.end_byte - binding.scope.start_byte


def _identifier_type(context: TypeContext, node: Node) -> str | None:
    # Reuse lexical scope information, but not inferred receiver annotations:
    # initializer classes may have subtypes, aliases, or unstable bindings.
    syntax = context.syntax
    candidates = (b for n in syntax.nodes for b in syntax.adapter.receiver_bindings(syntax, n))
    bindings = [b for b in candidates if _visible_binding(syntax, b, node)]
    if not bindings:
        return None
    return _nearest_type(context, bindings)


def _nearest_type(context: TypeContext, bindings) -> str | None:
    width = min(_scope_width(b) for b in bindings)
    nearest = [b for b in bindings if _scope_width(b) == width]
    return proven_type(context, nearest[0].annotation, nearest[0].node) if len(nearest) == 1 else None


_JAVA_NUMERIC = {"byte", "short", "int", "long", "float", "double", "char"}
_JAVA_PRIMITIVES = _JAVA_NUMERIC | {"boolean"}
_JAVA_STRINGS = {"String", "java.lang.String"}
_KOTLIN_CLOSED = {"String", "Char", "Boolean", "Int", "Long", "Float", "Double", "Byte", "Short"}


def _mentions_type(node: Node, annotation: str) -> bool:
    return (node.type in {"type_parameter", "type_parameters"}
            and re.search(r"\b" + re.escape(annotation) + r"\b", text(node)) is not None)


def _annotation_node(candidate: Node, node: Node) -> bool:
    return (node.start_byte <= candidate.start_byte < node.end_byte
            and candidate.type in {"nullable_type", "generic_type", "user_type"})


def _lossy_annotation(syntax, node: Node) -> bool:
    types = [n for n in syntax.nodes if _annotation_node(n, node)]
    return any("?" in text(n) or "<" in text(n) for n in types)


def _uncertain_type(context: TypeContext, annotation: str, node: Node) -> bool:
    syntax = context.syntax
    if annotation in context.ambiguous or syntax.imports:
        return True
    if any(_mentions_type(n, annotation) for n in syntax.nodes):
        return True
    # Inspect original annotations, not the lossy receiver normalization.
    return _lossy_annotation(syntax, node)


def proven_type(context: TypeContext, annotation: str | None, node: Node | None) -> str | None:
    """Return a usable annotation, or None when syntax or name resolution is uncertain.

    Java primitives remain proven; imports, colliding names and lossy
    nullable/generic annotations prevent other type proofs.
    """
    if annotation is None or node is None:
        return None
    # Primitive Java names cannot be shadowed. Reference/Kotlin names can.
    if context.syntax.adapter.family == "java" and annotation in _JAVA_PRIMITIVES:
        return annotation
    return None if _uncertain_type(context, annotation, node) else annotation


def _kotlin_incompatible(actual: str, expected: str) -> bool:
    # Integer literals can be contextually typed as smaller integral types.
    if actual == "Int" and expected in {"Byte", "Short", "Long"}:
        return False
    return actual in _KOTLIN_CLOSED and expected in _KOTLIN_CLOSED


def _java_incompatible(actual: str, expected: str) -> bool:
    # Widening, boxing and reference supertypes remain candidates.
    if actual in _JAVA_NUMERIC and expected in _JAVA_NUMERIC:
        return False
    if actual in _JAVA_STRINGS and expected in _JAVA_STRINGS:
        return False
    closed = _JAVA_PRIMITIVES | _JAVA_STRINGS
    return actual in closed and expected in closed


def incompatible(actual: str | None, expected: str | None, family: str) -> bool:
    """Only closed built-in domains prove incompatibility; nominal subtyping is unknown."""
    if actual is None or expected is None or actual == expected:
        return False
    if family == "kotlin":
        return _kotlin_incompatible(actual, expected)
    return _java_incompatible(actual, expected)
