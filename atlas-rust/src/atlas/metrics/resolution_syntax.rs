//! Replacement-decoded syntax and conservative lexical binding checks.
use super::adapters::resolution_policy::ResolutionAdapter;
use super::resolution_contract::{DeclarationLookup, FUNCTIONS};
use crate::domain::models::{ParsedFile, Symbol};
use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::sync::{Arc, Mutex, OnceLock};
use tree_sitter::{Node, Tree};

pub const PARAMETERS: &[&str] = &[
    "parameters",
    "formal_parameters",
    "parameter_list",
    "function_value_parameters",
    "lambda_parameters",
    "closure_parameters",
    "inferred_parameters",
];
pub const IDENTIFIERS: &[&str] =
    &["identifier", "simple_identifier", "field_identifier", "shorthand_property_identifier_pattern"];

pub fn field<'a>(node: Node<'a>, fields: &[&str]) -> Option<Node<'a>> {
    fields.iter().find_map(|name| node.child_by_field_name(name))
}
pub fn children(node: Node<'_>) -> Vec<Node<'_>> {
    let mut cursor = node.walk();
    node.named_children(&mut cursor).collect()
}
pub fn walk(node: Node<'_>) -> Vec<Node<'_>> {
    let mut result = Vec::new();
    let mut pending = vec![node];
    while let Some(node) = pending.pop() {
        result.push(node);
        pending.extend(children(node).into_iter().rev());
    }
    result
}
pub fn names(node: Option<Node<'_>>, source: &[u8]) -> BTreeSet<String> {
    let Some(node) = node else {
        return BTreeSet::new();
    };
    if IDENTIFIERS.contains(&node.kind()) {
        return [String::from_utf8_lossy(&source[node.byte_range()]).into_owned()].into();
    }
    if ["attribute", "member_expression", "field_expression", "subscript"].contains(&node.kind()) {
        return BTreeSet::new();
    }
    if node.kind() == "pair_pattern" {
        return names(field(node, &["value"]), source);
    }
    structured_names(node, source)
}
fn structured_names(node: Node<'_>, source: &[u8]) -> BTreeSet<String> {
    let mut cursor = node.walk();
    let declared: Vec<_> = node.children_by_field_name("name", &mut cursor).collect();
    if node.kind() == "parameter_declaration" && !declared.is_empty() {
        return declared.into_iter().flat_map(|n| names(Some(n), source)).collect();
    }
    if let Some(target) = field(node, &["pattern", "name", "declarator", "left"]) {
        return names(Some(target), source);
    }
    if ["typed_parameter", "default_parameter", "typed_default_parameter", "parameter", "variable_declaration"]
        .contains(&node.kind())
    {
        return names(children(node).into_iter().find(|n| IDENTIFIERS.contains(&n.kind())), source);
    }
    if node.kind().contains("pattern")
        || PARAMETERS.contains(&node.kind())
        || [
            "tuple",
            "list",
            "expression_list",
            "directly_assignable_expression",
            "parenthesized_declarator",
            "multi_variable_declaration",
        ]
        .contains(&node.kind())
    {
        return children(node).into_iter().flat_map(|n| names(Some(n), source)).collect();
    }
    BTreeSet::new()
}

/// A tree-relative node handle remains valid when an owned syntax cache is cloned.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NodeRef(pub usize);
pub type ReceiverScopeData = Vec<(Vec<NodeRef>, BTreeSet<String>)>;

#[derive(Default)]
struct NodeIndex {
    node_paths: BTreeMap<usize, NodeRef>,
    path_arena: Vec<(Option<usize>, u32)>,
    spans: BTreeMap<(usize, usize), NodeRef>,
}
impl NodeIndex {
    fn new(root: Option<Node<'_>>) -> Self {
        let mut result = Self::default();
        let Some(root) = root else { return result };
        let mut pending = vec![(root, None, 0)];
        while let Some((node, parent, child_index)) = pending.pop() {
            let index = result.path_arena.len();
            result.path_arena.push((parent, child_index));
            result.node_paths.insert(node.id(), NodeRef(index));
            pending.extend(child_paths(node, index));
        }
        result.spans = walk(root)
            .into_iter()
            .map(|node| ((node.start_byte(), node.end_byte()), result.node_paths[&node.id()]))
            .collect();
        result
    }
}
fn child_paths(node: Node<'_>, parent: usize) -> Vec<(Node<'_>, Option<usize>, u32)> {
    (0..node.child_count()).rev().map(|index| (node.child(index).unwrap(), Some(parent), index)).collect()
}
#[derive(Default)]
struct SyntaxCache {
    tree: OnceLock<Option<Tree>>,
    index: OnceLock<NodeIndex>,
    imports: OnceLock<Vec<(String, NodeRef)>>,
    bindings: OnceLock<Vec<(String, NodeRef, NodeRef)>>,
    written_members: OnceLock<HashSet<String>>,
}

#[derive(Clone)]
pub struct Syntax {
    pub language: String,
    pub file: Arc<ParsedFile>,
    pub adapter: ResolutionAdapter,
    pub source: Arc<Vec<u8>>,
    cache: Arc<SyntaxCache>,
    pub receiver_scope_cache: Arc<Mutex<BTreeMap<String, ReceiverScopeData>>>,
}
impl Syntax {
    pub fn new(file: &ParsedFile, adapter: ResolutionAdapter) -> Self {
        let source = String::from_utf8_lossy(&file.source.source).into_owned().into_bytes();
        Self {
            language: file.source.language.clone(),
            file: Arc::new(file.clone()),
            adapter,
            source: Arc::new(source),
            cache: Arc::new(SyntaxCache::default()),
            receiver_scope_cache: Arc::new(Mutex::new(BTreeMap::new())),
        }
    }
    pub fn root(&self) -> Option<Node<'_>> {
        self.cache.tree.get_or_init(|| self.parse_tree()).as_ref().map(Tree::root_node)
    }
    fn parse_tree(&self) -> Option<Tree> {
        let language = tree_sitter_language_pack::get_language(&self.language).ok()?;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&language).ok()?;
        parser.parse(self.source.as_slice(), None)
    }
    fn index(&self) -> &NodeIndex {
        self.cache.index.get_or_init(|| NodeIndex::new(self.root()))
    }
    pub fn reference(&self, node: Node<'_>) -> NodeRef {
        *self.index().node_paths.get(&node.id()).expect("Node must belong to this syntax tree")
    }
    pub fn dereference(&self, reference: &NodeRef) -> Option<Node<'_>> {
        let paths = &self.index().path_arena;
        let mut indices = Vec::new();
        let mut index = reference.0;
        while let Some((Some(parent), child)) = paths.get(index) {
            indices.push(*child);
            index = *parent;
        }
        paths.get(index)?;
        let mut node = self.root()?;
        for child in indices.into_iter().rev() {
            node = node.child(child)?;
        }
        Some(node)
    }
    pub fn nodes(&self) -> Vec<Node<'_>> {
        self.root().map(walk).unwrap_or_default()
    }
    pub fn text(&self, node: Node<'_>) -> String {
        String::from_utf8_lossy(&self.source[node.byte_range()]).into_owned()
    }
    pub fn node(&self, start: usize, end: usize) -> Option<Node<'_>> {
        self.index().spans.get(&(start, end)).and_then(|reference| self.dereference(reference))
    }
    pub fn scope<'a>(&'a self, node: Node<'a>) -> Node<'a> {
        let mut parent = node.parent();
        while let Some(candidate) = parent {
            if self.adapter.scopes().contains(&candidate.kind()) {
                return candidate;
            }
            parent = candidate.parent();
        }
        self.root().unwrap_or(node)
    }
    pub fn imports(&self) -> Vec<(String, Node<'_>)> {
        self.cache
            .imports
            .get_or_init(|| {
                self.adapter
                    .lexical_imports(self)
                    .into_iter()
                    .map(|(name, node)| (name, self.reference(node)))
                    .collect()
            })
            .iter()
            .filter_map(|(name, node)| Some((name.clone(), self.dereference(node)?)))
            .collect()
    }
    pub fn bindings(&self) -> Vec<(String, Node<'_>, Node<'_>)> {
        self.cache
            .bindings
            .get_or_init(|| {
                self.nodes()
                    .into_iter()
                    .flat_map(|node| self.node_bindings(node))
                    .map(|(name, scope, node)| (name, self.reference(scope), self.reference(node)))
                    .collect()
            })
            .iter()
            .filter_map(|(name, scope, node)| Some((name.clone(), self.dereference(scope)?, self.dereference(node)?)))
            .collect()
    }
    fn node_bindings<'a>(&'a self, node: Node<'a>) -> Vec<(String, Node<'a>, Node<'a>)> {
        let scope = self.scope(node);
        if PARAMETERS.contains(&node.kind()) {
            return children(node)
                .into_iter()
                .flat_map(|child| names(Some(child), &self.source))
                .map(|name| (name, scope, node))
                .collect();
        }
        if self.adapter.single_parameter_functions().contains(&node.kind()) {
            return field(node, &["parameter", "parameters"])
                .filter(|n| IDENTIFIERS.contains(&n.kind()))
                .map(|n| vec![(self.text(n), node, n)])
                .unwrap_or_default();
        }
        let (target, scope) = self.adapter.binding(self, node, scope);
        names(target, &self.source).into_iter().map(|name| (name, scope, node)).collect()
    }
    pub fn visible(&self, scope: Node<'_>, position: usize) -> bool {
        scope.start_byte() <= position && position < scope.end_byte() && self.adapter.visible(self, scope, position)
    }
    fn declaration_allowed(&self, lookup: &DeclarationLookup<'_>, allowed: &[Symbol]) -> bool {
        allowed.iter().any(|s| lookup.node.start_byte() <= s.start_byte && s.end_byte <= lookup.node.end_byte())
            || self.adapter.declaration_allowed(self, lookup)
    }
    pub fn shadowed(&self, name: &str, position: usize, allowed: &[Symbol]) -> bool {
        if self.adapter.import_shadowed(self, name, position) {
            return true;
        }
        self.bindings().into_iter().any(|(binding, scope, node)| {
            binding == name
                && self.visible(scope, position)
                && !self.declaration_allowed(&DeclarationLookup { name, node, position }, allowed)
        })
    }
    pub fn import_node(&self, line: usize, source: Option<&str>) -> Option<Node<'_>> {
        let mut candidates: Vec<_> = self
            .nodes()
            .into_iter()
            .filter(|n| n.start_position().row + 1 == line && self.adapter.is_import_node_with_source(*n, &self.source))
            .collect();
        if let Some(source) = source {
            let exact: Vec<_> = candidates
                .iter()
                .copied()
                .filter(|n| self.text(*n).trim().trim_end_matches(';') == source.trim().trim_end_matches(';'))
                .collect();
            if !exact.is_empty() {
                candidates = exact;
            }
        }
        if candidates.len() == 1 { Some(candidates[0]) } else { None }
    }
    pub fn import_scope(&self, line: usize, source: Option<&str>) -> Option<Node<'_>> {
        self.import_node(line, source).map(|n| self.scope(n)).or_else(|| self.root())
    }
    pub fn class_rebound(&self, symbol: &Symbol, name: &str) -> bool {
        self.bindings().into_iter().any(|(binding, _, node)| {
            if binding != name || self.adapter.rebound_declarations().contains(&node.kind()) {
                return false;
            }
            let mut parent = node.parent();
            while let Some(candidate) = parent {
                if FUNCTIONS.contains(&candidate.kind())
                    || ["class_definition", "class_declaration"].contains(&candidate.kind())
                {
                    return candidate.start_byte() == symbol.start_byte && candidate.end_byte() == symbol.end_byte;
                }
                parent = candidate.parent();
            }
            false
        })
    }
    pub fn written_members(&self) -> &HashSet<String> {
        self.cache.written_members.get_or_init(|| {
            self.nodes()
                .into_iter()
                .filter(|n| self.adapter.member_writes().contains(&n.kind()))
                .map(|n| self.adapter.write_target(n).map(|n| self.text(n)).unwrap_or_default().replace(' ', ""))
                .collect()
        })
    }
    pub fn member_rebound(&self, qualifier: &str, name: &str) -> bool {
        self.written_members().contains(&format!("{qualifier}.{name}"))
    }
    pub fn static_symbol(&self, symbol: &Symbol) -> bool {
        self.adapter.static_symbol(self, symbol)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::models::SourceFile;
    use crate::metrics::adapters::get_resolution_adapter;
    use std::path::PathBuf;

    fn parsed(language: &str, source: &[u8]) -> ParsedFile {
        ParsedFile {
            source: SourceFile {
                path: format!("a.{language}"),
                absolute_path: PathBuf::from(format!("a.{language}")),
                language: language.into(),
                source: source.to_vec(),
            },
            content_hash: String::new(),
            parse_error: None,
            symbols: vec![],
            imports: vec![],
            calls: vec![],
            inheritances: vec![],
        }
    }
    fn syntax(source: &[u8]) -> Syntax {
        Syntax::new(&parsed("python", source), get_resolution_adapter("python"))
    }
    #[test]
    fn constructors_and_clones_defer_parsing_for_every_language() {
        for language in ["python", "rust", "java", "javascript", "json", "csv"] {
            let syntax = Syntax::new(&parsed(language, b"x"), get_resolution_adapter(language));
            let cloned = syntax.clone();
            assert!(syntax.cache.tree.get().is_none());
            assert!(syntax.cache.index.get().is_none());
            assert!(Arc::ptr_eq(&syntax.cache, &cloned.cache));
            assert!(Arc::ptr_eq(&syntax.file, &cloned.file));
            assert!(Arc::ptr_eq(&syntax.source, &cloned.source));
            assert_eq!(syntax.root().unwrap().id(), cloned.root().unwrap().id());
            assert!(syntax.cache.index.get().is_none());
            let reference = syntax.reference(syntax.root().unwrap());
            assert!(std::ptr::eq(syntax.index(), cloned.index()));
            assert_eq!(cloned.dereference(&reference), syntax.root());
        }
    }
    #[test]
    fn cached_declarations_and_members_share_the_same_tree_across_clones() {
        let syntax = syntax(b"import sys\ndef f(value):\n return value\nservice.run = f\n");
        let declared = syntax.bindings();
        let imports = syntax.imports();
        let written = syntax.written_members();
        let cloned = syntax.clone();
        assert!(!declared.is_empty());
        assert!(!imports.is_empty());
        assert!(written.contains("service.run"));
        assert!(std::ptr::eq(written, cloned.written_members()));
        assert!(std::ptr::eq(syntax.cache.bindings.get().unwrap(), cloned.cache.bindings.get().unwrap()));
        assert!(std::ptr::eq(syntax.cache.imports.get().unwrap(), cloned.cache.imports.get().unwrap()));
        assert_eq!(declared, cloned.bindings());
        assert_eq!(imports, cloned.imports());
    }
    #[test]
    fn csv_resolution_does_not_materialize_a_tree_but_explicit_root_parses_real_data() {
        use crate::domain::models::ParsedRepository;
        use crate::metrics::resolver::CallResolver;
        let file = crate::parsing::parser::parse_file(parsed("csv", b"name,value\na,1\nb,2\n").source).unwrap();
        assert!(file.symbols.is_empty());
        assert!(file.calls.is_empty());
        let path = file.source.path.clone();
        let resolver = CallResolver::new(&ParsedRepository { files: vec![file] });
        let syntax = &resolver.syntax[&path];
        let contexts = [
            &resolver.modules.syntax,
            &resolver.imports.syntax,
            &resolver.imports.modules.syntax,
            &resolver.identity.syntax,
        ];
        assert!(contexts.iter().all(|context| Arc::ptr_eq(&syntax.cache, &context[&path].cache)));
        assert!(syntax.cache.tree.get().is_none());
        assert!(syntax.cache.index.get().is_none());
        assert!(crate::metrics::resolver::resolve_connections(&resolver.repository).unwrap().connections.is_empty());
        assert!(syntax.cache.tree.get().is_none());
        let root = syntax.root().unwrap();
        assert_eq!(root.end_byte(), syntax.source.len());
        assert!(root.named_child_count() > 0);
        assert!(syntax.cache.index.get().is_none());
        assert!(syntax.node(0, syntax.source.len()).is_some());
        assert!(syntax.cache.index.get().is_some());
    }
    #[test]
    fn replacement_decoding_and_exact_span_lookup() {
        let syntax = syntax(b"value = '\xff'\n");
        assert_eq!(syntax.source.as_slice(), "value = '\u{fffd}'\n".as_bytes());
        let identifier = syntax.nodes().into_iter().find(|n| n.kind() == "identifier").unwrap();
        assert_eq!(syntax.node(identifier.start_byte(), identifier.end_byte()), Some(identifier));
        assert!(syntax.node(identifier.start_byte(), identifier.end_byte() - 1).is_none());
    }
    #[test]
    fn stable_node_handles_preserve_duplicate_spans_across_clones() {
        let syntax = syntax(b"x");
        let original = syntax.root().unwrap();
        let duplicates: Vec<_> = syntax.nodes().into_iter().filter(|node| node.byte_range() == (0..1)).collect();
        assert_eq!(duplicates.iter().map(|node| node.kind()).collect::<Vec<_>>(), ["module", "identifier"]);
        let reference = syntax.reference(original);
        let clone = syntax.clone();
        let restored = clone.dereference(&reference).unwrap();
        assert_eq!(restored.kind(), "module");
        assert_eq!(clone.reference(clone.root().unwrap()).0, 0);
        assert_eq!(clone.reference(restored).0, reference.0);
        assert_eq!(syntax.node(0, 1).unwrap().kind(), "identifier");
    }
    #[test]
    fn import_source_disambiguates_same_line_and_unknown_source_keeps_ambiguity() {
        let syntax = syntax(b"import first; import second\n");
        assert!(syntax.import_node(1, None).is_none());
        assert!(syntax.import_node(1, Some("import unknown")).is_none());
        assert_eq!(syntax.text(syntax.import_node(1, Some(" import first; ")).unwrap()), "import first");
        assert_eq!(syntax.import_scope(2, None), syntax.root());
    }
    #[test]
    fn nearest_parent_scope_and_half_open_visibility() {
        let syntax = syntax(b"def outer():\n def inner(value):\n  return value\n");
        let inner = syntax.nodes().into_iter().filter(|n| n.kind() == "function_definition").nth(1).unwrap();
        let outer = syntax.scope(inner);
        assert_eq!(outer.kind(), "function_definition");
        assert!(syntax.visible(inner, inner.start_byte()));
        assert!(!syntax.visible(inner, inner.end_byte()));
        assert!(syntax.shadowed("value", inner.end_byte() - 1, &[]));
        assert!(!syntax.shadowed("value", 0, &[]));
    }
    #[test]
    fn member_write_matching_removes_only_literal_spaces_and_keeps_full_name() {
        let syntax = syntax(b"service . run = replacement\n");
        assert!(syntax.member_rebound("service", "run"));
        assert!(!syntax.member_rebound("service", "runner"));
    }
    #[test]
    fn pattern_names_exclude_types_and_members() {
        let source = b"def f(x: int, y=1):\n a.b = 1\n";
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&tree_sitter_language_pack::get_language("python").unwrap()).unwrap();
        let tree = parser.parse(source, None).unwrap();
        let nodes = walk(tree.root_node());
        let parameters = nodes.iter().find(|n| n.kind() == "parameters").unwrap();
        assert_eq!(names(Some(*parameters), source), ["x".to_owned(), "y".to_owned()].into());
        let attribute = nodes.iter().find(|n| n.kind() == "attribute").unwrap();
        assert!(names(Some(*attribute), source).is_empty());
    }
}
