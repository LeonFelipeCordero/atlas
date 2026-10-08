"""Counterexamples found by independent review; never bless unsafe targets."""

from atlas.domain.resolver import resolve_connections
from tests.test_semantic_resolution import ResolutionAssertions, call_edges, repository


class ResolutionReviewRegressionTest(ResolutionAssertions):
    def test_java_base_is_looked_up_outside_the_derived_class_body(self):
        repo = repository(
            "java",
            {
                "main.java": "class Base {} class Derived extends Base {static class Base {}}"
            },
        )
        edge = next(
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "INHERITS"
        )
        self.assertIn("main.java::Base:", edge.target_key)
        self.assertNotIn("Derived.Base", edge.target_key)

    def test_python_imported_base_is_not_shadowed_by_future_class_body(self):
        repo = repository(
            "python",
            {
                "base.py": "class Base: pass",
                "main.py": "from base import Base\nclass Derived(Base):\n class Base: pass",
            },
        )
        edge = next(
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "INHERITS"
        )
        self.assertIn("base.py::Base:", edge.target_key)

    def test_js_namespace_export_aliases_do_not_expose_private_names(self):
        for language, extension in (("javascript", "js"), ("typescript", "ts")):
            with self.subTest(language=language):
                repo = repository(
                    language,
                    {
                        "r."
                        + extension: "function hidden() {} function api() {} export {hidden as api};",
                        "main."
                        + extension: "import * as r from './r'; r.hidden(); r.api();",
                    },
                )
                self.external(repo, "r.hidden()")
                self.internal(repo, "r.api()", "r." + extension + "::hidden:")

    def test_js_default_namespace_and_named_export_aliases_keep_real_keys(self):
        repo = repository(
            "typescript",
            {
                "r.ts": "function hidden(){} export {hidden as api, hidden as default};",
                "main.ts": "import * as r from './r'; import {api as run} from './r'; r.default(); run(); r.hidden();",
            },
        )
        self.internal(repo, "r.default()", "r.ts::hidden:")
        self.internal(repo, "run()", "r.ts::hidden:")
        self.external(repo, "r.hidden()")

    def test_macro_stringification_and_unknown_payloads_are_not_runtime_calls(self):
        repo = repository(
            "rust",
            {
                "main.rs": "fn brew()->i32{1} fn main(){stringify!(brew()); custom!(brew());}"
            },
        )
        self.assertNotIn("brew", {call.name for call in repo.calls})
        self.assertEqual({call.name for call in repo.calls}, {"stringify!", "custom!"})

    def test_macro_local_bindings_are_not_repository_functions(self):
        repo = repository(
            "rust",
            {
                "main.rs": "fn brew()->i32{1} fn main(){let values=vec![{let brew=||2;brew()}]; let text=stringify!(brew());}"
            },
        )
        self.external(repo, "brew()")
        self.assertEqual(len(call_edges(repo, "brew()")), 1)
        self.assertFalse(
            any("main.rs::brew:" in edge.target_key for edge in call_edges(repo))
        )

    def test_rust_closure_function_parameter_shadows_bare_function(self):
        repo = repository(
            "rust",
            {
                "main.rs": "fn brew(){} fn main(){let callback=|brew:fn()|brew(); brew();}"
            },
        )
        edges = call_edges(repo, "brew()")
        self.assertEqual(len(edges), 2)
        self.assertTrue(edges[0].target_key.startswith("external:"))
        self.assertIn("main.rs::brew:", edges[1].target_key)

    def test_macro_method_receivers_do_not_become_module_namespaces(self):
        repo = repository(
            "rust",
            {
                "main.rs": 'mod recipe; fn main(){println!("{}", recipe.portions());}',
                "recipe.rs": "pub fn portions()->i32{1}",
            },
        )
        self.external(repo, "recipe.portions()")

    def test_custom_macro_overriding_std_names_blocks_nested_payload_inference(self):
        repo = repository(
            "rust",
            {
                "main.rs": 'macro_rules! println {($x:expr)=>{stringify!($x)}} fn brew()->i32{1} fn main(){format!("{}", println!(brew()));}'
            },
        )
        self.assertNotIn("brew", {call.name for call in repo.calls})
        self.assertIn("println!", {call.name for call in repo.calls})

    def test_nested_macro_payloads_keep_enclosing_local_bindings(self):
        declarations = [
            "let brew=||2;",
            "const brew:fn()->i32=||2;",
            "static brew:fn()->i32=||2;",
            "use other::other as brew;",
        ]
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                repo = repository(
                    "rust",
                    {
                        "main.rs": "mod other{pub fn other()->i32{2}} fn brew()->i32{1} fn main(){let _=vec![{"
                        + declaration
                        + "dbg!(brew())}];}"
                    },
                )
                self.external(repo, "brew()")
                self.assertEqual(len(call_edges(repo, "brew()")), 1)

    def test_nested_custom_macro_definitions_remain_in_context(self):
        repo = repository(
            "rust",
            {
                "main.rs": 'fn brew()->i32{1} fn main(){let _=vec![{macro_rules! dbg{($e:expr)=>{stringify!($e)}} format!("{}",dbg!(brew()))}];}'
            },
        )
        self.assertNotIn("brew", {call.name for call in repo.calls})
        self.assertIn("dbg!", {call.name for call in repo.calls})

    def test_aliased_standard_macro_namespace_is_not_assumed_standard(self):
        repo = repository(
            "rust",
            {
                "main.rs": "mod custom{pub use std::stringify as dbg;} use custom as std; fn brew()->i32{1} fn main(){std::dbg!(brew());}"
            },
        )
        self.assertNotIn("brew", {call.name for call in repo.calls})
        self.assertIn("std::dbg!", {call.name for call in repo.calls})

    def test_future_class_body_import_does_not_shadow_base_header(self):
        repo = repository(
            "python",
            {
                "tools.py": "class Base: pass",
                "other.py": "class Base: pass",
                "main.py": "from tools import Base\nclass Derived(Base):\n from other import Base",
            },
        )
        inherited = [
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "INHERITS"
        ]
        self.assertEqual(len(inherited), 1)
        self.assertIn("tools.py::Base:", inherited[0].target_key)

    def test_rust_child_module_is_not_a_false_crate_root(self):
        repo = repository(
            "rust",
            {
                "main.rs": "mod outer; fn main(){crate::inner::work(); crate::outer::inner::work();}",
                "outer.rs": "pub mod inner;",
                "outer/inner.rs": "pub fn work(){}",
            },
        )
        self.external(repo, "crate::inner::work()")
        self.internal(repo, "crate::outer::inner::work()", "outer/inner.rs::work")

    def test_inline_rust_module_members_import_scopes_and_aliases(self):
        repo = repository(
            "rust",
            {
                "main.rs": "mod tools{pub fn work(){}} mod outer {use super::tools as t; pub mod inner; pub fn run(){t::work(); inner::work();}} fn main(){crate::outer::run(); t::work();}",
                "outer/inner.rs": "pub fn work(){}",
                "inner.rs": "pub fn work(){}",
            },
        )
        self.internal(repo, "crate::outer::run()", "main.rs::outer.run")
        self.internal(repo, "inner::work()", "outer/inner.rs::work")
        edges = call_edges(repo, "t::work()")
        self.assertEqual(len(edges), 2)
        self.assertTrue(edges[0].target_key.startswith("symbol:"))
        self.assertTrue(edges[1].target_key.startswith("external:"))
        imports = [
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "IMPORTS"
        ]
        self.assertTrue(imports)
        self.assertTrue(
            all(edge.target_key.startswith(("symbol:", "file:")) for edge in imports)
        )
