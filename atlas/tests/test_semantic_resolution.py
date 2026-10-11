"""Independent semantic invariants over centralized, snapshotted source cases."""

from tests.resolution_snapshot_support import fixture_sources
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
                (
                    e.target_key.startswith("symbol:") and suffix in e.target_key
                    for e in edges
                )
            ),
            edges,
        )
        return edges

    def external(self, repo, evidence):
        edges = call_edges(repo, evidence)
        self.assertTrue(edges, evidence)
        self.assertTrue(
            all((e.target_key.startswith("external:") for e in edges)), edges
        )


class SemanticResolutionTest(ResolutionAssertions):
    def test_python_relative_imports_classes_and_static_members(self):
        repo = repository(
            "python",
            fixture_sources(
                "semantic_resolution:test_python_relative_imports_classes_and_static_members:46-15"
            ),
        )
        self.internal(repo, "R.portions('tea')", "recipe.py::Recipe.portions")
        self.internal(repo, "Report.render([])", "report.py::Report.render")
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertTrue(all((e.target_key.startswith("file:") for e in imports)))

    def test_python_dotted_module_import_and_nonstatic_member(self):
        repo = repository(
            "python",
            fixture_sources(
                "semantic_resolution:test_python_dotted_module_import_and_nonstatic_member:62-15"
            ),
        )
        self.internal(repo, "pkg.recipe.portions(2)", "recipe.py::portions")
        self.external(repo, "Recipe.instance()")

    def test_python_self_and_immediate_construction_are_precise(self):
        repo = repository(
            "python",
            fixture_sources(
                "semantic_resolution:test_python_self_and_immediate_construction_are_precise:73-15"
            ),
        )
        recursion = self.internal(repo, "self.retry(n-1)", "Maker.retry")
        self.assertEqual(recursion[0].source_key, recursion[0].target_key)
        self.internal(repo, "Maker().brew()", "Maker.brew")
        self.internal(repo, "Maker()", "Maker:")
        self.external(repo, "unknown.brew()")
        self.external(repo, "factory().brew()")

    def test_import_shadowing_and_rebinding_never_guess(self):
        usages = [
            "import-shadowing-and-rebinding-never-guess-python-01",
            "import-shadowing-and-rebinding-never-guess-python-02",
            "import-shadowing-and-rebinding-never-guess-python-03",
            "import-shadowing-and-rebinding-never-guess-python-04",
            "import-shadowing-and-rebinding-never-guess-python-05",
            "import-shadowing-and-rebinding-never-guess-python-06",
        ]
        for usage in usages:
            with self.subTest(usage=usage):
                repo = repository(
                    "python",
                    fixture_sources(
                        "semantic_resolution:test_import_shadowing_and_rebinding_never_guess:105-23",
                        usage=usage,
                    ),
                )
                self.external(repo, "R.portions(1)")

    def test_nested_import_does_not_leak_and_strings_are_not_writes(self):
        repo = repository(
            "python",
            fixture_sources(
                "semantic_resolution:test_nested_import_does_not_leak_and_strings_are_not_writes:115-15"
            ),
        )
        self.internal(repo, "R.portions(1)", "Recipe.portions")
        self.external(repo, "R.portions(2)")
        repo = repository(
            "typescript",
            fixture_sources(
                "semantic_resolution:test_nested_import_does_not_leak_and_strings_are_not_writes:124-15"
            ),
        )
        self.internal(repo, "R.portions(1)", "Recipe.portions")

    def test_javascript_imported_classes_static_recursion_and_new_receiver(self):
        for language, extension in [("javascript", "js"), ("typescript", "ts")]:
            with self.subTest(language=language):
                repo = repository(
                    language,
                    fixture_sources(
                        "semantic_resolution:test_javascript_imported_classes_static_recursion_and_new_receiver:136-23",
                        language=language,
                    ),
                )
                self.internal(repo, "R.portions(1)", "Recipe.portions")
                recursion = self.internal(repo, "this.retry(n-1)", "Maker.retry")
                self.assertEqual(recursion[0].source_key, recursion[0].target_key)
                self.internal(repo, "new Maker().brew()", "Maker.brew")
                self.external(repo, "unknown.brew()")

    def test_javascript_default_exports_and_type_only_imports(self):
        repo = repository(
            "typescript",
            fixture_sources(
                "semantic_resolution:test_javascript_default_exports_and_type_only_imports:152-15"
            ),
        )
        self.internal(repo, "R.portions(1)", "Actual.portions")
        for imported in [
            "javascript-default-exports-and-type-only-imports-typescript-02",
            "javascript-default-exports-and-type-only-imports-typescript-03",
        ]:
            repo = repository(
                "typescript",
                fixture_sources(
                    "semantic_resolution:test_javascript_default_exports_and_type_only_imports:164-19",
                    imported=imported,
                ),
            )
            self.external(repo, "R.portions(1)")

    def test_javascript_parameter_destructuring_rebind_and_duplicates(self):
        usages = [
            "javascript-parameter-destructuring-rebind-and-duplicates-typescript-01",
            "javascript-parameter-destructuring-rebind-and-duplicates-typescript-02",
            "R = other; R.portions(1);",
            "javascript-parameter-destructuring-rebind-and-duplicates-typescript-04",
            "javascript-parameter-destructuring-rebind-and-duplicates-typescript-05",
            "factory().portions(1);",
            "object.portions(1);",
        ]
        for usage in usages:
            with self.subTest(usage=usage):
                repo = repository(
                    "typescript",
                    fixture_sources(
                        "semantic_resolution:test_javascript_parameter_destructuring_rebind_and_duplicates:185-23",
                        usage=usage,
                    ),
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
            fixture_sources(
                "semantic_resolution:test_java_declared_packages_and_same_package_types:203-15"
            ),
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
            fixture_sources(
                "semantic_resolution:test_declared_import_identity_not_terminal_name:220-15"
            ),
        )
        self.external(repo, "Recipe.portions()")
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertTrue(imports[0].target_key.startswith("external:"))

    def test_kotlin_class_and_member_imports(self):
        repo = repository(
            "kotlin",
            fixture_sources(
                "semantic_resolution:test_kotlin_class_and_member_imports:234-15"
            ),
        )
        file = next((f for f in repo.files if f.source.path == "main.kt"))
        self.assertEqual(len(file.imports), 2)
        self.internal(repo, "amount(1)", "recipe.kt::portions")
        self.internal(repo, "Maker().brew()", "Maker.brew")
        self.assertTrue(
            all(
                (
                    not e.target_key.startswith("external:")
                    for e in resolve_connections(repo).connections
                    if e.type == "IMPORTS"
                )
            )
        )

    def test_rust_path_modules_and_crate_imports(self):
        repo = repository(
            "rust",
            fixture_sources(
                "semantic_resolution:test_rust_path_modules_and_crate_imports:254-15"
            ),
        )
        self.internal(repo, "recipe::portions(1)", "recipe.rs::portions")
        self.internal(repo, "report::render()", "report.rs::render")
        self.internal(repo, "crate::recipe::portions(2)", "recipe.rs::portions")
        imports = [
            e for e in resolve_connections(repo).connections if e.type == "IMPORTS"
        ]
        self.assertTrue(imports)
        self.assertTrue(all((e.target_key.startswith("file:") for e in imports)))

    def test_rust_duplicate_module_roots_are_ambiguous(self):
        repo = repository(
            "rust",
            fixture_sources(
                "semantic_resolution:test_rust_duplicate_module_roots_are_ambiguous:272-15"
            ),
        )
        self.external(repo, "crate::tools::work()")

    def test_elixir_aliases_and_recursive_clause_identity(self):
        repo = repository(
            "elixir",
            fixture_sources(
                "semantic_resolution:test_elixir_aliases_and_recursive_clause_identity:284-15"
            ),
        )
        self.internal(repo, "R.render(x)", "Drinks.Report.render")
        edges = self.internal(repo, "retry(n-1)", "Drinks.Maker.retry")
        self.assertEqual(len(edges), 2)
        self.assertTrue(any((e.source_key == e.target_key for e in edges)))

    def test_named_go_closure_and_rebinding(self):
        for rebind in [False, True]:
            self.check_go_closure(rebind)

    def check_go_closure(self, rebind):
        repo = repository(
            "go",
            fixture_sources(
                "semantic_resolution:check_go_closure:301-15", rebind=rebind
            ),
        )
        file = repo.files[0]
        owner = next((s for s in file.symbols if s.name == "brew"))
        closure = next((s for s in file.symbols if s.name == "accept"))
        self.assertEqual(closure.parent_key, owner.key)
        if rebind:
            self.external(repo, "accept(1)")
        else:
            self.internal(repo, "accept(1)", "brew.accept")

    def test_ambiguous_types_and_methods_do_not_choose_first(self):
        repo = repository(
            "java",
            fixture_sources(
                "semantic_resolution:test_ambiguous_types_and_methods_do_not_choose_first:319-15"
            ),
        )
        self.external(repo, "R.work()")
