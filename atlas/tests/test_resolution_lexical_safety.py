"""Independent lexical safety invariants over complete source fixture projects."""

from tests.resolution_snapshot_support import fixture_sources
import unittest
from pathlib import Path
from atlas.metrics.adapters import get_resolution_adapter
from atlas.parsing.discovery import SourceFile
from atlas.parsing.parser import parse_files
from atlas.metrics.resolution_syntax import Syntax
from atlas.metrics.resolver import resolve_connections


def repository(language, sources):
    return parse_files(
        [
            SourceFile(path, Path("/lexical") / path, language, source.encode())
            for path, source in sources.items()
        ]
    )


class LexicalSafetyTest(unittest.TestCase):
    def assert_call(self, repo, evidence, target=None):
        edges = [
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "CALLS" and edge.evidence == evidence
        ]
        self.assertTrue(edges, evidence)
        if target is None:
            self.assertTrue(
                all((e.target_key.startswith("external:") for e in edges)), edges
            )
            return
        self.assertTrue(
            all(
                (
                    e.target_key.startswith("symbol:") and target in e.target_key
                    for e in edges
                )
            ),
            edges,
        )

    def test_python_blocks_bind_in_enclosing_function(self):
        usages = [
            "python-blocks-bind-in-enclosing-function-python-01",
            "python-blocks-bind-in-enclosing-function-python-02",
            "python-blocks-bind-in-enclosing-function-python-03",
            "python-blocks-bind-in-enclosing-function-python-04",
            "python-blocks-bind-in-enclosing-function-python-05",
            "python-blocks-bind-in-enclosing-function-python-06",
            "python-blocks-bind-in-enclosing-function-python-07",
        ]
        for usage in usages:
            with self.subTest(usage=usage):
                repo = repository(
                    "python",
                    fixture_sources(
                        "resolution_lexical_safety:test_python_blocks_bind_in_enclosing_function:64-23",
                        usage=usage,
                    ),
                )
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_module_and_class_blocks_are_not_scopes(self):
        repo = repository(
            "python",
            fixture_sources(
                "resolution_lexical_safety:test_python_module_and_class_blocks_are_not_scopes:69-15"
            ),
        )
        self.assert_call(repo, "R.work()")
        repo = repository(
            "python",
            fixture_sources(
                "resolution_lexical_safety:test_python_module_and_class_blocks_are_not_scopes:71-15"
            ),
        )
        self.assert_call(repo, "R.work()")
        self.assert_call(repo, "R.work(1)", "tools.py::R.work")
        self.assert_call(repo, "R.work(2)", "tools.py::R.work")
        self.assert_call(repo, "R.work(3)")
        self.assert_call(repo, "R.work(4)", "tools.py::R.work")
        self.assert_call(repo, "R.work(5)")

    def test_python_conditional_import_persists_without_leaking_function(self):
        repo = repository(
            "python",
            fixture_sources(
                "resolution_lexical_safety:test_python_conditional_import_persists_without_leaking_function:85-15"
            ),
        )
        self.assert_call(repo, "R.work()", "tools.py::R.work")
        self.assert_call(repo, "R.work(2)")
        syntax = Syntax(
            next((f for f in repo.files if f.source.path == "main.py")),
            get_resolution_adapter("python"),
        )
        scope = syntax.import_scope(3)
        self.assertIsNotNone(scope)
        self.assertEqual(scope.type if scope else None, "function_definition")

    def test_python_conditional_import_shadows_outer_import(self):
        repo = repository(
            "python",
            fixture_sources(
                "resolution_lexical_safety:test_python_conditional_import_shadows_outer_import:103-15"
            ),
        )
        self.assert_call(repo, "R.work()")
        self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_class_import_cannot_be_captured_by_method(self):
        repo = repository(
            "python",
            fixture_sources(
                "resolution_lexical_safety:test_python_class_import_cannot_be_captured_by_method:110-15"
            ),
        )
        self.assert_call(repo, "R.work()", "other.py::R.work")
        self.assert_call(repo, "R.work(1)")
        self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_module_conditional_import_is_visible_after_block(self):
        repo = repository(
            "python",
            fixture_sources(
                "resolution_lexical_safety:test_python_module_conditional_import_is_visible_after_block:125-15"
            ),
        )
        self.assert_call(repo, "R.work()", "tools.py::R.work")

    def test_python_lambda_parameters_are_callback_local(self):
        parameters = [
            "java-lambda-parameter-shapes-are-callback-local-java-01",
            "python-lambda-parameters-are-callback-local-python-02",
            "python-lambda-parameters-are-callback-local-python-03",
            "python-lambda-parameters-are-callback-local-python-04",
            "python-lambda-parameters-are-callback-local-python-05",
        ]
        for parameter in parameters:
            with self.subTest(parameter=parameter):
                repo = repository(
                    "python",
                    fixture_sources(
                        "resolution_lexical_safety:test_python_lambda_parameters_are_callback_local:138-23",
                        parameter=parameter,
                    ),
                )
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_comprehension_and_generator_bindings_do_not_escape(self):
        expressions = [
            "[R.work() for R in items]",
            "(R.work() for R in items)",
            "{R.work() for R in items}",
            "{R: R.work() for R in items}",
            "python-comprehension-and-generator-bindings-do-not-escape-python-05",
            "python-comprehension-and-generator-bindings-do-not-escape-python-06",
        ]
        for expression in expressions:
            with self.subTest(expression=expression):
                repo = repository(
                    "python",
                    fixture_sources(
                        "resolution_lexical_safety:test_python_comprehension_and_generator_bindings_do_not_escape:153-23",
                        expression=expression,
                    ),
                )
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_first_comprehension_iterable_uses_outer_scope(self):
        repo = repository(
            "python",
            fixture_sources(
                "resolution_lexical_safety:test_python_first_comprehension_iterable_uses_outer_scope:158-15"
            ),
        )
        self.assert_call(repo, "R.work()")
        self.assert_call(repo, "R.work(1)", "tools.py::R.work")
        self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_comprehension_walrus_binds_enclosing_function(self):
        repo = repository(
            "python",
            fixture_sources(
                "resolution_lexical_safety:test_python_comprehension_walrus_binds_enclosing_function:164-15"
            ),
        )
        self.assert_call(repo, "R.work()")
        self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_parameter_shadows_local_callable_without_hiding_module_call(self):
        repo = repository(
            "python",
            fixture_sources(
                "resolution_lexical_safety:test_python_parameter_shadows_local_callable_without_hiding_module_call:171-15"
            ),
        )
        edges = [
            edge
            for edge in resolve_connections(repo).connections
            if edge.type == "CALLS" and edge.evidence == "target()"
        ]
        self.assertEqual(len(edges), 2)
        self.assertEqual(
            {
                edge.line: edge.target_key.startswith("symbol:main.py::target:")
                for edge in edges
            },
            {2: False, 3: True},
        )

    def test_javascript_single_and_destructured_callback_parameters(self):
        callbacks = [
            "callback-parameters-javascript-01",
            "callback-parameters-javascript-02",
            "callback-parameters-javascript-03",
            "callback-parameters-javascript-04",
            "callback-parameters-javascript-05",
            "callback-parameters-javascript-06",
            "callback-parameters-javascript-07",
            "callback-parameters-javascript-08",
            "callback-parameters-javascript-09",
            "callback-parameters-javascript-10",
            "callback-parameters-javascript-11",
        ]
        for language, extension in [("javascript", "js"), ("typescript", "ts")]:
            self.check_callback_parameters(language, extension, callbacks)

    def check_callback_parameters(self, language, extension, callbacks):
        for callback in callbacks:
            with self.subTest(language=language, callback=callback):
                repo = repository(
                    language,
                    fixture_sources(
                        "resolution_lexical_safety:check_callback_parameters:209-23",
                        language=language,
                        callback=callback,
                    ),
                )
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", f"tools.{extension}::R.work")

    def test_javascript_property_keys_and_defaults_are_not_bindings(self):
        for callback in [
            "javascript-property-keys-and-defaults-are-not-bindings-javascript-01",
            "javascript-property-keys-and-defaults-are-not-bindings-javascript-02",
        ]:
            with self.subTest(callback=callback):
                repo = repository(
                    "javascript",
                    fixture_sources(
                        "resolution_lexical_safety:test_javascript_property_keys_and_defaults_are_not_bindings:222-23",
                        callback=callback,
                    ),
                )
                self.assert_call(repo, "R.work()", "tools.js::R.work")
                self.assert_call(repo, "R.work(2)", "tools.js::R.work")

    def test_java_lambda_parameter_shapes_are_callback_local(self):
        for parameters in [
            "java-lambda-parameter-shapes-are-callback-local-java-01",
            "java-lambda-parameter-shapes-are-callback-local-java-02",
            "java-lambda-parameter-shapes-are-callback-local-java-03",
            "java-lambda-parameter-shapes-are-callback-local-java-04",
            "java-lambda-parameter-shapes-are-callback-local-java-05",
        ]:
            with self.subTest(parameters=parameters):
                repo = repository(
                    "java",
                    fixture_sources(
                        "resolution_lexical_safety:test_java_lambda_parameter_shapes_are_callback_local:235-23",
                        parameters=parameters,
                    ),
                )
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "R.java::R.work")

    def test_java_blocks_loops_and_catch_bindings_do_not_leak(self):
        bodies = [
            "java-blocks-loops-and-catch-bindings-do-not-leak-java-01",
            "java-blocks-loops-and-catch-bindings-do-not-leak-java-02",
            "java-blocks-loops-and-catch-bindings-do-not-leak-java-03",
            "java-blocks-loops-and-catch-bindings-do-not-leak-java-04",
        ]
        for body in bodies:
            with self.subTest(body=body):
                repo = repository(
                    "java",
                    fixture_sources(
                        "resolution_lexical_safety:test_java_blocks_loops_and_catch_bindings_do_not_leak:259-23",
                        body=body,
                    ),
                )
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "R.java::R.work")

    def test_go_range_and_callback_bindings_do_not_leak(self):
        for body in [
            "go-range-and-callback-bindings-do-not-leak-go-01",
            "go-range-and-callback-bindings-do-not-leak-go-02",
            "go-range-and-callback-bindings-do-not-leak-go-03",
        ]:
            with self.subTest(body=body):
                repo = repository(
                    "go",
                    fixture_sources(
                        "resolution_lexical_safety:test_go_range_and_callback_bindings_do_not_leak:270-23",
                        body=body,
                    ),
                )
                self.assert_call(repo, "R.Work()")
                self.assert_call(repo, "R.Work(2)", "tools.go::Work")

    def test_kotlin_lambda_and_range_bindings_do_not_leak(self):
        for body in [
            "kotlin-lambda-and-range-bindings-do-not-leak-kotlin-01",
            "kotlin-lambda-and-range-bindings-do-not-leak-kotlin-02",
            "for (R in items) {R()}; R(2)",
            "kotlin-lambda-and-range-bindings-do-not-leak-kotlin-04",
        ]:
            with self.subTest(body=body):
                repo = repository(
                    "kotlin",
                    fixture_sources(
                        "resolution_lexical_safety:test_kotlin_lambda_and_range_bindings_do_not_leak:290-23",
                        body=body,
                    ),
                )
                self.assert_call(repo, "R()")
                self.assert_call(repo, "R(2)", "tools.kt::work")


if __name__ == "__main__":
    unittest.main()
