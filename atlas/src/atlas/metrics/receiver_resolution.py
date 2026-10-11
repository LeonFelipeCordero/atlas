"""Resolve lexical receiver bindings without member-name or global type guesses."""

from dataclasses import replace
from functools import cached_property

from .receiver_syntax import ReceiverBinding
from .resolution_contract import FUNCTIONS
from .resolution_syntax import names
from ..syntax import field, text


class ReceiverTypes:
    def __init__(self, resolver):
        self.resolver = resolver

    @cached_property
    def bindings(self):
        return {path: [b for n in syntax.nodes for b in syntax.adapter.receiver_bindings(syntax, n)]
                for path, syntax in self.resolver.syntax.items()}

    def resolve(self, request):
        types = self._receiver_types(request)
        return None if types is None else self.resolver.members(types, request.name, False)

    def _receiver_types(self, request):
        qualifier = request.qualifier or ""
        syntax = self.resolver.syntax[request.file.source.path]
        root = qualifier.split(".")[0]
        implicit = root in syntax.adapter.self_qualifiers
        if implicit:
            types = self._implicit_types(request, root)
            if types is not None:
                return types
        if qualifier.count(".") > 1 or "." in qualifier and not implicit:
            return self._field_types(request)
        return self._lexical_types(request, qualifier, syntax)

    def _implicit_types(self, request, root):
        if self._path_written(request):
            return []
        syntax = self.resolver.syntax[request.file.source.path]
        types = syntax.adapter.receiver_owner(self.resolver, request)
        if types is None or request.qualifier == root:
            return types
        return self._fields(types, request.qualifier.partition(".")[2], request)

    def _lexical_types(self, request, qualifier, syntax):
        member = self._member_receiver(syntax, request)
        if member and not self.resolver._self_class(replace(request, qualifier=qualifier.split(".")[0])):
            return []
        name = qualifier.split(".")[-1] if member else qualifier
        if not name or "." in name or "::" in name:
            return None
        candidates = self._candidates(syntax, name, request)
        if not candidates:
            return None
        return self._binding_types(syntax, self._nearest(candidates), request)

    def _binding_types(self, syntax, candidates, request):
        if len(candidates) != 1:
            return []
        binding = candidates[0]
        if not self._member_receiver(syntax, request) and self._shadowed(syntax, binding, request.call.start_byte):
            return []
        if self._unsafe(syntax, binding, request) or self._path_written(request, receiver=False):
            return []
        return self._declared_types(syntax, binding, request)

    def _nearest(self, candidates):
        size = min(b.scope.end_byte - b.scope.start_byte for b in candidates)
        candidates = [b for b in candidates if b.scope.end_byte - b.scope.start_byte == size]
        declared = [b for b in candidates if not b.inferred]
        return declared or candidates

    def _member_receiver(self, syntax, request):
        qualifier = request.qualifier or ""
        return "." in qualifier and qualifier.split(".")[0] in syntax.adapter.self_qualifiers

    def _candidates(self, syntax, name, request):
        return [b for b in self.bindings[request.file.source.path]
                if b.name == name and self._visible(syntax, b, request)]

    def _visible(self, syntax, binding, request):
        position = request.call.start_byte
        if self._member_receiver(syntax, request):
            return binding.member and binding.scope.start_byte <= position < binding.scope.end_byte
        if binding.member and not syntax.adapter.bare_instance_fields:
            return False
        return syntax._visible(binding.scope, position)

    def _unsafe(self, syntax, binding, request):
        return (binding.member and not binding.static and self._static(request)
                or self._conditional(syntax, binding)
                or not binding.annotation
                or self._reassigned(syntax, binding, request.qualifier)
                or not binding.member and binding.node.start_byte >= request.call.start_byte)

    def _conditional(self, syntax, binding):
        if not binding.inferred and syntax.adapter.trust_receiver_annotations:
            return False
        node = binding.node.parent
        controls = {"if_statement", "for_statement", "while_statement", "try_statement", "if_expression", "when_expression", "conditional_expression"}
        while node and node != binding.scope:
            if node.type in controls:
                return True
            node = node.parent
        return False

    def _declared_types(self, syntax, binding, request):
        if not binding.annotation or not syntax.adapter.receiver_type_allowed(syntax, binding.annotation, request.name):
            return []
        call = replace(request.call, file_path=syntax.file.source.path, start_byte=binding.node.start_byte, end_byte=binding.node.end_byte)
        context = replace(request, file=syntax.file, call=call, owner=self.resolver.owner(call), name=binding.annotation, qualifier=None)
        types = self.resolver.named(context)
        types = syntax.adapter.qualify_class(self.resolver, context, types)
        if not types:
            types = self._qualified_type(context)
        types = self._type_symbols(types)
        if types is None:
            return []
        initialized = self._initializer_types(syntax, binding, request)
        if initialized is not None and self._conflicting_types(types, initialized):
            return []
        return [] if self._identity_overwritten(types, request) else types

    def _type_symbols(self, types):
        kinds = {"class", "interface", "struct", "trait", "type", "enum", "object"}
        if any(s.kind not in kinds | {"impl"} for s in types):
            return None
        return [s for s in types if s.kind in kinds]

    def _conflicting_types(self, types, initialized):
        return len(types) != 1 or len(initialized) != 1 or types[0].key != initialized[0].key

    def _initializer_types(self, syntax, binding, request):
        if binding.inferred or not syntax.adapter.validate_receiver_initializer:
            return None
        return self._value_types(syntax, binding, request)

    def _value_types(self, syntax, binding, request):
        value = field(binding.node, "right", "value")
        if value is None:
            return None
        if value.type == "identifier":
            call = replace(request.call, file_path=syntax.file.source.path,
                           start_byte=binding.node.start_byte, end_byte=binding.node.end_byte)
            context = replace(request, file=syntax.file, call=call, owner=self.resolver.owner(call), qualifier=text(value))
            return self._receiver_types(context) or []
        elif value.type in syntax.adapter.receiver_class_nodes:
            callee, receiver = syntax.adapter.call_target(value)
            annotation = text(callee) if receiver is None else text(receiver) + "." + text(callee)
            return self._declared_types(syntax, replace(binding, annotation=annotation, inferred=True), request)
        return []

    def _qualified_type(self, request):
        separator = "::" if "::" in request.name else "."
        qualifier, _, name = request.name.rpartition(separator)
        return self.resolver.qualified(replace(request, name=name, qualifier=qualifier)) if qualifier else []

    def _field_types(self, request):
        qualifier, _, name = request.qualifier.rpartition(".")
        types = self._receiver_types(replace(request, qualifier=qualifier))
        return self._fields(types, name, request)

    def _fields(self, types, name, request):
        if types is None:
            return None
        if len(types) != 1:
            return []
        parent = types[0]
        bindings = self._field_bindings(parent, name)
        if len(bindings) != 1:
            return []
        syntax = self.resolver.syntax[parent.file_path]
        if (self._path_written(request)
                or self._conditional(syntax, bindings[0])
                or self._reassigned(syntax, bindings[0], request.qualifier)):
            return []
        return self._declared_types(syntax, bindings[0], request)

    def _field_bindings(self, parent, name):
        return [b for b in self.bindings[parent.file_path] if b.member and b.name == name
                and parent.start_byte <= b.node.start_byte < parent.end_byte]

    def _static(self, request):
        return any(s.kind in {"method", "function"} and self.resolver.syntax[s.file_path].static(s)
                   for s in self.resolver.ancestors(request.owner))

    def _shadowed(self, syntax, binding, position):
        return any(name == binding.name and scope.start_byte <= position < scope.end_byte
                   and scope.end_byte - scope.start_byte <= binding.scope.end_byte - binding.scope.start_byte
                   and not (node.start_byte <= binding.node.start_byte < node.end_byte)
                   and node.type not in syntax.adapter.assignments
                   for name, scope, node in syntax.bindings)

    def _reassigned(self, syntax, binding: ReceiverBinding, qualifier):
        targets = {qualifier, binding.name}
        if binding.member:
            targets.update({"self." + binding.name, "this." + binding.name})
        return any(n != binding.node and n.type in syntax.adapter.assignments | syntax.adapter.receiver_updates
                   and self._write_names(syntax, n) & targets
                   and not self._field_initialization(syntax, binding, n)
                   and binding.scope.start_byte <= n.start_byte < binding.scope.end_byte
                   for n in syntax.nodes)

    def _field_initialization(self, syntax, binding, node):
        if binding.inferred or not binding.member or not syntax.adapter.trust_receiver_annotations:
            return False
        parent = node.parent
        while parent and parent != binding.scope:
            if parent.type == "constructor_declaration":
                return self._constructor_initialization(syntax, binding, (parent, node))
            parent = parent.parent
        return False

    def _constructor_initialization(self, syntax, binding, context):
        parent, node = context
        value = text(field(node, "right"))
        parameters = [b for b in self.bindings[syntax.file.source.path]
                      if not b.member and b.name == value and b.annotation == binding.annotation
                      and parent.start_byte <= b.node.start_byte < parent.end_byte]
        return len(parameters) == 1 and not self._reassigned(syntax, parameters[0], value)

    def _path_written(self, request, receiver=True):
        syntax = self.resolver.syntax[request.file.source.path]
        call = syntax.node(request.call.start_byte, request.call.end_byte)
        if call is None:
            return True
        scope = self._call_scope(call)
        nodes = [n for n in syntax.nodes if scope.start_byte <= n.start_byte < scope.end_byte]
        paths = self._expand_paths(syntax, nodes, {request.qualifier or ""})
        targets = (paths if receiver else set()) | {path + "." + request.name for path in paths}
        return self._targets_written(syntax, nodes, targets)

    def _call_scope(self, call):
        scope = call
        while scope.parent and scope.type not in FUNCTIONS:
            scope = scope.parent
        return scope

    def _targets_written(self, syntax, nodes, targets):
        return any(node.type in syntax.adapter.assignments | syntax.adapter.receiver_updates
                   and self._write_names(syntax, node) & targets for node in nodes)

    def _expand_paths(self, syntax, nodes, paths):
        # Propagate known lexical aliases, including aliases of a path's prefix.
        for _ in range(len(nodes)):
            expanded = self._expand_aliases(syntax, nodes, paths)
            if expanded == paths:
                break
            paths = expanded
        return paths

    def _expand_aliases(self, syntax, nodes, paths):
        expanded = set(paths)
        for node in nodes:
            if node.type in syntax.adapter.assignments | syntax.adapter.declarations:
                expanded.update(self._node_aliases(node, paths))
        return expanded

    def _node_aliases(self, node, paths):
        left = self._single_expression(field(node, "left", "name"))
        right = text(self._single_expression(field(node, "right", "value"))).replace(" ", "")
        if left is None or left.type != "identifier" or not right:
            return set()
        return self._alias_paths(paths, text(left), right)

    def _alias_paths(self, paths, left, right):
        return {alias + path[len(original):] for original, alias in ((right, left), (left, right))
                for path in paths if path == original or path.startswith(original + ".")}

    def _identity_overwritten(self, types, request):
        if len(types) != 1:
            return False
        syntax = self.resolver.syntax[request.file.source.path]
        return any(types[0].key in self._identity_write(syntax, node, request) for node in syntax.nodes)

    def _identity_write(self, syntax, node, request):
        if node.type not in syntax.adapter.member_writes:
            return set()
        target = text(syntax.adapter.write_target(node)).replace(" ", "")
        qualifier, _, member = target.rpartition(".")
        if member != request.name:
            return set()
        matches = self._write_identities(node, qualifier.removesuffix(".prototype"), request)
        return {s.key for s in matches}

    def _write_identities(self, node, qualifier, request):
        call = replace(request.call, start_byte=node.start_byte, end_byte=node.end_byte)
        context = replace(request, call=call, owner=self.resolver.owner(call), name=qualifier, qualifier=None)
        matches = self.resolver.named(context)
        return matches if matches else self._qualified_type(context)

    def _single_expression(self, node):
        if node is not None and node.type == "expression_list" and len(node.named_children) == 1:
            return node.named_children[0]
        return node

    def _write_names(self, syntax, node):
        target = self._single_expression(syntax.adapter.write_target(node))
        return names(target) | {text(target).replace(" ", "")}
