"""Grammar-specific receiver declarations; unknown annotations are not types."""

import re
from dataclasses import dataclass

from tree_sitter import Node

from ..syntax import field, text


@dataclass(frozen=True)
class ReceiverBinding:
    name: str
    annotation: str | None
    scope: Node
    node: Node
    inferred: bool = False
    member: bool = False
    static: bool = False


def type_name(node: Node | None) -> str | None:
    """Extract a simple or qualified type name, stripping supported wrappers.

    Generic arguments are discarded; absent or unsupported syntax returns None.
    """
    if node is None:
        return None
    if node.type in {"generic_type", "generic_type_with_turbofish"}:
        return type_name(field(node, "name", "type") or child(node, {"type_identifier"}))
    if node.type in {"type_annotation", "type", "pointer_type", "reference_type", "nullable_type"}:
        return _wrapped_type_name(node)
    value = text(node).split("<", 1)[0] if node.type == "user_type" else text(node)
    return value if re.fullmatch(r"[\w$]+(?:(?:\.|::)[\w$]+)*", value) else None


def _wrapped_type_name(node: Node) -> str | None:
    children = [c for c in node.named_children if c.type != "lifetime"]
    return type_name(children[-1]) if len(children) == 1 else None


def child(node: Node, kinds: set[str]) -> Node | None:
    """Return the first direct named child of a requested kind, or None."""
    return next((c for c in node.named_children if c.type in kinds), None)


def enclosing(node: Node, kinds: set[str]) -> Node | None:
    """Return the nearest matching ancestor, excluding node itself, or None."""
    parent = node.parent
    while parent and parent.type not in kinds:
        parent = parent.parent
    return parent


CLASSES = {"class_definition", "class_declaration", "struct_item", "type_spec"}


@dataclass(frozen=True)
class Declaration:
    name: Node | None
    annotation: str | None
    value: Node | None = None
    member: bool = False


def declaration(syntax, node, details: Declaration):
    """Build one receiver binding, or an empty list if name or scope is absent.

    Members use their enclosing type scope. Missing annotations and Java ``var``
    permit conservative constructor or injected-parameter type inference.
    """
    scope = enclosing(node, CLASSES) if details.member else syntax.scope(node)
    if details.name is None or scope is None:
        return []
    annotation = None if details.annotation == "var" else details.annotation
    inferred = annotation is None
    if inferred:
        annotation = _inferred_annotation(syntax, node, details)
    return [ReceiverBinding(text(details.name), annotation, scope, node, inferred, details.member, static_field(node))]


def _inferred_annotation(syntax, node, details: Declaration):
    value = details.value
    if details.member and member_assignment(node) and not constructor(node):
        value = None
    annotation = _constructed_annotation(syntax, value)
    if details.member and value is not None and value.type == "identifier":
        annotation = injected_parameter(syntax, node, text(value))
    return annotation


def _constructed_annotation(syntax, value):
    if value is not None and value.type in syntax.adapter.receiver_class_nodes:
        callee, receiver = syntax.adapter.call_target(value)
        if receiver is None:
            return type_name(callee)
    return None


def member_assignment(node):
    """Return whether the left-hand target is an attribute or member expression."""
    target = field(node, "left")
    return target is not None and target.type in {"attribute", "member_expression"}


def static_field(node):
    """Detect a static marker on a declaration or its variable-declarator parent."""
    owner = node.parent if node.type == "variable_declarator" else node
    return owner is not None and any(c.type == "static" or c.type == "modifiers" and "static" in text(c).split()
                                     for c in owner.children)


def constructor(node):
    """Return whether the nearest function or method is __init__ or constructor."""
    method = enclosing(node, {"function_definition", "method_definition"})
    return method is not None and text(field(method, "name")) in {"__init__", "constructor"}


def injected_parameter(syntax, node, name):
    """Return the unique unwritten enclosing parameter's annotation, or None."""
    method = enclosing(node, {"function_definition", "method_definition"})
    if method is None:
        return None
    parameters = field(method, "parameters")
    if parameters is None:
        return None
    if _parameter_written(syntax, method, name):
        return None
    matches = _parameter_bindings(syntax, parameters, name)
    return matches[0].annotation if len(matches) == 1 else None


def _parameter_written(syntax, method, name):
    return any(n.type in syntax.adapter.assignments
               and method.start_byte <= n.start_byte < method.end_byte and text(field(n, "left")) == name
               for n in syntax.nodes)


def _parameter_bindings(syntax, parameters, name):
    return [b for parameter in parameters.named_children
            for b in syntax.adapter.receiver_bindings(syntax, parameter) if b.name == name]


