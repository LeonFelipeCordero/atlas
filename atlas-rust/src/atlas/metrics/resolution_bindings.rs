//! Ordered lexical binding descriptors and their name index contain no borrowed AST nodes.
use std::collections::BTreeMap;
use tree_sitter::Node;

pub fn walk_range(root: Node<'_>, span: (usize, usize)) -> Vec<Node<'_>> {
    let mut result = Vec::new();
    let mut pending = vec![root];
    while let Some(node) = pending.pop() {
        if outside_span(node, span) {
            continue;
        }
        if span.0 <= node.start_byte() {
            result.push(node);
        }
        let mut cursor = node.walk();
        let children: Vec<_> = node.named_children(&mut cursor).collect();
        pending.extend(children.into_iter().rev());
    }
    result
}
fn outside_span(node: Node<'_>, span: (usize, usize)) -> bool {
    node.end_byte() < span.0 || node.start_byte() >= span.1
}

/// A tree-relative node handle remains valid across shared syntax cache clones.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NodeRef(pub usize);

pub struct StoredBinding {
    pub name: String,
    pub scope: NodeRef,
    pub node: NodeRef,
    pub scope_span: (usize, usize),
    pub node_span: (usize, usize),
}
impl StoredBinding {
    pub fn visible_at(&self, position: usize) -> bool {
        self.scope_span.0 <= position && position < self.scope_span.1
    }
    pub fn contained_in(&self, span: (usize, usize)) -> bool {
        span.0 <= self.node_span.0 && self.node_span.1 <= span.1
    }
}

#[derive(Default)]
pub struct BindingIndex {
    pub entries: Vec<StoredBinding>,
    names: BTreeMap<String, Vec<usize>>,
}
impl FromIterator<StoredBinding> for BindingIndex {
    fn from_iter<T: IntoIterator<Item = StoredBinding>>(iter: T) -> Self {
        let entries: Vec<_> = iter.into_iter().collect();
        let mut names: BTreeMap<String, Vec<usize>> = BTreeMap::new();
        for (index, binding) in entries.iter().enumerate() {
            names.entry(binding.name.clone()).or_default().push(index);
        }
        Self { entries, names }
    }
}
impl BindingIndex {
    pub fn named(&self, name: &str) -> impl Iterator<Item = &StoredBinding> {
        self.names.get(name).into_iter().flatten().map(|index| &self.entries[*index])
    }
}
