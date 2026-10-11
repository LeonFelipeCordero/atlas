"""Independent lexical safety probes; no snapshot or coffee-name expectations."""

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
                all(e.target_key.startswith("external:") for e in edges), edges
            )
            return
        self.assertTrue(
            all(
                e.target_key.startswith("symbol:") and target in e.target_key
                for e in edges
            ),
            edges,
        )

    def python_repo(self, usage):
        return repository(
            "python",
            {
                "tools.py": "class R:\n @staticmethod\n def work(tag=None): return tag\n",
                "main.py": "from tools import R\n" + usage,
            },
        )

    def test_python_blocks_bind_in_enclosing_function(self):
        usages = [
            "def run(other):\n if True:\n  R = other\n return R.work()",
            "def run(other):\n R.work()\n if True:\n  R = other",
            "def run(items):\n if True:\n  for R in items: pass\n return R.work()",
            "def run(other):\n with other as R: pass\n return R.work()",
            "def run():\n try: pass\n except Exception as R: pass\n return R.work()",
            "def run(other):\n if True:\n  def R(): pass\n return R.work()",
            "def run():\n if True:\n  class R: pass\n return R.work()",
        ]
        for usage in usages:
            with self.subTest(usage=usage):
                repo = self.python_repo(usage + "\nR.work(2)\n")
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_module_and_class_blocks_are_not_scopes(self):
        repo = self.python_repo("if True:\n R = other\nR.work()")
        self.assert_call(repo, "R.work()")
        repo = self.python_repo(
            "class Container:\n if True:\n  R = other\n R.work()\n"
            " def run(self): return R.work(1)\n"
            " def default(self, value=R.work(3)): pass\n"
            " [R.work(4) for item in R.work(5)]\nR.work(2)"
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
            {
                "tools.py": "class R:\n @staticmethod\n def work(tag=None): pass",
                "main.py": "def run():\n if True:\n  from tools import R\n return R.work()\nR.work(2)",
            },
        )
        self.assert_call(repo, "R.work()", "tools.py::R.work")
        self.assert_call(repo, "R.work(2)")
        syntax = Syntax(
            next(f for f in repo.files if f.source.path == "main.py"),
            get_resolution_adapter("python"),
        )
        scope = syntax.import_scope(3)
        self.assertIsNotNone(scope)
        self.assertEqual(scope.type if scope else None, "function_definition")

    def test_python_conditional_import_shadows_outer_import(self):
        repo = self.python_repo(
            "def run():\n if True:\n  from unavailable import R\n return R.work()\nR.work(2)"
        )
        self.assert_call(repo, "R.work()")
        self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_class_import_cannot_be_captured_by_method(self):
        repo = repository(
            "python",
            {
                "tools.py": "class R:\n @staticmethod\n def work(tag=None): pass",
                "other.py": "class R:\n @staticmethod\n def work(tag=None): pass",
                "main.py": "from tools import R\nclass Container:\n from other import R\n R.work()\n"
                " def run(self): return R.work(1)\nR.work(2)",
            },
        )
        self.assert_call(repo, "R.work()", "other.py::R.work")
        # Reject rather than accidentally selecting the class import by its span.
        self.assert_call(repo, "R.work(1)")
        self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_module_conditional_import_is_visible_after_block(self):
        repo = repository(
            "python",
            {
                "tools.py": "class R:\n @staticmethod\n def work(): pass",
                "main.py": "if True:\n from tools import R\nR.work()",
            },
        )
        self.assert_call(repo, "R.work()", "tools.py::R.work")

    def test_python_lambda_parameters_are_callback_local(self):
        parameters = ["R", "R=other", "*R", "**R", "other, R=other"]
        for parameter in parameters:
            with self.subTest(parameter=parameter):
                repo = self.python_repo(f"use(lambda {parameter}: R.work())\nR.work(2)")
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_comprehension_and_generator_bindings_do_not_escape(self):
        expressions = [
            "[R.work() for R in items]",
            "(R.work() for R in items)",
            "{R.work() for R in items}",
            "{R: R.work() for R in items}",
            "[R.work() for (other, R) in items]",
            "[R.work() for other in items for R in other]",
        ]
        for expression in expressions:
            with self.subTest(expression=expression):
                repo = self.python_repo(expression + "\nR.work(2)")
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_first_comprehension_iterable_uses_outer_scope(self):
        repo = self.python_repo("[R.work() for R in R.work(1)]\nR.work(2)")
        self.assert_call(repo, "R.work()")
        self.assert_call(repo, "R.work(1)", "tools.py::R.work")
        self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_comprehension_walrus_binds_enclosing_function(self):
        repo = self.python_repo(
            "def run(items):\n [(R := item) for item in items]\n return R.work()\nR.work(2)"
        )
        self.assert_call(repo, "R.work()")
        self.assert_call(repo, "R.work(2)", "tools.py::R.work")

    def test_python_parameter_shadows_local_callable_without_hiding_module_call(self):
        repo = repository(
            "python",
            {"main.py": "def target(): pass\ndef caller(target): target()\ntarget()\n"},
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
            "R=>R.work()",
            "(R)=>R.work()",
            "({R})=>R.work()",
            "({key: R})=>R.work()",
            "({key: R=other})=>R.work()",
            "({nested: {R}})=>R.work()",
            "([R])=>R.work()",
            "(...R)=>R.work()",
            "({ ...R })=>R.work()",
            "function R() { return R.work(); }",
            "()=>{function R() {} return R.work();}",
        ]
        for language, extension in [("javascript", "js"), ("typescript", "ts")]:
            self.check_callback_parameters(language, extension, callbacks)

    def check_callback_parameters(self, language, extension, callbacks):
        for callback in callbacks:
            with self.subTest(language=language, callback=callback):
                repo = repository(
                    language,
                    {
                        f"tools.{extension}": "export class R { static work(tag) {} }",
                        f"main.{extension}": f"import {{R}} from './tools'; use({callback}); R.work(2);",
                    },
                )
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", f"tools.{extension}::R.work")

    def test_javascript_property_keys_and_defaults_are_not_bindings(self):
        for callback in ["({R: other})=>R.work()", "({other=R})=>R.work()"]:
            with self.subTest(callback=callback):
                repo = repository(
                    "javascript",
                    {
                        "tools.js": "export class R { static work(tag) {} }",
                        "main.js": f"import {{R}} from './tools'; use({callback}); R.work(2);",
                    },
                )
                self.assert_call(repo, "R.work()", "tools.js::R.work")
                self.assert_call(repo, "R.work(2)", "tools.js::R.work")

    def test_java_lambda_parameter_shapes_are_callback_local(self):
        for parameters in ["R", "(R)", "(R, other)", "(Thing R)", "(var R)"]:
            with self.subTest(parameters=parameters):
                repo = self.java_repo(f"use({parameters} -> R.work()); R.work(2);")
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "R.java::R.work")

    def java_repo(self, body):
        return repository(
            "java",
            {
                "R.java": "package tools; public class R {public static void work(Object... tags) {}}",
                "App.java": "package app; import tools.R; class App {void run(){"
                + body
                + "}}",
            },
        )

    def test_java_blocks_loops_and_catch_bindings_do_not_leak(self):
        bodies = [
            "{ Thing R = other; R.work(); } R.work(2);",
            "for (Thing R : items) {R.work();} R.work(2);",
            "for (Thing R = other; check(); next()) {R.work();} R.work(2);",
            "try {} catch (Exception R) {R.work();} R.work(2);",
        ]
        for body in bodies:
            with self.subTest(body=body):
                repo = self.java_repo(body)
                self.assert_call(repo, "R.work()")
                self.assert_call(repo, "R.work(2)", "R.java::R.work")

    def test_go_range_and_callback_bindings_do_not_leak(self):
        for body in [
            "for R := range items {R.Work()}; R.Work(2)",
            "use(func(R Thing) {R.Work()}); R.Work(2)",
            "use(func(other, R Thing) {R.Work()}); R.Work(2)",
        ]:
            with self.subTest(body=body):
                repo = repository(
                    "go",
                    {
                        "tools/tools.go": "package tools\nfunc Work(tag ...int) {}",
                        "main.go": 'package main\nimport R "./tools"\nfunc run(){'
                        + body
                        + "}",
                    },
                )
                self.assert_call(repo, "R.Work()")
                self.assert_call(repo, "R.Work(2)", "tools.go::Work")

    def test_kotlin_lambda_and_range_bindings_do_not_leak(self):
        for body in [
            "use { R -> R() }; R(2)",
            "use { (other, R) -> R() }; R(2)",
            "for (R in items) {R()}; R(2)",
            "for ((other, R) in items) {R()}; R(2)",
        ]:
            with self.subTest(body=body):
                repo = repository(
                    "kotlin",
                    {
                        "tools.kt": "package tools\nfun work(tag: Int = 0) {}",
                        "main.kt": "package app\nimport tools.work as R\nfun run() {"
                        + body
                        + "}",
                    },
                )
                self.assert_call(repo, "R()")
                self.assert_call(repo, "R(2)", "tools.kt::work")


if __name__ == "__main__":
    unittest.main()