def java_bindings(syntax, node):
    """Extract Java parameter, local, or field receiver bindings; otherwise return []."""
    if node.type == "formal_parameter":
        return declaration(syntax, node, Declaration(field(node, "name"), type_name(field(node, "type"))))
    if node.type != "variable_declarator" or node.parent is None:
        return []
    return declaration(syntax, node, Declaration(field(node, "name"), type_name(field(node.parent, "type")),
                       field(node, "value"), node.parent.type == "field_declaration"))


def kotlin_bindings(syntax, node):
    """Extract Kotlin parameter/property bindings, including val/var class parameters.

    Plain class parameters and unsupported declarations return an empty list.
    """
    if node.type not in {"class_parameter", "parameter", "variable_declaration"}:
        return []
    name = child(node, {"simple_identifier"})
    annotation = type_name(child(node, {"user_type", "nullable_type", "function_type"}))
    member = _kotlin_member(node)
    if node.type == "class_parameter" and not member:
        return []
    value, member = _kotlin_property(node, member)
    return declaration(syntax, node, Declaration(name, annotation, value, member))


def _kotlin_member(node):
    return node.type == "class_parameter" and any(c.type in {"val", "var", "binding_pattern_kind"} for c in node.children)


def _kotlin_property(node, member):
    parent = node.parent
    if parent and parent.type == "property_declaration":
        value = next((c for c in parent.named_children if c.type == "call_expression"), None)
        return value, parent.parent is not None and parent.parent.type == "class_body"
    return None, member


def python_bindings(syntax, node):
    """Extract typed parameters and simple assignments as Python receiver bindings.

    Class-scope names and self attributes are members; other targets return [].
    """
    if node.type in {"typed_parameter", "typed_default_parameter"}:
        return declaration(syntax, node, Declaration(child(node, {"identifier"}), type_name(field(node, "type"))))
    if node.type != "assignment":
        return []
    name = field(node, "left")
    if name is None:
        return []
    member = name.type == "attribute" and text(field(name, "object")) == "self"
    if member:
        name = field(name, "attribute")
    elif name.type != "identifier":
        return []
    else:
        member = syntax.scope(node).type == "class_definition"
    return declaration(syntax, node, Declaration(name, type_name(field(node, "type")), field(node, "right"), member))


def script_bindings(syntax, node):
    """Extract JavaScript/TypeScript parameter, variable, and field bindings.

    Includes this assignments and accessibility-marked parameter properties;
    unsupported targets return an empty list.
    """
    if node.type == "assignment_expression":
        target = field(node, "left")
        if target and target.type == "member_expression" and text(field(target, "object")) == "this":
            return declaration(syntax, node, Declaration(field(target, "property"), None, field(node, "right"), True))
        return []
    if node.type not in {"required_parameter", "optional_parameter", "variable_declarator", "public_field_definition", "field_definition"}:
        return []
    member = "field_definition" in node.type or any(c.type == "accessibility_modifier" for c in node.named_children)
    return declaration(syntax, node, Declaration(field(node, "name", "pattern", "property"), type_name(field(node, "type")), field(node, "value"), member))


def go_bindings(syntax, node):
    """Extract Go parameter, variable, field, and short-declaration bindings.

    Short declarations infer types only from one initializer per name.
    Unsupported declarations return an empty list.
    """
    if node.type == "short_var_declaration":
        return _go_short_bindings(syntax, node)
    if node.type not in {"parameter_declaration", "var_spec", "field_declaration"}:
        return []
    return [binding for name in node.children_by_field_name("name")
            for binding in declaration(syntax, node, Declaration(name, type_name(field(node, "type")),
                                       member=node.type == "field_declaration"))]


def _go_short_bindings(syntax, node):
    target = field(node, "left")
    names = target.named_children if target else []
    right = field(node, "right")
    values = right.named_children if right else []
    # Only pair one initializer per name; a multi-result call proves no type.
    return [b for index, name in enumerate(names) if name.type == "identifier"
            for b in declaration(syntax, node, Declaration(
                name, None, values[index] if len(values) == len(names) else None))]


def rust_bindings(syntax, node):
    """Extract Rust parameter, let, and field receiver bindings.

    Destructured let patterns and unsupported declarations return an empty list.
    """
    if node.type not in {"parameter", "let_declaration", "field_declaration"}:
        return []
    name = field(node, "pattern", "name")
    if name is None or node.type == "let_declaration" and name.type != "identifier":
        return []
    return declaration(syntax, node, Declaration(name, type_name(field(node, "type")),
                       field(node, "value"), member=node.type == "field_declaration"))
