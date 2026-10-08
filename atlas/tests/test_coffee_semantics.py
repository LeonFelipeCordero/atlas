"""Scenario-specific assertions that a full graph equality check cannot justify."""

import unittest

from tests.coffee_fixture import LANGUAGES, coffee_graph, coffee_snapshot
from tests.coffee_scenarios import COMPLEXITY_FIELDS
from tests.coffee_snapshot_assertions import nodes_by_key
from tests.coffee_semantic_assertions import (
    assert_elixir_recursion,
    assert_go_closure,
    assert_library_output,
    assert_oo_contract,
    assert_workflow,
)


class CoffeeSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graphs = {
            language: coffee_snapshot(coffee_graph(language)) for language in LANGUAGES
        }

    def test_all_oo_contracts_and_explicit_brewer_constructions(self):
        for language in ("java", "kotlin", "javascript", "typescript", "python"):
            with self.subTest(language=language):
                assert_oo_contract(self, language, self.graphs[language])

    def test_java_method_reference_is_a_dependency_not_an_immediate_call(self):
        graph = self.graphs["java"]
        nodes = nodes_by_key(graph)
        edges = [
            edge for edge in graph["edges"] if edge["evidence"] == "Recipe::portions"
        ]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["type"], "REFERENCES")
        self.assertEqual(nodes[edges[0]["sourceStableKey"]]["name"], "total")
        self.assertEqual(nodes[edges[0]["targetStableKey"]]["name"], "portions")

    def test_go_closure_has_its_own_call_edges_and_metrics(self):
        assert_go_closure(self, self.graphs["go"])

    def test_elixir_recursion_is_one_real_call_site_with_clause_dispatch(self):
        assert_elixir_recursion(self, self.graphs["elixir"])

    def test_python_decorators_base_abc_and_match_complexity(self):
        graph = self.graphs["python"]
        nodes = nodes_by_key(graph)
        by_name = {node.get("qualifiedName"): node for node in nodes.values()}
        abstract = by_name["src/coffee/brewing/brewer.py::Brewing.brew"]
        self.assertEqual(abstract["properties"]["decorators"], ["@abstractmethod"])
        portions = by_name["src/coffee/brewing/recipe.py::Recipe.portions"]
        self.assertEqual(portions["properties"]["decorators"], ["@staticmethod"])
        self.assertEqual(
            tuple(portions["properties"][key] for key in COMPLEXITY_FIELDS),
            (3, 0, 0, 3, 1),
        )
        self.assertTrue(
            any(
                edge["type"] == "INHERITS"
                and nodes[edge["sourceStableKey"]]["name"] == "Brewing"
                and nodes[edge["targetStableKey"]]["name"] == "ABC"
                for edge in graph["edges"]
            )
        )

    def test_python_import_styles_link_to_local_files(self):
        graph = self.graphs["python"]
        nodes = nodes_by_key(graph)
        brewer = "src/coffee/brewing/brewer.py"
        recipe = "src/coffee/brewing/recipe.py"
        report = "src/coffee/reporting/report.py"
        brewer_imports = [
            edge for edge in graph["edges"]
            if edge["type"] == "IMPORTS" and edge["path"] == brewer
        ]
        imports = [
            (edge["evidence"], nodes[edge["targetStableKey"]]["path"])
            for edge in brewer_imports
            if nodes[edge["targetStableKey"]]["level"] != "external"
        ]
        comma_import = "import coffee.brewing.recipe as recipe, coffee.reporting.report as module_report"
        self.assertCountEqual(imports, [
            ("from .recipe import Recipe", recipe),
            ("from ..reporting.report import Report", report),
            (comma_import, recipe),
            (comma_import, report),
            ("import coffee.brewing.recipe", recipe),
            ("from coffee.brewing.recipe import portions as portion_count", recipe),
            ("from coffee.reporting.report import render as render_coffee", report),
            ("from . import (\n    recipe as relative_recipe,\n)", recipe),
            ("from ..reporting import report as relative_report", report),
            ("from coffee.reporting import report as absolute_report", report),
        ])
        external = [
            edge["evidence"] for edge in brewer_imports
            if nodes[edge["targetStableKey"]]["level"] == "external"
        ]
        self.assertCountEqual(external, ["from abc import ABC, abstractmethod", "import sys"])

    def test_python_import_styles_link_to_namespace_callables(self):
        graph = self.graphs["python"]
        nodes = nodes_by_key(graph)
        recipe = "src/coffee/brewing/recipe.py"
        report = "src/coffee/reporting/report.py"
        calls = [
            (edge["evidence"], nodes[edge["targetStableKey"]].get("qualifiedName"))
            for edge in graph["edges"]
            if edge["type"] == "CALLS"
            and nodes[edge["sourceStableKey"]]["name"] == "import_styles"
        ]
        self.assertCountEqual(calls, [
            ("recipe.portions(name)", recipe + "::portions"),
            ("coffee.brewing.recipe.portions(name)", recipe + "::portions"),
            ("relative_recipe.portions(name)", recipe + "::portions"),
            ("portion_count(name)", recipe + "::portions"),
            ("module_report.render([name])", report + "::render"),
            ("absolute_report.render([name])", report + "::render"),
            ("relative_report.render([name])", report + "::render"),
            ("render_coffee([name])", report + "::render"),
        ])

    def test_workflow_edges_reach_the_actual_sample_files(self):
        """The recipe/report cycle must describe project calls, not same-name externals."""
        for language, graph in self.graphs.items():
            with self.subTest(language=language):
                assert_workflow(self, language, graph)

    def test_library_output_dependencies_include_rust_macros(self):
        names = {
            "java": "println",
            "kotlin": "println",
            "go": "Println",
            "rust": "println!",
            "javascript": "write",
            "typescript": "write",
            "elixir": "puts",
            "python": "write",
        }
        for language, name in names.items():
            with self.subTest(language=language):
                assert_library_output(self, self.graphs[language], name)
