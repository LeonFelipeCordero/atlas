//! Language resolution dispatch, independent from syntax tree ownership.
use super::resolution::{Binding, CallableIdentity, ImportBindings, Modules};
use super::resolution_paths;
use super::{elixir, generic, go, java, javascript, kotlin, python, rust, typescript};
use crate::domain::models::{Call, ParsedFile, Symbol};
use crate::metrics::receiver_syntax::{self, ReceiverBinding};
use crate::metrics::resolution_contract::{CallTarget, DeclarationLookup, ImportRequest, ResolutionRequest};
use crate::metrics::resolution_syntax::Syntax;
use crate::metrics::resolver::CallResolver;
use crate::syntax::children;
use std::collections::BTreeMap;
use tree_sitter::Node;

#[derive(Clone, Debug)]
pub struct ResolutionAdapter {
    pub language: String,
}
impl ResolutionAdapter {
    pub fn receiver_bindings<'a>(&self, syntax: &'a Syntax, node: Node<'a>) -> Vec<ReceiverBinding<'a>> {
        match self.language.as_str() {
            "python" => receiver_syntax::python_bindings(syntax, node),
            "java" => receiver_syntax::java_bindings(syntax, node),
            "kotlin" => receiver_syntax::kotlin_bindings(syntax, node),
            "go" => receiver_syntax::go_bindings(syntax, node),
            "rust" => receiver_syntax::rust_bindings(syntax, node),
            _ if self.script() => receiver_syntax::script_bindings(syntax, node),
            _ => vec![],
        }
    }
    pub fn receiver_owner(&self, resolver: &CallResolver, request: &ResolutionRequest<'_>) -> Option<Vec<Symbol>> {
        (self.language == "rust").then(|| rust::receiver_owner(resolver, request))
    }
    pub fn instance_members(&self, resolver: &CallResolver, parent: &Symbol, name: &str) -> Vec<Symbol> {
        match self.language.as_str() {
            "rust" => rust::instance_members(resolver, parent, name),
            "go" => go::instance_members(resolver, parent, name),
            "python" => python::instance_members(resolver, parent, name),
            _ if self.script() => javascript::instance_members(resolver, parent, name),
            _ => resolver.member_declarations(parent, name),
        }
    }
    pub fn lexical_imports<'a>(&self, syntax: &'a Syntax) -> Vec<(String, Node<'a>)> {
        if self.language == "python" { python::lexical_imports(syntax) } else { vec![] }
    }
    pub fn binding<'a>(&self, syntax: &'a Syntax, node: Node<'a>, scope: Node<'a>) -> (Option<Node<'a>>, Node<'a>) {
        match self.language.as_str() {
            "python" => python::binding(self, syntax, (node, scope)),
            "java" => java::binding(self, syntax, (node, scope)),
            "kotlin" => kotlin::binding(self, syntax, (node, scope)),
            "go" => go::binding(self, syntax, (node, scope)),
            _ if self.script() => javascript::binding(self, syntax, (node, scope)),
            _ => generic::binding(self, syntax, (node, scope)),
        }
    }
    pub fn write_target<'a>(&self, node: Node<'a>) -> Option<Node<'a>> {
        if self.language == "kotlin" { kotlin::write_target(node) } else { generic::write_target(node) }
    }
    pub fn visible(&self, syntax: &Syntax, scope: Node<'_>, position: usize) -> bool {
        self.language != "python" || python::visible(syntax, scope, position)
    }
    pub fn declaration_allowed(&self, syntax: &Syntax, lookup: &DeclarationLookup<'_>) -> bool {
        self.language == "python" && python::declaration_allowed(syntax, lookup)
    }
    pub fn import_shadowed(&self, syntax: &Syntax, name: &str, position: usize) -> bool {
        self.language == "python" && python::import_shadowed(syntax, name, position)
    }
    pub fn is_import_node(&self, node: Node<'_>) -> bool {
        self.import_nodes().contains(node.kind())
    }
    pub fn is_import_node_with_source(&self, node: Node<'_>, source: &[u8]) -> bool {
        if self.language == "elixir" { elixir::is_import_node(node, source) } else { self.is_import_node(node) }
    }
    pub fn static_symbol(&self, syntax: &Syntax, symbol: &Symbol) -> bool {
        match self.language.as_str() {
            "python" => python::static_symbol(syntax, symbol),
            "rust" => rust::static_symbol(syntax, symbol).unwrap_or_else(|| self.default_static_symbol(syntax, symbol)),
            _ => self.default_static_symbol(syntax, symbol),
        }
    }
    pub fn default_static_symbol(&self, syntax: &Syntax, symbol: &Symbol) -> bool {
        if let Some(node) = syntax.node(symbol.start_byte, symbol.end_byte) {
            return children(node).iter().any(|c| {
                self.static_nodes().contains(c.kind())
                    || self.static_containers().contains(c.kind())
                        && syntax.text(*c).split_whitespace().any(|w| w == "static")
            });
        }
        symbol
            .signature
            .as_deref()
            .unwrap_or("")
            .split('(')
            .next()
            .unwrap_or("")
            .split_whitespace()
            .any(|w| w == "static")
    }
    pub fn paths(&self, source: &ParsedFile, name: &str, files: &[ParsedFile]) -> Vec<ParsedFile> {
        match self.language.as_str() {
            "python" => python::paths(source, name, files),
            _ if self.script() => javascript::paths(source, name, files),
            _ if name.starts_with('.') && name.contains('/') => resolution_paths::relative_targets(
                &ImportRequest { file: source, path: name.into(), position: None, source: String::new() },
                files,
                false,
            ),
            _ => resolution_paths::package_targets(name, files),
        }
    }
    pub fn import_files(&self, ctx: &ImportBindings, request: &ImportRequest<'_>) -> Vec<ParsedFile> {
        match self.language.as_str() {
            "python" => python::import_files(ctx, request),
            "rust" => rust::import_files(ctx, request),
            _ => ctx.path_files(request.file, &request.path),
        }
    }
    pub fn import_path(&self, source: &str) -> String {
        match self.language.as_str() {
            "python" => python::import_path(source),
            "java" => java::import_path(source),
            "kotlin" => kotlin::import_path(source),
            "go" => go::import_path(source),
            "rust" => rust::import_path(source),
            "elixir" => elixir::import_path(source),
            _ if self.script() => javascript::import_path(source),
            _ => resolution_paths::import_path(source),
        }
    }
    pub fn import_key(&self, ctx: &ImportBindings, request: &ImportRequest<'_>) -> Option<String> {
        match self.language.as_str() {
            "java" => java::import_key(ctx, request),
            "kotlin" => kotlin::import_key(ctx, request),
            "rust" => rust::import_key(ctx, request),
            "elixir" => elixir::import_key(ctx, request),
            _ => resolution_paths::path_target_key(&self.import_files(ctx, request)),
        }
    }
    pub fn import_targets(&self, ctx: &ImportBindings, request: &ImportRequest<'_>) -> Vec<(String, Option<String>)> {
        if self.language == "python" {
            python::import_targets(ctx, request)
        } else {
            vec![(request.path.clone(), self.import_key(ctx, request))]
        }
    }
    pub fn import_type_only(&self, node: Option<Node<'_>>) -> bool {
        self.script() && javascript::import_type_only(node)
    }
    pub fn import_item(&self, ctx: &ImportBindings, request: &ImportRequest<'_>) -> Vec<(String, Vec<Symbol>, bool)> {
        match self.language.as_str() {
            "python" => python::import_item(ctx, request),
            "java" => java::import_item(ctx, request),
            "kotlin" => kotlin::import_item(ctx, request),
            "go" => go::import_item(ctx, request),
            "rust" => rust::import_item(ctx, request),
            "elixir" => elixir::import_item(ctx, request),
            _ if self.script() => javascript::import_item(ctx, request),
            _ => resolution_paths::namespace_binding(&request.source, &request.path)
                .filter(|s| !s.is_empty())
                .map(|name| {
                    vec![(
                        name,
                        self.import_files(ctx, request).iter().flat_map(resolution_paths::top_symbols).collect(),
                        true,
                    )]
                })
                .unwrap_or_default(),
        }
    }
    pub fn namespace_members(
        &self,
        ctx: &ImportBindings,
        request: &ImportRequest<'_>,
        targets: &[Symbol],
    ) -> Option<BTreeMap<String, Vec<Symbol>>> {
        if self.script() { Some(javascript::namespace_members(ctx, request, targets)) } else { None }
    }
    pub fn module_bindings(&self, ctx: &ImportBindings, file: &ParsedFile, source_length: usize) -> Vec<Binding> {
        if self.language == "rust" { rust::module_bindings(ctx, file, source_length) } else { vec![] }
    }
    pub fn members(&self, ctx: &ImportBindings, request: &ImportRequest<'_>, name: &str) -> Vec<Symbol> {
        match self.language.as_str() {
            "rust" => rust::members(ctx, request, name),
            _ if self.script() => javascript::members(ctx, request, name),
            _ => {
                let targets = self.import_files(ctx, request);
                if targets.len() == 1 {
                    resolution_paths::top_symbols(&targets[0]).into_iter().filter(|s| s.name == name).collect()
                } else {
                    vec![]
                }
            }
        }
    }
    pub fn module_identity(&self, file: &ParsedFile, symbol: &Symbol, syntax: &Syntax) -> String {
        match self.language.as_str() {
            "java" | "kotlin" => java::module_identity(file, symbol, syntax),
            "elixir" => elixir::module_identity(file, symbol, syntax),
            _ => String::new(),
        }
    }
    pub fn same_package(&self, modules: &Modules, source: &ParsedFile, name: &str) -> Vec<Symbol> {
        match self.language.as_str() {
            "java" | "kotlin" => java::same_package(modules, source, name),
            "go" => go::same_package(modules, source, name),
            _ => vec![],
        }
    }
    pub fn qualify_class(
        &self,
        resolver: &CallResolver,
        request: &ResolutionRequest<'_>,
        matches: Vec<Symbol>,
    ) -> Vec<Symbol> {
        match self.language.as_str() {
            "java" | "kotlin" => java::qualify_class(resolver, request, matches),
            "rust" => rust::qualify_class(resolver, request, matches),
            _ => matches,
        }
    }
    pub fn qualified(&self, resolver: &CallResolver, request: &ResolutionRequest<'_>) -> Vec<Symbol> {
        match self.language.as_str() {
            "rust" => rust::qualified(resolver, request),
            "elixir" => elixir::qualified(resolver, request),
            _ => vec![],
        }
    }
    pub fn local_namespace(&self, resolver: &CallResolver, local: &[Symbol]) -> bool {
        self.language == "rust" && rust::local_namespace(resolver, local)
    }
    pub fn static_member(&self, parent: &Symbol) -> bool {
        if self.language == "kotlin" { kotlin::static_member(parent) } else { parent.kind == "module" }
    }
    pub fn member_overwritten(&self, syntax: &Syntax, parent: &Symbol, name: &str) -> bool {
        if self.script() {
            javascript::member_overwritten(syntax, parent, name)
        } else {
            self.default_member_overwritten(syntax, parent, name)
        }
    }
    pub fn default_member_overwritten(&self, syntax: &Syntax, parent: &Symbol, name: &str) -> bool {
        syntax.member_rebound(&parent.name, name) || syntax.class_rebound(parent, name)
    }
    pub fn call_target<'a>(&self, node: Option<Node<'a>>) -> (Option<Node<'a>>, Option<Node<'a>>) {
        match self.language.as_str() {
            "java" => java::call_target(self, node),
            "kotlin" => kotlin::call_target(self, node),
            "go" => go::call_target(self, node),
            "rust" => node
                .and_then(|node| rust::call_target(self, node))
                .unwrap_or_else(|| generic::default_call_target(self, node)),
            _ if self.script() => javascript::call_target(self, node),
            _ if !self.dedicated() => generic::call_target(self, node),
            _ => generic::default_call_target(self, node),
        }
    }
    pub fn normalized_call<'a>(
        &self,
        syntax: &Syntax,
        call: &Call,
        (callee, receiver): (Option<Node<'a>>, Option<Node<'a>>),
    ) -> CallTarget<'a> {
        if self.script() && call.relationship == "REFERENCES" {
            return CallTarget { callee, receiver, name: call.name.clone(), qualifier: call.qualifier.clone() };
        }
        let name = callee.map(|n| syntax.text(n)).filter(|s| !s.is_empty()).unwrap_or_else(|| call.name.clone());
        CallTarget {
            callee,
            receiver,
            name,
            qualifier: receiver.map(|n| syntax.text(n)).or_else(|| call.qualifier.clone()),
        }
    }
    pub fn receiver_type_allowed(&self, syntax: &Syntax, name: &str, member: &str) -> bool {
        !syntax.member_rebound(name, member)
            && (!self.script() || !syntax.member_rebound(&format!("{name}.prototype"), member))
    }
    pub fn receiver_class_allowed(&self, syntax: &Syntax, callee: Option<Node<'_>>, member: &str) -> bool {
        if self.script() {
            javascript::receiver_class_allowed(syntax, callee, member)
        } else if !self.dedicated() {
            generic::receiver_class_allowed(syntax, callee, member)
        } else {
            true
        }
    }
    pub fn receiver_rejected(&self, receiver: Option<Node<'_>>, qualifier: Option<&str>) -> bool {
        self.language == "rust" && rust::receiver_rejected(receiver, qualifier)
    }
    pub fn implicit_receiver(&self, resolver: &CallResolver, request: &ResolutionRequest<'_>, method: &Symbol) -> bool {
        match self.language.as_str() {
            "python" => python::implicit_receiver(resolver, request, method),
            _ if self.script() => javascript::implicit_receiver(resolver, request, method),
            _ => true,
        }
    }
    pub fn select(
        &self,
        identity: &CallableIdentity,
        request: &ResolutionRequest<'_>,
        matches: Vec<Symbol>,
    ) -> Vec<Symbol> {
        match self.language.as_str() {
            "python" => python::select(identity, request, matches),
            "typescript" | "tsx" => typescript::select(identity, request, matches),
            "javascript" | "jsx" => javascript::select(identity, request, matches),
            "java" | "kotlin" => java::select(identity, request, matches),
            "elixir" => elixir::select(identity, request, matches),
            _ if matches.len() == 1 => matches,
            _ => vec![],
        }
    }
    pub fn inheritance(
        &self,
        resolver: &CallResolver,
        request: &ResolutionRequest<'_>,
        matches: Vec<Symbol>,
    ) -> Vec<Symbol> {
        if self.jvm() {
            return java::inheritance(resolver, request, matches);
        }
        default_inheritance(resolver, request, matches)
    }
}
pub fn default_inheritance(
    resolver: &CallResolver,
    request: &ResolutionRequest<'_>,
    matches: Vec<Symbol>,
) -> Vec<Symbol> {
    if let Some((qualifier, terminal)) = request.name.rsplit_once('.')
        && let Some(binding) = resolver.imports.get(request.file, qualifier, request.call.start_byte)
        && binding.namespace
        && resolver.lexical(request.file, qualifier, request.owner).is_empty()
        && !resolver.syntax[&request.file.source.path].shadowed(qualifier, request.call.start_byte, &[])
    {
        return binding.targets.into_iter().filter(|s| s.name == terminal).collect();
    }
    if request.name.contains("::") { resolver.class_named(request) } else { matches }
}
