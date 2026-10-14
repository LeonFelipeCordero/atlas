"""Python overload and bound-instance selection helpers."""

from tree_sitter import Node

from ...domain.models import Symbol
from ...syntax import field, text


def import_names(node: Node) -> list[tuple[str, str]]:
    return [
        (text(field(child, "name") or child), text(field(child, "alias")))
        for child in node.children_by_field_name("name")
    ]


def _decorators(node: Node) -> list[str]:
    return [text(c).removeprefix("@").strip() for c in node.named_children
            if c.type == "decorator"]


def _prior_import(syntax, imported: Node, position: int) -> bool:
    return (imported.type in {"import_statement", "import_from_statement"}
            and syntax._visible(syntax.scope(imported), position)
            and imported.start_byte < position)


def _overload_target(imported: Node, name: str, local: str) -> str:
    if imported.type == "import_statement" and name == "typing":
        return local + ".overload"
    if (imported.type == "import_from_statement"
            and text(field(imported, "module_name")) == "typing" and name == "overload"):
        return local
    return ""


def _add_providers(providers: dict[str, list[str]], imported: Node) -> None:
    for name, alias in import_names(imported):
        local = alias or name
        providers.setdefault(local, []).append(_overload_target(imported, name, local))


class _OverloadProviders:
    def __init__(self, syntax, decorators, position):
        self.syntax = syntax
        self.decorators = decorators
        self.position = position

    def matches(self, local, targets) -> bool:
        return (len(targets) == 1 and targets[0] in self.decorators
                and not self.syntax.shadowed(local, self.position)
                and not self.syntax.member_rebound(local, "overload"))


def typing_overload(syntax, symbol: Symbol) -> bool:
    node = syntax.node(symbol.start_byte, symbol.end_byte)
    if node is None or node.parent is None or node.parent.type != "decorated_definition":
        return False
    decorators = _decorators(node.parent)
    providers: dict[str, list[str]] = {}
    for imported in syntax.nodes:
        if _prior_import(syntax, imported, node.start_byte):
            _add_providers(providers, imported)
    selection = _OverloadProviders(syntax, decorators, node.start_byte)
    return any(selection.matches(local, targets) for local, targets in providers.items())


def overload_implementation(syntax, ordered: list[Symbol]) -> list[Symbol]:
    if all(typing_overload(syntax, s) for s in ordered[:-1]) and not typing_overload(syntax, ordered[-1]):
        return [ordered[-1]]
    return []


def _descriptor_aliases(imported: Node) -> set[str]:
    if (imported.type != "import_from_statement"
            or text(field(imported, "module_name")) != "builtins"):
        return set()
    return {alias or name for name, alias in import_names(imported)
            if name in {"staticmethod", "classmethod"}}


def _descriptor_method(syntax, owner: Node) -> bool:
    descriptors = {"staticmethod", "classmethod", "builtins.staticmethod", "builtins.classmethod"}
    for imported in syntax.nodes:
        descriptors |= _descriptor_aliases(imported)
    return any(text(c).removeprefix("@").strip() in descriptors for c in owner.named_children)


def _first_self(node: Node) -> bool:
    parameters = field(node, "parameters")
    return bool(parameters is not None and parameters.named_children
                and text(parameters.named_children[0]).split(":", 1)[0] == "self")


def _self_assignment(syntax, assignment: Node, node: Node) -> bool:
    return (assignment.type in syntax.adapter.assignments
            and node.start_byte <= assignment.start_byte < node.end_byte
            and text(field(assignment, "left", "name")) == "self")


def _instance_owner(syntax, node: Node) -> bool:
    owner = node.parent
    if owner is not None and owner.type == "decorated_definition":
        if _descriptor_method(syntax, owner):
            return False
        owner = owner.parent
    return bool(owner is not None and owner.parent is not None
                and owner.parent.type == "class_definition")


def bound_self(syntax, node: Node | None) -> bool:
    while node is not None and node.type != "function_definition":
        node = node.parent
    if node is None or not _first_self(node):
        return False
    if not _instance_owner(syntax, node):
        return False
    return not any(_self_assignment(syntax, n, node) for n in syntax.nodes)
