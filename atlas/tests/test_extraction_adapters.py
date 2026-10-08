"""Focused extraction-policy tests independent of graph resolution."""

import unittest
from pathlib import Path

from tree_sitter_language_pack import get_parser

from atlas.adapters import DEFAULT_ADAPTER, get_adapter
from atlas.discovery import SourceFile
from atlas.extraction.parser import parse_file
from atlas.extraction.syntax import walk
from atlas.extraction.structure import extract_structure


class ExtractionAdapterTest(unittest.TestCase):
    def test_per_language_inheritance_and_generic_fallback(self):
        for language, signature, expected in [
            (
                "java",
                "class Child extends Base implements Service {}",
                ["Base", "Service"],
            ),
            ("kotlin", "class Child : Base(), Service {}", ["Base", "Service"]),
            (
                "typescript",
                "class Child extends Base implements Service {}",
                ["Base", "Service"],
            ),
            ("python", "class Child(Base, pkg.Mixin):\n pass", ["Base", "pkg.Mixin"]),
            ("javascript", "class Child extends Base {}", ["Base"]),
        ]:
            with self.subTest(language=language):
                self.assertEqual(
                    get_adapter(language).inheritance(language, "class", signature),
                    expected,
                )
        self.assertEqual(
            get_adapter("typescript").inheritance(
                "typescript",
                "interface",
                "interface Child extends pkg.Base, Service {}",
            ),
            ["pkg.Base", "Service"],
        )
        self.assertIs(get_adapter("ruby"), DEFAULT_ADAPTER)

    def test_jsx_tag_name_sites_are_references_without_swallowing_attribute_calls(self):
        sample = b"const App = () => <><Card onClick={() => brew()}/><UI.Card/><div/><custom-card/><svg:path/><Card></Card></>;"
        for language in ("javascript", "tsx"):
            with self.subTest(language=language):
                self.assert_jsx_reference_calls(language, sample)

    def assert_jsx_reference_calls(self, language, sample):
        parsed = parse_file(SourceFile("App.jsx", Path("App.jsx"), language, sample))
        self.assertEqual(
            [
                (call.evidence, call.relationship, call.qualifier)
                for call in parsed.calls
            ],
            [
                ("Card", "REFERENCES", None),
                ("brew()", "CALLS", None),
                ("UI.Card", "REFERENCES", "UI"),
                ("Card", "REFERENCES", None),
            ],
        )
        self.assertTrue(
            all(
                call.end_byte - call.start_byte == len(call.evidence.encode())
                for call in parsed.calls
            )
        )

    def test_decorators_visibility_and_import_supplement_owned_by_adapters(self):
        for language, code, node_type, visibility, decorators in [
            (
                "java",
                b"@Deprecated public class Service {}",
                "class_declaration",
                "public",
                ["@Deprecated"],
            ),
            ("rust", b"pub struct Service {}", "struct_item", None, []),
        ]:
            with self.subTest(language=language):
                self.assert_declaration_metadata(
                    language, code, node_type, visibility, decorators
                )
        for language, code, expected in [
            ("kotlin", b"import demo.Service\n", [("import demo.Service", 1)]),
            ("rust", b"mod external;\nmod inline {}", [("mod external;", 1)]),
        ]:
            source = SourceFile("sample", Path("sample"), language, code)
            self.assertEqual(get_adapter(language).imports(source, []), expected)

    def assert_declaration_metadata(
        self, language, code, node_type, visibility, decorators
    ):
        root = get_parser(language).parse(code).root_node
        node = next(node for node in walk(root) if node.type == node_type)
        actual_visibility, actual_decorators = get_adapter(language).metadata(node)
        self.assertEqual(actual_visibility, visibility)
        self.assertEqual(actual_decorators, decorators)

    def test_rust_macro_payload_remains_rust_only(self):
        code = b'fn run() { println!("{}", helper()); }'
        root = get_parser("rust").parse(code).root_node
        rust = get_adapter("rust")
        sites = list(rust.call_sites(root))
        self.assertEqual(
            [rust.normalize_call(site)[0] for site in sites], ["println!", "helper"]
        )
        self.assertEqual([site[2] for site in sites], [False, True])
        self.assertTrue(extract_structure(b"def run():\n pass\n", "python"))


if __name__ == "__main__":
    unittest.main()
