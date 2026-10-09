"""Independent semantic fixtures; no snapshot or coffee inventory expectations."""

import unittest
from pathlib import Path

from atlas.parsing.discovery import SourceFile
from atlas.parsing.parser import parse_files
from atlas.metrics.resolver import resolve_connections


def repository(language, sources):
    return parse_files(
        [
            SourceFile(path, Path("/semantic") / path, language, source.encode())
            for path, source in sources.items()
        ]
    )


def call_edges(repo, evidence=None):
    edges = [e for e in resolve_connections(repo).connections if e.type == "CALLS"]
    return [e for e in edges if e.evidence == evidence] if evidence else edges


class ResolutionAssertions(unittest.TestCase):
    def internal(self, repo, evidence, suffix):
        edges = call_edges(repo, evidence)
        self.assertTrue(edges, evidence)
        self.assertTrue(
            all(
                e.target_key.startswith("symbol:") and suffix in e.target_key
                for e in edges
            ),
            edges,
        )
        return edges

    def external(self, repo, evidence):
        edges = call_edges(repo, evidence)
        self.assertTrue(edges, evidence)
        self.assertTrue(all(e.target_key.startswith("external:") for e in edges), edges)


class SemanticResolutionTest(ResolutionAssertions):
    def test_python_relative_imports_classes_and_static_members(self):
        repo = repository(
            "python",
            {
                "making/main.py": "from .recipe import Recipe as R\nfrom ..view.report import Report\nR.portions('tea')\nReport.render([])",
                "making/recipe.py": "class Recipe:\n @staticmethod\n def portions(name): return 2\n def instance(self): return 0",
                "view/report.py": "from ..making.recipe import Recipe\nclass Report:\n @staticmethod\n def render(names): return Recipe.portions('tea')",
            },
        )
        self.internal(repo, "R.portions('tea')", "recipe.py::Recipe.portions")
        self.internal(repo, "Report.render([])", "report.py::Report.render")
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertTrue(all(e.target_key.startswith("file:") for e in imports))

    def test_python_dotted_module_import_and_nonstatic_member(self):
        repo = repository(
            "python",
            {
                "pkg/recipe.py": "def portions(x): return x\nclass Recipe:\n def instance(self): return 1",
                "main.py": "import pkg.recipe\nfrom pkg.recipe import Recipe\npkg.recipe.portions(2)\nRecipe.instance()",
            },
        )
        self.internal(repo, "pkg.recipe.portions(2)", "recipe.py::portions")
        self.external(repo, "Recipe.instance()")

    def test_python_self_and_immediate_construction_are_precise(self):
        repo = repository(
            "python",
            {
                "main.py": """class Maker:
 def retry(self, n): return self.retry(n-1) if n else 0
 def brew(self): return 1
class Other:
 def brew(self): return 2
Maker().brew()
unknown.brew()
factory().brew()
"""
            },
        )
        recursion = self.internal(repo, "self.retry(n-1)", "Maker.retry")
        self.assertEqual(recursion[0].source_key, recursion[0].target_key)
        self.internal(repo, "Maker().brew()", "Maker.brew")
        self.internal(repo, "Maker()", "Maker:")
        self.external(repo, "unknown.brew()")
        self.external(repo, "factory().brew()")

    def test_import_shadowing_and_rebinding_never_guess(self):
        usages = [
            "def run(R): return R.portions(1)",
            "def run(R: object): return R.portions(1)",
            "def run():\n R = other\n return R.portions(1)",
            "R = other\nR.portions(1)",
            "R.portions = other\nR.portions(1)",
            "def run():\n for R in items: pass\n return R.portions(1)",
        ]
        for usage in usages:
            with self.subTest(usage=usage):
                repo = repository(
                    "python",
                    {
                        "recipe.py": "class Recipe:\n @staticmethod\n def portions(x): return x",
                        "main.py": "from recipe import Recipe as R\n" + usage,
                    },
                )
                self.external(repo, "R.portions(1)")

    def test_nested_import_does_not_leak_and_strings_are_not_writes(self):
        repo = repository(
            "python",
            {
                "recipe.py": "class Recipe:\n @staticmethod\n def portions(x): return x",
                "main.py": "def inside():\n from recipe import Recipe as R\n return R.portions(1)\ndef outside(): return R.portions(2)",
            },
        )
        self.internal(repo, "R.portions(1)", "Recipe.portions")
        self.external(repo, "R.portions(2)")
        repo = repository(
            "typescript",
            {
                "recipe.ts": "export class Recipe { static portions(x) { return x; } }",
                "main.ts": "import {Recipe as R} from './recipe'; const s = 'R = other'; /* R = other */ R.portions(1);",
            },
        )
        self.internal(repo, "R.portions(1)", "Recipe.portions")

    def test_javascript_imported_classes_static_recursion_and_new_receiver(self):
        for language, extension in [("javascript", "js"), ("typescript", "ts")]:
            with self.subTest(language=language):
                repo = repository(
                    language,
                    {
                        "recipe."
                        + extension: "export class Recipe { static portions(x) { return x; } }",
                        "main."
                        + extension: "import { Recipe as R } from './recipe'; class Maker { retry(n) { return n ? this.retry(n-1) : 0; } brew() {return R.portions(1);} } new Maker().brew(); unknown.brew();",
                    },
                )
                self.internal(repo, "R.portions(1)", "Recipe.portions")
                recursion = self.internal(repo, "this.retry(n-1)", "Maker.retry")
                self.assertEqual(recursion[0].source_key, recursion[0].target_key)
                self.internal(repo, "new Maker().brew()", "Maker.brew")
                self.external(repo, "unknown.brew()")

    def test_javascript_default_exports_and_type_only_imports(self):
        repo = repository(
            "typescript",
            {
                "recipe.ts": "class Actual { static portions(x) {return x;} } export default Actual;",
                "main.ts": "import R from './recipe'; R.portions(1);",
            },
        )
        self.internal(repo, "R.portions(1)", "Actual.portions")
        for imported in [
            "import R from './recipe';",
            "import type {Recipe as R} from './recipe';",
        ]:
            repo = repository(
                "typescript",
                {
                    "recipe.ts": "export class Recipe { static portions(x) {return x;} }",
                    "main.ts": imported + " R.portions(1);",
                },
            )
            self.external(repo, "R.portions(1)")

    def test_javascript_parameter_destructuring_rebind_and_duplicates(self):
        usages = [
            "function run(R) {R.portions(1);}",
            "const {R} = other; R.portions(1);",
            "R = other; R.portions(1);",
            "R.portions = other; R.portions(1);",
            "import {Recipe as R} from './other'; R.portions(1);",
            "factory().portions(1);",
            "object.portions(1);",
        ]
        for usage in usages:
            with self.subTest(usage=usage):
                repo = repository(
                    "typescript",
                    {
                        "recipe.ts": "export class Recipe {static portions(x) {return x;}}",
                        "other.ts": "export class Recipe {static portions(x) {return x;}}",
                        "main.ts": "import {Recipe as R} from './recipe'; " + usage,
                    },
                )
                evidence = (
                    "factory().portions(1)"
                    if usage.startswith("factory")
                    else "object.portions(1)"
                    if usage.startswith("object")
                    else "R.portions(1)"
                )
                self.external(repo, evidence)

    def test_java_declared_packages_and_same_package_types(self):
        repo = repository(
            "java",
            {
                "odd/Recipe.java": "package drinks.recipe; public class Recipe { public static int portions(int n){return n;} }",
                "physical/Report.java": "package drinks.report; import drinks.recipe.Recipe; class Report {static int total(){return Recipe.portions(2);}}",
                "elsewhere/App.java": "package drinks.recipe; class App {int run(){return Recipe.portions(1);}}",
            },
        )
        self.internal(repo, "Recipe.portions(2)", "Recipe.portions")
        self.internal(repo, "Recipe.portions(1)", "Recipe.portions")
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertEqual(len(imports), 1)
        self.assertIn("odd/Recipe.java::Recipe:", imports[0].target_key)

    def test_declared_import_identity_not_terminal_name(self):
        repo = repository(
            "java",
            {
                "Recipe.java": "package drinks.recipe; class Recipe {static int portions(){return 1;}}",
                "App.java": "package app; import other.Recipe; class App {int run(){return Recipe.portions();}}",
            },
        )
        self.external(repo, "Recipe.portions()")
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertTrue(imports[0].target_key.startswith("external:"))

    def test_kotlin_class_and_member_imports(self):
        repo = repository(
            "kotlin",
            {
                "odd/recipe.kt": "package drinks.recipe\nfun portions(x: Int): Int = x\nclass Maker {fun brew(): Int = 1}",
                "main.kt": "package app\nimport drinks.recipe.portions as amount\nimport drinks.recipe.Maker\nfun main() { amount(1); Maker().brew() }",
            },
        )
        file = next(f for f in repo.files if f.source.path == "main.kt")
        self.assertEqual(len(file.imports), 2)
        self.internal(repo, "amount(1)", "recipe.kt::portions")
        self.internal(repo, "Maker().brew()", "Maker.brew")
        self.assertTrue(
            all(
                not e.target_key.startswith("external:")
                for e in resolve_connections(repo).connections
                if e.type == "IMPORTS"
            )
        )

    def test_rust_path_modules_and_crate_imports(self):
        repo = repository(
            "rust",
            {
                "src/main.rs": '#[path = "../odd/recipe.rs"]\nmod recipe;\n#[path = "../view/report.rs"]\nmod report;\nfn main(){recipe::portions(1);}',
                "odd/recipe.rs": "use crate::report; pub fn portions(x:i32)->i32{x} pub fn preview(){report::render();}",
                "view/report.rs": "use crate::recipe; pub fn render(){crate::recipe::portions(2);}",
            },
        )
        self.internal(repo, "recipe::portions(1)", "recipe.rs::portions")
        self.internal(repo, "report::render()", "report.rs::render")
        self.internal(repo, "crate::recipe::portions(2)", "recipe.rs::portions")
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertTrue(imports)
        self.assertTrue(all(e.target_key.startswith("file:") for e in imports))

    def test_rust_duplicate_module_roots_are_ambiguous(self):
        repo = repository(
            "rust",
            {
                "a/main.rs": "mod tools; fn run(){crate::tools::work();}",
                "a/tools.rs": "pub fn work(){}",
                "b/main.rs": "mod tools;",
                "b/tools.rs": "pub fn work(){}",
            },
        )
        self.external(repo, "crate::tools::work()")

    def test_elixir_aliases_and_recursive_clause_identity(self):
        repo = repository(
            "elixir",
            {
                "report.ex": "defmodule Drinks.Report do\n def render(x), do: x\nend",
                "maker.ex": "defmodule Drinks.Maker do\n alias Drinks.Report, as: R\n def retry(0), do: 0\n def retry(n) when n > 0, do: retry(n-1)\n def brew(x), do: R.render(x)\nend",
            },
        )
        self.internal(repo, "R.render(x)", "Drinks.Report.render")
        edges = self.internal(repo, "retry(n-1)", "Drinks.Maker.retry")
        self.assertEqual(len(edges), 2)
        self.assertTrue(any(e.source_key == e.target_key for e in edges))

    def test_named_go_closure_and_rebinding(self):
        for rebind in [False, True]:
            self.check_go_closure(rebind)

    def check_go_closure(self, rebind):
        repo = repository(
            "go",
            {
                "main.go": "package main\nfunc brew(){accept := func(n int) int { return n }; "
                + ("accept = other; " if rebind else "")
                + "accept(1)}"
            },
        )
        file = repo.files[0]
        owner = next(s for s in file.symbols if s.name == "brew")
        closure = next(s for s in file.symbols if s.name == "accept")
        self.assertEqual(closure.parent_key, owner.key)
        if rebind:
            self.external(repo, "accept(1)")
        else:
            self.internal(repo, "accept(1)", "brew.accept")

    def test_ambiguous_types_and_methods_do_not_choose_first(self):
        repo = repository(
            "java",
            {
                "one/R.java": "package tools; class R {static void work(){}}",
                "two/R.java": "package tools; class R {static void work(){}}",
                "App.java": "import tools.R; class App {void f(){R.work();}}",
            },
        )
        self.external(repo, "R.work()")
