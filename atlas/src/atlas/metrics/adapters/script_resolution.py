"""Conservative inheritance and executable selection for script languages."""

import re

from ...domain.models import Call, Symbol
from ...syntax import field, text
from ..resolution_contract import ResolutionRequest


def inherited_members(resolver, parent: Symbol, name: str, seen=None):
    """Follow only one proven base; unknown bases and cycles remain unresolved."""
    seen = set() if seen is None else seen
    if parent.key in seen:
        return []
    seen = seen | {parent.key}
    syntax = resolver.syntax[parent.file_path]
    if (not _plain_class(syntax, parent) or syntax.adapter.member_overwritten(syntax, parent, name)
            or _instance_member_write(syntax, parent, name)):
        return []
    direct = resolver._member_declarations(parent, name)
    if direct:
        return [] if _base_instance_write(resolver, parent, name, seen) else direct
    # A non-callable own declaration also masks an inherited method.
    if any(s.parent_key == parent.key and s.name == name for s in syntax.file.symbols):
        return []
    base = _base_class(resolver, parent)
    return inherited_members(resolver, base, name, seen) if base is not None else []


def _base_class(resolver, parent):
    syntax = resolver.syntax[parent.file_path]
    file = resolver.files[parent.file_path]
    bases = [i for i in file.inheritances if i.source_key == parent.key]
    if len(bases) != 1 or not _plain_base(syntax, parent, bases[0].target_name):
        return None
    base = bases[0]
    call = Call(file.source.path, base.target_name, parent.start_byte, parent.end_byte,
                base.line, base.evidence, True)
    request = ResolutionRequest(file, call, resolver.symbols.get(parent.parent_key), base.target_name)
    matches = syntax.adapter.inheritance(resolver, request, resolver.named(request))
    return matches[0] if len(matches) == 1 and matches[0].kind == "class" else None


def _base_instance_write(resolver, parent, name, seen):
    target = _base_class(resolver, parent)
    if target is None or target.key in seen:
        return False
    syntax = resolver.syntax[target.file_path]
    return (not _plain_class(syntax, target) or _instance_field(syntax, target, name)
            or _instance_member_write(syntax, target, name)
            or _base_instance_write(resolver, target, name, seen | {target.key}))


def _instance_member_write(syntax, parent, name):
    for nodes, receivers in _receiver_scopes(syntax, parent):
        if any(node.type in syntax.adapter.member_writes
               and text(syntax.adapter.write_target(node)).strip() not in receivers
               and member_write(text(syntax.adapter.write_target(node)), receivers, name)
               or member_mutation(node, receivers) for node in nodes):
            return True
    return False


def _receiver_scopes(syntax, parent):
    # Syntax is immutable during resolution; scan each class only once per run.
    cache = syntax.receiver_scope_cache
    if parent.key in cache:
        return cache[parent.key]
    scopes = {}
    for node in syntax.nodes:
        if parent.start_byte <= node.start_byte < parent.end_byte:
            scope = _instance_scope(node, parent)
            scopes.setdefault(scope, []).append(node)
    result = []
    for scope, nodes in scopes.items():
        receivers = set(syntax.adapter.self_qualifiers)
        receiver = _method_receiver(scope, parent)
        if syntax.adapter.family == "python" and receiver:
            receivers.add(receiver)
        result.append((nodes, _lexical_aliases(nodes, receivers)))
    cache[parent.key] = result
    return result


def _instance_scope(node, parent):
    """Keep aliases within one method, including its nested closures."""
    scope = node
    while node.parent is not None and node.start_byte != parent.start_byte:
        if node.type in {"function_definition", "method_definition", "arrow_function",
                         "function_expression", "function_declaration"}:
            scope = node
        node = node.parent
    return scope if scope.type in {"function_definition", "method_definition", "arrow_function",
                                  "function_expression", "function_declaration"} else node


def _lexical_aliases(nodes, receivers):
    """Retain possible aliases across rebindings and branches until a fixed point."""
    receivers = set(receivers)
    while True:
        aliases = {text(target) for node in nodes
                   if node.type in {"assignment", "named_expression", "assignment_expression",
                                    "variable_declarator"}
                   and text(field(node, "right", "value")) in receivers
                   and (target := field(node, "left", "name")) is not None
                   and target.type == "identifier"}
        if aliases <= receivers:
            return receivers
        receivers |= aliases


def _instance_field(syntax, parent, name):
    body = field(syntax.node(parent.start_byte, parent.end_byte), "body")
    return bool(body and any(
        child.type in {"field_definition", "public_field_definition"}
        and not any(token.type == "static" for token in child.children)
        and (target := field(child, "name", "property")) is not None
        and (text(target) == name or target.type == "computed_property_name")
        for child in body.named_children))


def _plain_class(syntax, parent):
    node = syntax.node(parent.start_byte, parent.end_byte)
    return bool(node is not None
                and (node.parent is None or node.parent.type != "decorated_definition"))


def _method_receiver(node, parent):
    if node.type != "function_definition":
        return None
    owner = node.parent
    if owner is not None and owner.type == "decorated_definition":
        owner = owner.parent
    parameters = field(node, "parameters")
    if (owner and owner.parent and owner.parent.start_byte == parent.start_byte
            and parameters and parameters.named_children):
        return text(parameters.named_children[0]).split(":", 1)[0]
    return None


def member_mutation(node, receivers: set[str]) -> bool:
    if node.type not in {"call_expression", "call"}:
        return False
    function = text(field(node, "function"))
    mutators = {"Object.defineProperty", "Object.defineProperties", "Object.assign",
                "Object.setPrototypeOf", "Reflect.defineProperty", "Reflect.set",
                "Reflect.deleteProperty", "setattr", "delattr"}
    arguments = field(node, "arguments")
    return bool(function in mutators and arguments and arguments.named_children
                and text(arguments.named_children[0]) in receivers)


def member_write(target: str, receivers: set[str], name: str) -> bool:
    target = re.sub(r"\s+", "", target)
    return any(target == receiver + "." + name or target.startswith(receiver + "[")
               or target == receiver for receiver in receivers)


def _plain_base(syntax, parent, target):
    node = syntax.node(parent.start_byte, parent.end_byte)
    if node is None or node.parent is not None and node.parent.type == "decorated_definition":
        return False
    bases = field(node, "superclasses")
    if bases is None and node is not None:
        bases = next((c for c in node.named_children if c.type == "class_heritage"), None)
    if bases is None or len(bases.named_children) != 1:
        return False
    base = bases.named_children[0]
    if base.type == "extends_clause":
        base = field(base, "value")
    return bool(base and re.fullmatch(r"[\w$]+(?:\.[\w$]+)*", text(base)) and text(base) == target)


def same_declaration_group(matches: list[Symbol]) -> bool:
    return len({(s.file_path, s.parent_key, s.name) for s in matches}) == 1


def executable_implementation(identity, matches: list[Symbol], signature_types: set[str]):
    """Signatures describe one implementation, never arity-specific bodies."""
    if not matches or not same_declaration_group(matches):
        return []
    nodes = [identity.syntax[s.file_path].node(s.start_byte, s.end_byte) for s in matches]
    if any(node is None for node in nodes):
        return []
    bodies = [s for s, node in zip(matches, nodes) if field(node, "body") is not None]
    signatures = [node for node in nodes if field(node, "body") is None]
    if len(bodies) != 1 or any(node.type not in signature_types for node in signatures):
        return []
    return bodies if all(s.start_byte < bodies[0].start_byte for s, node in zip(matches, nodes)
                         if field(node, "body") is None) else []
