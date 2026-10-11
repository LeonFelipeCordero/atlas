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
            if self._path_written(request):
                return []
            types = syntax.adapter.receiver_owner(self.resolver, request)
            if types is not None:
                return types if qualifier == root else self._fields(types, qualifier.partition(".")[2], request)
        if qualifier.count(".") > 1 or "." in qualifier and not implicit:
            return self._field_types(request)
        return self._lexical_types(request, qualifier, syntax)

    def _lexical_types(self, request, qualifier, syntax):
        bindings = self.bindings[request.file.source.path]
        member = "." in qualifier and qualifier.split(".")[0] in syntax.adapter.self_qualifiers
        if member and not self.resolver._self_class(replace(request, qualifier=qualifier.split(".")[0])):
            return []
        name = qualifier.split(".")[-1] if member else qualifier
        if not name or "." in name or "::" in name:
            return None
        candidates = self._candidates(syntax, bindings, name, member, request.call.start_byte)
        if not candidates:
            return None
        candidates = self._nearest(candidates)
        if len(candidates) != 1:
            return []
        binding = candidates[0]
        if not member and self._shadowed(syntax, binding, request.call.start_byte):
            return []
        if self._unsafe(syntax, binding, request) or self._path_written(request, receiver=False):
            return []
        return self._declared_types(syntax, binding, request)

    def _nearest(self, candidates):
        size = min(b.scope.end_byte - b.scope.start_byte for b in candidates)
        candidates = [b for b in candidates if b.scope.end_byte - b.scope.start_byte == size]
        declared = [b for b in candidates if not b.inferred]
        return declared or candidates

    def _candidates(self, syntax, bindings, name, member, position):
        return [b for b in bindings if b.name == name and self._visible(syntax, b, member, position)]

    def _visible(self, syntax, binding, member, position):
        if member:
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
        kinds = {"class", "interface", "struct", "trait", "type", "enum", "object"}
        if any(s.kind not in kinds | {"impl"} for s in types):
            return []
        types = [s for s in types if s.kind in kinds]
        if self._initializer_conflicts(syntax, binding, request, types):
            return []
        return [] if self._identity_overwritten(types, request) else types

    def _initializer_conflicts(self, syntax, binding, request, types):
        if binding.inferred or not syntax.adapter.validate_receiver_initializer:
            return False
        value = field(binding.node, "right", "value")
        if value is None:
            return False
        if value.type == "identifier":
            call = replace(request.call, file_path=syntax.file.source.path,
                           start_byte=binding.node.start_byte, end_byte=binding.node.end_byte)
            context = replace(request, file=syntax.file, call=call, owner=self.resolver.owner(call), qualifier=text(value))
            initialized = self._receiver_types(context) or []
        elif value.type in syntax.adapter.receiver_class_nodes:
            callee, receiver = syntax.adapter.call_target(value)
            annotation = text(callee) if receiver is None else text(receiver) + "." + text(callee)
            initialized = self._declared_types(syntax, replace(binding, annotation=annotation, inferred=True), request)
        else:
            initialized = []
        return len(types) != 1 or len(initialized) != 1 or types[0].key != initialized[0].key

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
        bindings = [b for b in self.bindings[parent.file_path] if b.member and b.name == name
                    and parent.start_byte <= b.node.start_byte < parent.end_byte]
        if len(bindings) != 1:
            return []
        syntax = self.resolver.syntax[parent.file_path]
        if (self._path_written(request)
                or self._conditional(syntax, bindings[0])
                or self._reassigned(syntax, bindings[0], request.qualifier)):
            return []
        return self._declared_types(syntax, bindings[0], request)

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
                value = text(field(node, "right"))
                parameters = [b for b in self.bindings[syntax.file.source.path]
                              if not b.member and b.name == value and b.annotation == binding.annotation
                              and parent.start_byte <= b.node.start_byte < parent.end_byte]
                return len(parameters) == 1 and not self._reassigned(syntax, parameters[0], value)
            parent = parent.parent
        return False

    def _path_written(self, request, receiver=True):
        syntax = self.resolver.syntax[request.file.source.path]
        call = syntax.node(request.call.start_byte, request.call.end_byte)
        if call is None:
            return True
        scope = call
        while scope.parent and scope.type not in FUNCTIONS:
            scope = scope.parent
        paths = {request.qualifier or ""}
        nodes = [n for n in syntax.nodes if scope.start_byte <= n.start_byte < scope.end_byte]
        # Propagate known lexical aliases, including aliases of a path's prefix.
        for _ in range(len(nodes)):
            expanded = set(paths)
            for node in nodes:
                if node.type not in syntax.adapter.assignments | syntax.adapter.declarations:
                    continue
                left = self._single_expression(field(node, "left", "name"))
                right = text(self._single_expression(field(node, "right", "value"))).replace(" ", "")
                if left is None or left.type != "identifier" or not right:
                    continue
                expanded.update(self._alias_paths(paths, text(left), right))
            if expanded == paths:
                break
            paths = expanded
        targets = (paths if receiver else set()) | {path + "." + request.name for path in paths}
        return any(node.type in syntax.adapter.assignments | syntax.adapter.receiver_updates
                   and self._write_names(syntax, node) & targets for node in nodes)

    def _alias_paths(self, paths, left, right):
        return {alias + path[len(original):] for original, alias in ((right, left), (left, right))
                for path in paths if path == original or path.startswith(original + ".")}

    def _identity_overwritten(self, types, request):
        if len(types) != 1:
            return False
        syntax = self.resolver.syntax[request.file.source.path]
        for node in syntax.nodes:
            if node.type not in syntax.adapter.member_writes:
                continue
            target = text(syntax.adapter.write_target(node)).replace(" ", "")
            qualifier, _, member = target.rpartition(".")
            if member != request.name:
                continue
            qualifier = qualifier.removesuffix(".prototype")
            call = replace(request.call, start_byte=node.start_byte, end_byte=node.end_byte)
            context = replace(request, call=call, owner=self.resolver.owner(call), name=qualifier, qualifier=None)
            matches = self.resolver.named(context)
            if not matches:
                matches = self._qualified_type(context)
            if any(s.key == types[0].key for s in matches):
                return True
        return False

    def _single_expression(self, node):
        if node is not None and node.type == "expression_list" and len(node.named_children) == 1:
            return node.named_children[0]
        return node

    def _write_names(self, syntax, node):
        target = self._single_expression(syntax.adapter.write_target(node))
        return names(target) | {text(target).replace(" ", "")}
