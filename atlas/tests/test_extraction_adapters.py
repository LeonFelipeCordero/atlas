"""Focused extraction-policy tests independent of graph resolution."""

from tests.source_snapshot_fixture import case_bytes, case_text

import unittest
from dataclasses import dataclass
from pathlib import Path

from tree_sitter_language_pack import get_parser

from atlas.parsing.adapters import DEFAULT_ADAPTER, get_adapter
from atlas.parsing.discovery import SourceFile
from atlas.parsing.parser import parse_file
from atlas.syntax import walk
from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import DeclarationHeader, ParsedSyntax
from tests.parsing_fixture import parsing_syntax


@dataclass(frozen=True)
class MetadataCase:
    syntax: ParsedSyntax
    node_type: str
    visibility: str | None
    decorators: list[str]


class ExtractionAdapterTest(unittest.TestCase):
    def test_per_language_inheritance_and_generic_fallback(self):
        for language, signature, expected in [
            (
                "java",
                case_text('parsing', 'extraction_adapters-per_language_inheritance_and_generic_fallback-java', 'sample.java'),
                ["Base", "Service"],
            ),
            ("kotlin", case_text('parsing', 'extraction_adapters-per_language_inheritance_and_generic_fallback-kotlin', 'sample.kt'), ["Base", "Service"]),
            (
                "typescript",
                case_text('parsing', 'extraction_adapters-per_language_inheritance_and_generic_fallback-java', 'sample.java'),
                ["Base", "Service"],
            ),
            ("python", case_text('parsing', 'extraction_adapters-per_language_inheritance_and_generic_fallback-python', 'sample.py'), ["Base", "pkg.Mixin"]),
            ("javascript", case_text('parsing', 'extraction_adapters-per_language_inheritance_and_generic_fallback-javascript', 'sample.js'), ["Base"]),
        ]:
            with self.subTest(language=language):
                self.assertEqual(
                    get_adapter(language).inheritance(DeclarationHeader(language, "class", signature)),
                    expected,
                )
        self.assertEqual(
            get_adapter("typescript").inheritance(
                DeclarationHeader("typescript", "interface", case_text('parsing', 'extraction_adapters-per_language_inheritance_and_generic_fallback-typescript-2', 'sample.ts')),
            ),
            ["pkg.Base", "Service"],
        )
        self.assertIs(get_adapter("ruby"), DEFAULT_ADAPTER)

    def test_jsx_tag_name_sites_are_references_without_swallowing_attribute_calls(self):
        sample = case_bytes('parsing', 'extraction_adapters-jsx_tag_name_sites_are_references_without_swallowing_attribute_calls-javascript', 'App.jsx')
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
                case_bytes('parsing', 'extraction_adapters-decorators_visibility_and_import_supplement_owned_by_adapters-java', 'sample.java'),
                "class_declaration",
                "public",
                ["@Deprecated"],
            ),
            ("rust", case_bytes('parsing', 'extraction_adapters-decorators_visibility_and_import_supplement_owned_by_adapters-rust', 'sample.rs'), "struct_item", None, []),
        ]:
            with self.subTest(language=language):
                self.assert_declaration_metadata(
                    MetadataCase(parsing_syntax(code, language), node_type, visibility, decorators)
                )
        for language, code, expected in [
            ("kotlin", case_bytes('parsing', 'extraction_adapters-decorators_visibility_and_import_supplement_owned_by_adapters-kotlin', 'sample.kt'), [("import demo.Service", 1)]),
            ("rust", case_bytes('parsing', 'extraction_adapters-decorators_visibility_and_import_supplement_owned_by_adapters-rust-2', 'sample.rs'), [("mod external;", 1)]),
        ]:
            source = SourceFile("sample", Path("sample"), language, code)
            self.assertEqual(get_adapter(language).imports(ParsedSyntax(source), []), expected)

    def assert_declaration_metadata(self, case: MetadataCase):
        node = next(node for node in walk(case.syntax.tree()) if node.type == case.node_type)
        actual_visibility, actual_decorators = get_adapter(case.syntax.source.language).metadata(node)
        self.assertEqual(actual_visibility, case.visibility)
        self.assertEqual(actual_decorators, case.decorators)

    def test_rust_macro_payload_remains_rust_only(self):
        code = case_bytes('parsing', 'extraction_adapters-rust_macro_payload_remains_rust_only-rust', 'sample.rs')
        root = get_parser("rust").parse(code).root_node
        rust = get_adapter("rust")
        sites = list(rust.call_sites(root))
        self.assertEqual(
            [rust.normalize_call(site)[0] for site in sites], ["println!", "helper"]
        )
        self.assertEqual([site[2] for site in sites], [False, True])
        self.assertTrue(extract_structure(parsing_syntax(case_bytes('parsing', 'extraction_adapters-rust_macro_payload_remains_rust_only-python', 'sample.py'), "python")))


if __name__ == "__main__":
    unittest.main()
