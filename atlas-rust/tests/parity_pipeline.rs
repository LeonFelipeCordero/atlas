//! Complete extraction, analysis, and graph parity, including structures and grammar variants.
mod pipeline;
mod support;
use support::{assert_json, fixtures, snapshot};

macro_rules! pipeline_tests {
    ($($language:ident),+ $(,)?) => {$ (
        mod $language {
            use super::*;
            use std::sync::OnceLock;
            fn bundle() -> &'static pipeline::Bundle {
                static BUNDLE: OnceLock<pipeline::Bundle> = OnceLock::new();
                BUNDLE.get_or_init(|| pipeline::project(&fixtures().join(stringify!($language))))
            }
            fn expected(stage: &str) -> serde_json::Value {
                snapshot(&format!("coffee/{}/{stage}.json", stringify!($language)))
            }
            // The full bundle includes files, all three structure seams, excluded sources, and grammar variants.
            #[test] fn complete_extraction_bundle() { assert_json(&bundle().extraction, &expected("extraction"), ""); }
            #[test] fn enriched_repository_and_resolution() { assert_json(&bundle().analysis, &expected("analysis"), ""); }
            #[test] fn staged_pipeline_graph() { assert_json(&bundle().graph, &expected("graph"), ""); }
        }
    )+};
}

pipeline_tests!(java, kotlin, go, rust, javascript, typescript, elixir, python, tsx);
