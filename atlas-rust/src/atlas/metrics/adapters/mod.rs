//! Independent language registries for metrics and name resolution.
pub mod base;
pub mod callable_selection;
pub mod elixir;
pub mod generic;
pub mod go;
pub mod java;
pub mod javascript;
pub mod kotlin;
pub mod module_index;
pub mod parameters;
pub mod python;
pub mod resolution;
pub mod resolution_metadata;
pub mod resolution_paths;
pub mod resolution_policy;
pub mod rust;
pub mod script_python_selection;
pub mod script_resolution;
pub mod typescript;
pub use base::{MetricAdapter, MetricPolicy};
pub use resolution_policy::ResolutionAdapter;

pub const DEDICATED_LANGUAGES: &[&str] = crate::parsing::discovery::SUPPORTED_LANGUAGES;
pub fn adapter_for_language(language: &str) -> ResolutionAdapter {
    ResolutionAdapter { language: language.into() }
}
pub fn get_resolution_adapter(language: &str) -> ResolutionAdapter {
    adapter_for_language(language)
}
pub fn metric_adapter_for_language(language: &str) -> MetricAdapter {
    assert!(
        crate::parsing::discovery::is_supported_language(language),
        "Unsupported Rust importer language: {language}"
    );
    MetricAdapter::new(language)
}
pub fn get_metric_adapter(language: &str) -> MetricAdapter {
    metric_adapter_for_language(language)
}
pub fn parameter_count(language: &str, node: tree_sitter::Node<'_>, source: &[u8]) -> Option<usize> {
    metric_adapter_for_language(language).parameter_count(node, source)
}
pub fn receiver_coverage() -> serde_json::Value {
    let languages: Vec<_> = crate::parsing::discovery::supported_languages().iter().map(String::as_str).collect();
    generic::receiver_coverage(&languages, DEDICATED_LANGUAGES)
}
