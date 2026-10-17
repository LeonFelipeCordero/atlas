//! Every complete-project extraction/analysis golden, including processing structures and grammar variants.
mod pipeline;
mod support;
use pipeline::{Bundle, structure_seam};
use serde_json::Value;
use support::{assert_json, fixtures, snapshot};

struct State {
    actual: Bundle,
    extraction: Value,
    analysis: Value,
    graph: Value,
}

impl State {
    fn new(language: &str) -> Self {
        Self {
            actual: pipeline::project(&fixtures().join(language)),
            extraction: snapshot(&format!("coffee/{language}/extraction.json")),
            analysis: snapshot(&format!("coffee/{language}/analysis.json")),
            graph: snapshot(&format!("coffee/{language}/graph.json")),
        }
    }

    fn field(&self, field: &str) {
        assert_json(&self.actual.extraction[field], &self.extraction[field], &format!("/{field}"));
    }

    fn structures(&self, seam: &str) {
        assert_json(
            &structure_seam(&self.actual.extraction, seam),
            &structure_seam(&self.extraction, seam),
            "/structures",
        );
    }
}

macro_rules! pipeline_tests {
    ($($language:ident),+ $(,)?) => {$ (
        mod $language {
            use super::*;
            use std::sync::OnceLock;
            fn state() -> &'static State {
                static STATE: OnceLock<State> = OnceLock::new();
                STATE.get_or_init(|| State::new(stringify!($language)))
            }
            #[test] fn complete_parsed_files() { state().field("files"); }
            #[test] fn native_processing_structures() { state().structures("native"); }
            #[test] fn tags_only_structures() { state().structures("tags_only"); }
            #[test] fn merged_structures() { state().structures("merged"); }
            #[test] fn excluded_language_sources() { state().field("excluded_sources"); }
            #[test] fn same_source_grammar_variants() { state().field("grammar_variants"); }
            #[test] fn complete_extraction_bundle() { assert_json(&state().actual.extraction, &state().extraction, ""); }
            #[test] fn enriched_repository_and_resolution() { assert_json(&state().actual.analysis, &state().analysis, ""); }
            #[test] fn staged_pipeline_graph() { assert_json(&state().actual.graph, &state().graph, ""); }
        }
    )+};
}

pipeline_tests!(java, kotlin, go, rust, javascript, typescript, elixir, python, tsx);
