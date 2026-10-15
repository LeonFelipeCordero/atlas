"""Adapter contracts exercised on whole coffee application modules."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import get_args
from unittest.mock import patch

from tree_sitter_language_pack import SupportedLanguage, available_languages

from atlas.parsing.adapters import ADAPTERS, DEFAULT_ADAPTER, get_adapter
from atlas.parsing.discovery import (
    EXCLUDED_LANGUAGES, SUPPORTED_LANGUAGES, SourceFile, detect_language, discover_files,
)
from atlas.parsing.parser import parse_file
from atlas.parsing.structure import _declaration_query, extract_structure
from atlas.parsing.syntax import DeclarationCarrier, ImportPolicy, ParsedSyntax, supplement_imports
from atlas.syntax import walk
from tests.coffee_consolidation import coffee_source


class AdapterContractTest(unittest.TestCase):
    def test_registry_is_overrides_not_the_language_support_list(self):
        self.assertEqual(
            SUPPORTED_LANGUAGES,
            (frozenset(get_args(SupportedLanguage)) | frozenset(available_languages()))
            - {"c", "cpp", "php", "phpdoc", "csharp", "ruby", "rbs"},
        )
        self.assertEqual(EXCLUDED_LANGUAGES, {"c", "cpp", "php", "phpdoc", "csharp", "ruby", "rbs"})
        for language in ["json", "html", "agda"]:
            with self.subTest(language=language):
                self.assertIn(language, SUPPORTED_LANGUAGES)
                self.assertIs(get_adapter(language), DEFAULT_ADAPTER)
        self.assertFalse(EXCLUDED_LANGUAGES & ADAPTERS.keys())

    def test_hooks_return_common_carriers_and_call_site_contracts(self):
        for language, path in [
            ("java", "orders/OrderService.java"),
            ("kotlin", "orders/OrderService.kt"),
            ("go", "reporting/Dispatch.go"),
            ("rust", "Dispatch.rs"),
            ("javascript", "ordering/Orders.js"),
            ("typescript", "ordering/Orders.ts"),
            ("tsx", "App.tsx"),
            ("python", "src/coffee/orders/service.py"),
            ("elixir", "reporting/Dispatch.ex"),
        ]:
            with self.subTest(language=language):
                self.assert_source_contract(coffee_source(language, path))

    def assert_source_contract(self, source):
        adapter = get_adapter(source.language)
        root = ParsedSyntax(source).tree()
        self.assertFalse(root.has_error)
        carriers = [adapter.normalize_declaration(node) for node in walk(root)]
        self.assertTrue(any(isinstance(carrier, DeclarationCarrier) for carrier in carriers))
        self.assertTrue(all(carrier is None or isinstance(carrier, DeclarationCarrier) for carrier in carriers))
        sites = list(adapter.call_sites(root))
        self.assertTrue(sites)
        for site in sites:
            self.assert_call_site_contract(source, site)
        parsed = parse_file(source)
        self.assertIsNone(parsed.parse_error)
        self.assertTrue(parsed.symbols)
        self.assertTrue(parsed.calls)
        for call in parsed.calls:
            self.assertEqual(source.source[call.start_byte:call.end_byte].decode(), call.evidence)

    def assert_call_site_contract(self, source, site):
        node, offset, opaque, parents = site
        self.assertGreaterEqual(node.start_byte + offset, 0)
        self.assertLessEqual(node.end_byte + offset, len(source.source))
        self.assertIsInstance(opaque, bool)
        self.assertIsInstance(parents, tuple)
        name, bare, qualifier = get_adapter(source.language).normalize_call(site)
        self.assertTrue(name is None or isinstance(name, str))
        self.assertIsInstance(bare, bool)
        self.assertTrue(qualifier is None or isinstance(qualifier, str))

    def test_kotlin_recovery_and_hierarchy_remain_shared(self):
        source = coffee_source("kotlin", "reporting/Dispatch.kt")
        structure = extract_structure(ParsedSyntax(source), [])
        self.assertEqual([item.name for item in structure], ["coffee.reporting", "DispatchFormatter", "Dispatch"])
        factory = structure[2].children[-1]
        self.assertEqual((factory.name, factory.kind), ("Factory", "class"))
        self.assertEqual([item.name for item in factory.children], ["console"])

    def test_adapter_import_supplements_keep_original_evidence_and_line(self):
        for language, path, expected in [
            ("kotlin", "reporting/Dispatch.kt", [
                ("import coffee.orders.Order", 3),
                ("import coffee.orders.OrderStatus", 4),
                ("import coffee.orders.receipt", 5),
            ]),
            ("rust", "main.rs", [
                ("mod brewing;", 1), ("mod reporting;", 2), ("mod dispatch;", 4),
            ]),
        ]:
            with self.subTest(language=language):
                self.assert_import_supplements(ParsedSyntax(coffee_source(language, path)), expected)

    def assert_import_supplements(self, syntax, expected):
        native = list(reversed(expected))
        original = native.copy()
        adapter = get_adapter(syntax.source.language)
        self.assertEqual(adapter.imports(syntax, []), expected)
        self.assertEqual(adapter.imports(syntax, native), expected)
        self.assertEqual(native, original)
        for evidence, line in expected:
            self.assertEqual(syntax.source.source.decode().splitlines()[line - 1], evidence)

    def test_shared_import_merging_defers_inline_module_policy_to_adapter(self):
        source = coffee_source("rust", "Dispatch.rs")
        syntax = ParsedSyntax(source)
        self.assertEqual(supplement_imports(syntax, [], ImportPolicy("mod_item")), [
            ("mod dispatch_report;", 2),
            ('mod dispatch_labels {\n    pub fn pickup(name: &str) -> String {\n        format!("pickup:{}", name)\n    }\n}', 6),
        ])
        self.assertEqual(get_adapter("rust").imports(syntax, []), [("mod dispatch_report;", 2)])


class LanguageSupportTest(unittest.TestCase):
    def test_unrecognized_filenames_return_none(self):
        for name in ["main.atlas_unknown_language", "no-extension"]:
            with self.subTest(name=name):
                self.assertIsNone(detect_language(Path(name)))

    def test_discovery_propagates_language_detection_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dispatch.py").write_bytes(coffee_source("python", "src/coffee/reporting/dispatch.py").source)
            with (
                patch("atlas.parsing.discovery.detect_language_from_path", side_effect=RuntimeError("detection failed")),
                self.assertRaisesRegex(RuntimeError, "detection failed"),
            ):
                discover_files(root)

    def test_discovery_excludes_retired_languages_without_narrowing_other_grammars(self):
        # Detection is an extension boundary, independent of source validity.
        application = coffee_source("java", "reporting/Dispatch.java").source
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for extension in ("c", "h", "cpp", "hpp", "cc", "cxx", "php", "cs", "rb"):
                path = root / f"Dispatch.{extension}"
                path.write_bytes(application)
                self.assertIsNone(detect_language(path), extension)
            expected = {
                "py": "python", "kt": "kotlin", "go": "go", "java": "java",
                "rs": "rust", "js": "javascript", "ts": "typescript", "ex": "elixir",
                "agda": "agda", "json": "json",
            }
            for extension, language in expected.items():
                path = root / f"Dispatch.{extension}"
                path.write_bytes(application)
                self.assertEqual(detect_language(path), language)
            files = discover_files(root)
            self.assertEqual({file.path: file.language for file in files}, {
                f"Dispatch.{extension}": language for extension, language in expected.items()
            })
            self.assertFalse(EXCLUDED_LANGUAGES & {file.language for file in files})

    def test_call_parser_failure_propagates(self):
        source = coffee_source("python", "src/coffee/orders/service.py")
        with patch("atlas.parsing.parser.get_parser", side_effect=RuntimeError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                parse_file(source)

    def test_native_processing_failure_propagates(self):
        source = coffee_source("python", "src/coffee/orders/service.py")
        with patch("atlas.parsing.parser.process", side_effect=RuntimeError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                parse_file(source)

    def test_direct_extraction_rejects_excluded_languages_before_parsing_or_queries(self):
        source = coffee_source("java", "reporting/Dispatch.java")
        for language in sorted(EXCLUDED_LANGUAGES):
            with self.subTest(language=language):
                self.assert_unsupported_extraction(replace(source, language=language))

    def assert_unsupported_extraction(self, file: SourceFile):
        with (
            patch("atlas.parsing.parser.process") as process,
            patch("atlas.parsing.parser.get_parser") as parser,
            self.assertRaisesRegex(ValueError, "Unsupported Python importer"),
        ):
            parse_file(file)
        process.assert_not_called()
        parser.assert_not_called()
        _declaration_query.cache_clear()
        try:
            with (
                patch("atlas.parsing.structure.get_tags_query") as query,
                patch("atlas.parsing.syntax.get_parser") as syntax_parser,
            ):
                with self.assertRaisesRegex(ValueError, "Unsupported Python importer"):
                    extract_structure(ParsedSyntax(file))
                query.assert_not_called()
                syntax_parser.assert_not_called()
        finally:
            _declaration_query.cache_clear()


if __name__ == "__main__":
    unittest.main()
