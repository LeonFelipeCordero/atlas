"""End-to-end extraction/resolution contracts, with no injected source facts."""

from tests.test_semantic_resolution import ResolutionAssertions, call_edges, repository


class ExtractionContractTest(ResolutionAssertions):
    # Inherit assertion helpers, not the semantic fixture suite.
    def test_macro_inner_calls_have_original_source_spans_and_hints(self):
        repo = repository(
            "rust", {"main.rs": 'fn brew()->i32{1} fn main(){println!("{}", brew());}'}
        )
        file = repo.files[0]
        calls = [call for call in file.calls if call.name == "brew"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].start_byte, file.source.source.rindex(b"brew()"))
        self.assertEqual(calls[0].evidence, "brew()")
        self.assertIn("println!", {call.name for call in file.calls})

    def test_constructor_identity_never_uses_global_type_guessing(self):
        for language, extension, declaration, usage in [
            (
                "python",
                "py",
                "class Maker:\n def brew(self): return 1",
                "Maker().brew()",
            ),
            (
                "typescript",
                "ts",
                "export class Maker {brew(){return 1;}}",
                "new Maker().brew()",
            ),
        ]:
            with self.subTest(language=language):
                repo = repository(
                    language,
                    {"maker." + extension: declaration, "main." + extension: usage},
                )
                self.external(repo, usage)
                self.external(
                    repo, "Maker()" if language == "python" else "new Maker()"
                )

    def test_java_static_member_import(self):
        repo = repository(
            "java",
            {
                "odd/R.java": "package drinks; class R {public static int portions(int n){return n;}}",
                "App.java": "import static drinks.R.portions; class App {int f(){return portions(1);}}",
            },
        )
        self.internal(repo, "portions(1)", "R.portions")

    def test_elixir_clause_arity_and_unrelated_modules_remain_ambiguous(self):
        repo = repository(
            "elixir",
            {
                "maker.ex": "defmodule Maker do\n def retry(0), do: 0\n def retry(n), do: retry(n-1)\n def retry(n, x), do: x\nend",
                "other.ex": "defmodule Other do\n def retry(n), do: n\nend",
            },
        )
        edges = call_edges(repo, "retry(n-1)")
        self.assertEqual(len(edges), 2)
        self.assertTrue(all("Maker.retry" in e.target_key for e in edges))
        other_arity = next(
            s.key for s in repo.symbols if s.signature and "retry(n, x)" in s.signature
        )
        self.assertNotIn(other_arity, {e.target_key for e in edges})

    def test_rust_object_dot_is_not_a_module_reference(self):
        repo = repository(
            "rust",
            {
                "main.rs": "mod recipe; fn main(){recipe.portions(1);}",
                "recipe.rs": "pub fn portions(x:i32)->i32{x}",
            },
        )
        self.external(repo, "recipe.portions(1)")

    def test_receiver_rebinding_and_prototype_replacement(self):
        repo = repository(
            "python",
            {
                "main.py": "class Maker:\n def retry(self, n):\n  self = other\n  return self.retry(n-1)"
            },
        )
        self.external(repo, "self.retry(n-1)")
        repo = repository(
            "typescript",
            {
                "main.ts": "class Maker {brew(){return 1;}} Maker.prototype.brew = other; new Maker().brew();"
            },
        )
        self.external(repo, "new Maker().brew()")
        repo = repository(
            "typescript",
            {
                "maker.ts": "export class Maker {brew(){return 1;}}",
                "main.ts": "import {Maker as R} from './maker'; R.prototype.brew = other; new R().brew();",
            },
        )
        self.external(repo, "new R().brew()")
