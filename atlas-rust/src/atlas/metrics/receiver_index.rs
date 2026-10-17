//! Owned receiver binding descriptors. Tree paths preserve nodes with duplicate spans.
use std::collections::BTreeMap;
use std::sync::{Arc, OnceLock};

use crate::metrics::receiver_syntax::ReceiverBinding;
use crate::metrics::resolution_syntax::NodeRef;
use crate::metrics::resolution_syntax::Syntax;

/// Owned binding index; borrowed syntax nodes never become resolver-owned data.
#[derive(Clone)]
pub struct ReceiverTypes {
    bindings: BTreeMap<String, Arc<FileBindings>>,
}

struct FileBindings {
    syntax: Syntax,
    entries: OnceLock<Vec<StoredReceiverBinding>>,
}
impl FileBindings {
    fn entries(&self) -> &Vec<StoredReceiverBinding> {
        self.entries.get_or_init(|| {
            self.syntax
                .nodes()
                .into_iter()
                .flat_map(|node| self.syntax.adapter.receiver_bindings(&self.syntax, node))
                .map(|binding| StoredReceiverBinding::new(&self.syntax, binding))
                .collect()
        })
    }
}

#[derive(Clone)]
struct StoredReceiverBinding {
    name: String,
    annotation: Option<String>,
    scope: NodeRef,
    node: NodeRef,
    inferred: bool,
    member: bool,
    static_: bool,
}

impl StoredReceiverBinding {
    fn new(syntax: &Syntax, binding: ReceiverBinding<'_>) -> Self {
        Self {
            name: binding.name,
            annotation: binding.annotation,
            scope: syntax.reference(binding.scope),
            node: syntax.reference(binding.node),
            inferred: binding.inferred,
            member: binding.member,
            static_: binding.static_,
        }
    }

    fn restore<'tree>(&self, syntax: &'tree Syntax) -> Option<ReceiverBinding<'tree>> {
        Some(ReceiverBinding {
            name: self.name.clone(),
            annotation: self.annotation.clone(),
            scope: syntax.dereference(&self.scope)?,
            node: syntax.dereference(&self.node)?,
            inferred: self.inferred,
            member: self.member,
            static_: self.static_,
        })
    }
}

impl ReceiverTypes {
    pub fn new(syntax: &BTreeMap<String, Syntax>) -> Self {
        let bindings = syntax
            .iter()
            .map(|(path, syntax)| {
                (path.clone(), Arc::new(FileBindings { syntax: syntax.clone(), entries: OnceLock::new() }))
            })
            .collect();
        Self { bindings }
    }

    pub(super) fn bindings_for<'tree>(&self, syntax: &'tree Syntax) -> Vec<ReceiverBinding<'tree>> {
        self.bindings[&syntax.file.source.path]
            .entries()
            .iter()
            .map(|binding| binding.restore(syntax).expect("Receiver index must use the syntax trees it was built from"))
            .collect()
    }
}
