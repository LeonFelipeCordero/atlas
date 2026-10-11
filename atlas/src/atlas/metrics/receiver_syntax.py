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
    if node is None:
        return None
    if node.type in {"generic_type", "generic_type_with_turbofish"}:
        return type_name(field(node, "name", "type") or child(node, {"type_identifier"}))
    if node.type in {"type_annotation", "type", "pointer_type", "reference_type", "nullable_type"}:
        children = [c for c in node.named_children if c.type != "lifetime"]
        return type_name(children[-1]) if len(children) == 1 else None
    value = text(node).split("<", 1)[0] if node.type == "user_type" else text(node)
    return value if re.fullmatch(r"[\w$]+(?:(?:\.|::)[\w$]+)*", value) else None


def child(node: Node, kinds: set[str]) -> Node | None:
    return next((c for c in node.named_children if c.type in kinds), None)


def enclosing(node: Node, kinds: set[str]) -> Node | None:
    parent = node.parent
    while parent and parent.type not in kinds:
        parent = parent.parent
    return parent


CLASSES = {"class_definition", "class_declaration", "struct_item", "type_spec"}


def declaration(syntax, node, name, annotation, value=None, member=False):
    scope = enclosing(node, CLASSES) if member else syntax.scope(node)
    if name is None or scope is None:
        return []
    annotation = None if annotation == "var" else annotation
    inferred = annotation is None
    if inferred and member and member_assignment(node) and not constructor(node):
        value = None
    if inferred and value is not None and value.type in syntax.adapter.receiver_class_nodes:
        callee, receiver = syntax.adapter.call_target(value)
        if receiver is None:
            annotation = type_name(callee)
    if inferred and member and value is not None and value.type == "identifier":
        annotation = injected_parameter(syntax, node, text(value))
    return [ReceiverBinding(text(name), annotation, scope, node, inferred, member, static_field(node))]


def member_assignment(node):
    target = field(node, "left")
    return target is not None and target.type in {"attribute", "member_expression"}


def static_field(node):
    owner = node.parent if node.type == "variable_declarator" else node
    return owner is not None and any(c.type == "static" or c.type == "modifiers" and "static" in text(c).split()
                                     for c in owner.children)


def constructor(node):
    method = enclosing(node, {"function_definition", "method_definition"})
    return method is not None and text(field(method, "name")) in {"__init__", "constructor"}


def injected_parameter(syntax, node, name):
    method = enclosing(node, {"function_definition", "method_definition"})
    if method is None:
        return None
    parameters = field(method, "parameters")
    if parameters is None:
        return None
    writes = [n for n in syntax.nodes if n.type in syntax.adapter.assignments
              and method.start_byte <= n.start_byte < method.end_byte and text(field(n, "left")) == name]
    if writes:
        return None
    matches = [b for parameter in parameters.named_children
               for b in syntax.adapter.receiver_bindings(syntax, parameter) if b.name == name]
    return matches[0].annotation if len(matches) == 1 else None


def java_bindings(syntax, node):
    if node.type == "formal_parameter":
        return declaration(syntax, node, field(node, "name"), type_name(field(node, "type")))
    if node.type != "variable_declarator" or node.parent is None:
        return []
    return declaration(syntax, node, field(node, "name"), type_name(field(node.parent, "type")),
                       field(node, "value"), node.parent.type == "field_declaration")


def kotlin_bindings(syntax, node):
    if node.type not in {"class_parameter", "parameter", "variable_declaration"}:
        return []
    name = child(node, {"simple_identifier"})
    annotation = type_name(child(node, {"user_type", "nullable_type", "function_type"}))
    parent = node.parent
    value = None
    member = node.type == "class_parameter" and any(c.type in {"val", "var", "binding_pattern_kind"} for c in node.children)
    if node.type == "class_parameter" and not member:
        return []
    if parent and parent.type == "property_declaration":
        value = next((c for c in parent.named_children if c.type == "call_expression"), None)
        member = parent.parent is not None and parent.parent.type == "class_body"
    return declaration(syntax, node, name, annotation, value, member)


def python_bindings(syntax, node):
    if node.type in {"typed_parameter", "typed_default_parameter"}:
        return declaration(syntax, node, child(node, {"identifier"}), type_name(field(node, "type")))
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
    return declaration(syntax, node, name, type_name(field(node, "type")), field(node, "right"), member)


def script_bindings(syntax, node):
    if node.type == "assignment_expression":
        target = field(node, "left")
        if target and target.type == "member_expression" and text(field(target, "object")) == "this":
            return declaration(syntax, node, field(target, "property"), None, field(node, "right"), True)
        return []
    if node.type not in {"required_parameter", "optional_parameter", "variable_declarator", "public_field_definition", "field_definition"}:
        return []
    member = "field_definition" in node.type or any(c.type == "accessibility_modifier" for c in node.named_children)
    return declaration(syntax, node, field(node, "name", "pattern", "property"), type_name(field(node, "type")), field(node, "value"), member)


def go_bindings(syntax, node):
    if node.type == "short_var_declaration":
        target = field(node, "left")
        names = target.named_children if target else []
        return [b for name in names if name.type == "identifier" for b in declaration(syntax, node, name, None)]
    if node.type not in {"parameter_declaration", "var_spec", "field_declaration"}:
        return []
    return [binding for name in node.children_by_field_name("name")
            for binding in declaration(syntax, node, name, type_name(field(node, "type")),
                                       member=node.type == "field_declaration")]


def rust_bindings(syntax, node):
    if node.type not in {"parameter", "let_declaration", "field_declaration"}:
        return []
    return declaration(syntax, node, field(node, "pattern", "name"), type_name(field(node, "type")),
                       member=node.type == "field_declaration")
