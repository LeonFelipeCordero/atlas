//! Shared receiver lookup context, independent of inference and write detection.
use crate::domain::models::Symbol;
use crate::metrics::receiver_syntax::ReceiverBinding;
use crate::metrics::resolution_contract::ResolutionRequest;
use crate::metrics::resolver::CallResolver;

pub(super) struct ReceiverInference<'resolver> {
    pub(super) resolver: &'resolver CallResolver,
}

impl<'resolver> ReceiverInference<'resolver> {
    pub(super) fn new(resolver: &'resolver CallResolver) -> Self {
        Self { resolver }
    }

    pub(super) fn bindings(&self, path: &str) -> Vec<ReceiverBinding<'resolver>> {
        self.resolver.receivers.bindings_for(&self.resolver.syntax[path])
    }

    pub(super) fn qualified_type(&self, request: &ResolutionRequest<'_>) -> Vec<Symbol> {
        let separator = if request.name.contains("::") { "::" } else { "." };
        let Some((qualifier, name)) = request.name.rsplit_once(separator).filter(|(q, _)| !q.is_empty()) else {
            return vec![];
        };
        self.resolver.qualified(&ResolutionRequest {
            name: name.to_owned(),
            qualifier: Some(qualifier.to_owned()),
            ..request.clone()
        })
    }
}
