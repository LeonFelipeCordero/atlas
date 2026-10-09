import tempfile
import unittest
from pathlib import Path

from tree_sitter_language_pack import get_parser

from atlas.domain.models import Complexity
from atlas.metrics.complexity import calculate_complexity
from atlas.indexer import analyze_repository


class ComplexityTests(unittest.TestCase):
    def measure(self, source: str, language: str = "typescript") -> Complexity:
        return calculate_complexity(
            get_parser(language).parse(source.encode()).root_node.named_children[0]
        )

    def test_entry_and_sequential_decisions(self) -> None:
        self.assertEqual(self.measure("{}"), Complexity(1, 0, 0, 1, 0))
        self.assertEqual(
            self.measure("{ if(a){} if(b){} if(c){} }"), Complexity(4, 0, 0, 4, 1)
        )

    def test_requested_example_across_grammars(self) -> None:
        samples = {
            "typescript": "{ for(let a of x){for(let b of x){if(a){if(b){}}}} }",
            "javascript": "{ for(let a of x){for(let b of x){if(a){if(b){}}}} }",
            "python": "for a in x:\n for b in x:\n  if a:\n   if b: pass\n",
            "java": "{ for(int a=0;a<2;a++){while(true){if(a>0){if(a>1){}}}} }",
            "kotlin": "fun f() { for(a in x){for(b in x){if(a){if(b){}}}} }",
            "go": "func f(){for {for {if true {if true {}}}}}",
            "rust": "fn f(){for a in x {for b in x {if a {if b {}}}}}",
        }
        for language, source in samples.items():
            with self.subTest(language=language):
                self.assertEqual(
                    self.measure(source, language), Complexity(5, 2, 1, 8, 4)
                )

    def test_depths_three_four_five(self) -> None:
        for depth in (3, 4, 5):
            with self.subTest(depth=depth):
                source = "{" + "if(a){" * depth + "}" * depth + "}"
                self.assertEqual(
                    self.measure(source),
                    Complexity(depth + 1, depth - 2, 0, 2 * depth - 1, depth),
                )

    def test_penalty_per_deep_decision_not_only_maximum(self) -> None:
        self.assertEqual(
            self.measure("{if(a){if(b){if(c){} if(d){}}}}"), Complexity(5, 2, 0, 7, 3)
        )

    def test_loop_ancestor_need_not_be_immediate_parent(self) -> None:
        self.assertEqual(
            self.measure("{for(;;){if(a){while(b){for(;;){}}}}}"),
            Complexity(5, 2, 2, 9, 4),
        )
        self.assertEqual(
            self.measure("{for(;;){} while(a){} }"), Complexity(3, 0, 0, 3, 1)
        )

    def test_boolean_ternary_catch_and_cases(self) -> None:
        self.assertEqual(
            self.measure("{if(a && b || c){} }"), Complexity(4, 0, 0, 4, 1)
        )
        self.assertEqual(
            self.measure("{const x = a ? b : c; try {} catch(e) {} }"),
            Complexity(3, 0, 0, 3, 1),
        )
        self.assertEqual(
            self.measure("{switch(x){case 1: break; case 2: break; default: break;} }"),
            Complexity(3, 0, 0, 3, 1),
        )

    def test_else_if_is_not_nesting(self) -> None:
        self.assertEqual(
            self.measure("{if(a){}else if(b){}else if(c){}else if(d){} }"),
            Complexity(5, 0, 0, 5, 1),
        )
        source = "if a: pass\nelif b: pass\nelif c: pass\nelse: pass\n"
        self.assertEqual(self.measure(source, "python"), Complexity(4, 0, 0, 4, 1))

    def test_nested_scopes_are_not_counted(self) -> None:
        source = "{ if(a) { function inner(){for(;;){for(;;){if(b){}}}} const f = () => {while(a){if(b){}}}; class A {run(){if(a){}}} } }"
        self.assertEqual(self.measure(source), Complexity(2, 0, 0, 2, 1))

    def test_python_method_and_inner_function_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.py").write_text(
                "class A:\n"
                " def run(self, default=1 if flag else 0):\n"
                "  for a in x:\n"
                "   def inner():\n"
                "    for b in x:\n"
                "     if b: pass\n"
            )
            artifact = analyze_repository(root)
            by_name = {node["name"]: node for node in artifact.nodes}
            self.assertEqual(by_name["run"]["properties"]["cyclomaticComplexity"], 2)
            self.assertEqual(by_name["inner"]["properties"]["cyclomaticComplexity"], 3)
            self.assertEqual(by_name["inner"]["properties"]["loopNestedComplexity"], 0)
            self.assertNotIn("cyclomaticComplexity", by_name["A"]["properties"])

    def test_artifact_only_function_and_method_properties(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.ts").write_text("""
for(;;) { if(globalFlag) {} }
class A {
    run() { for(;;){for(;;){if(a){if(b){}}}} }
}
function outer() {
    if(a) {
        function inner() { for(;;){while(b){if(c){}}} }
        const anonymous = () => { while(a){if(b){}} };
    }
}
function empty() {}
""")
            nodes = analyze_repository(root).nodes
            by_name = {
                node["name"]: node
                for node in nodes
                if node["type"] in {"function", "method"}
            }
            self.assertEqual(by_name["run"]["properties"]["cyclomaticComplexity"], 8)
            self.assertEqual(
                by_name["run"]["properties"]["nestedCyclomaticComplexity"], 2
            )
            self.assertEqual(by_name["run"]["properties"]["loopNestedComplexity"], 1)
            self.assertEqual(by_name["outer"]["properties"]["cyclomaticComplexity"], 2)
            self.assertEqual(by_name["inner"]["properties"]["cyclomaticComplexity"], 6)
            self.assertEqual(by_name["empty"]["properties"]["cyclomaticComplexity"], 1)
            for node in nodes:
                if node["type"] not in {"function", "method"}:
                    self.assertNotIn("cyclomaticComplexity", node["properties"])
                    self.assertNotIn("nestedCyclomaticComplexity", node["properties"])
                    self.assertNotIn("loopNestedComplexity", node["properties"])


if __name__ == "__main__":
    unittest.main()
