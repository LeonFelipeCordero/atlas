"""Adapter contracts and the Python-only language support boundary."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from typing import get_args

from tree_sitter_language_pack import SupportedLanguage, available_languages, get_parser

from atlas.parsing.adapters import ADAPTERS, DEFAULT_ADAPTER, get_adapter
from atlas.parsing.syntax import DeclarationCarrier, ImportPolicy, ParsedSyntax
from tests.parsing_fixture import parsing_syntax
from atlas.parsing.discovery import SourceFile, detect_language, discover_files
from atlas.parsing.parser import parse_file
from atlas.parsing.syntax import supplement_imports
from atlas.syntax import walk
from atlas.parsing.discovery import EXCLUDED_LANGUAGES, SUPPORTED_LANGUAGES
from atlas.parsing.structure import _declaration_query, extract_structure


class AdapterContractTest(unittest.TestCase):
    def test_registry_is_overrides_not_the_language_support_list(self):
        self.assertEqual(
            SUPPORTED_LANGUAGES,
            (frozenset(get_args(SupportedLanguage)) | frozenset(available_languages()))
            - {"c", "cpp"},
        )
        self.assertEqual(EXCLUDED_LANGUAGES, {"c", "cpp"})
        for language in ["ruby", "csharp", "json", "html", "agda"]:
            with self.subTest(language=language):
                self.assertIn(language, SUPPORTED_LANGUAGES)
                self.assertIs(get_adapter(language), DEFAULT_ADAPTER)
        self.assertNotIn("c", ADAPTERS)
        self.assertNotIn("cpp", ADAPTERS)

    def test_hooks_return_common_carriers_and_call_site_contracts(self):
        samples = {
            "java": "class Service { Service() {} void run() { helper(); } }",
            "kotlin": "class Service { fun run() = helper() }",
            "go": "package demo\nfunc run() { f := func() { helper() }; f() }",
            "rust": 'fn run() { println!("{}", helper()); }',
            "javascript": "const run = () => helper();",
            "typescript": "interface Service { run: () => number; } function run() { helper(); }",
            "python": "def run():\n    helper()\n",
            "elixir": "defmodule Service do\n  def run(), do: helper()\nend",
        }
        for language, sample in samples.items():
            with self.subTest(language=language):
                self.assert_sample_contract(language, sample)

    def assert_sample_contract(self, language, sample):
        adapter = get_adapter(language)
        root = get_parser(language).parse(sample.encode()).root_node
        self.assert_declaration_carriers(adapter, root)
        sites = list(adapter.call_sites(root))
        self.assertTrue(sites)
        for site in sites:
            self.assert_call_site_contract(adapter, site, sample)
        parsed = parse_file(
            SourceFile("sample", Path("sample"), language, sample.encode())
        )
        self.assertIsNone(parsed.parse_error)
        self.assertTrue(parsed.symbols)
        self.assertTrue(parsed.calls)

    def assert_declaration_carriers(self, adapter, root):
        for node in walk(root):
            carrier = adapter.normalize_declaration(node)
            self.assertTrue(carrier is None or isinstance(carrier, DeclarationCarrier))

    def assert_call_site_contract(self, adapter, site, sample):
        node, offset, opaque, parents = site
        self.assertGreaterEqual(node.start_byte + offset, 0)
        self.assertLessEqual(node.end_byte + offset, len(sample.encode()))
        self.assertIsInstance(opaque, bool)
        self.assertIsInstance(parents, tuple)
        name, bare, qualifier = adapter.normalize_call((node, offset, opaque, parents))
        self.assertTrue(name is None or isinstance(name, str))
        self.assertIsInstance(bare, bool)
        self.assertTrue(qualifier is None or isinstance(qualifier, str))

    def test_kotlin_recovery_and_hierarchy_remain_shared(self):
        source = b"""package demo
class Service {
    companion object Factory {
        fun run() = helper()
    }
}
"""
        structure = extract_structure(parsing_syntax(source, "kotlin"), [])
        self.assertEqual([item.name for item in structure], ["demo", "Service"])
        factory = structure[1].children[0]
        self.assertEqual(factory.name, "Factory")
        self.assertEqual([item.name for item in factory.children], ["run"])

    def test_adapter_import_supplements_keep_original_evidence_and_line(self):
        for language, sample, imports in [
            (
                "kotlin",
                b"package demo\nimport demo.Helper\nclass Service {}",
                [("import demo.Helper", 2)],
            ),
            ("rust", b"mod helper;\nmod inline { fn run() {} }", [("mod helper;", 1)]),
        ]:
            with self.subTest(language=language):
                file = SourceFile("sample", Path("sample"), language, sample)
                adapter = get_adapter(language)
                self.assertEqual(adapter.imports(ParsedSyntax(file), []), imports)
                self.assertEqual(adapter.imports(ParsedSyntax(file), imports), imports)

    def test_shared_import_merging_defers_inline_module_policy_to_adapter(self):
        sample = b"mod external;\nmod inline { fn run() {} }"
        file = SourceFile("sample.rs", Path("sample.rs"), "rust", sample)
        self.assertEqual(
            supplement_imports(ParsedSyntax(file), [], ImportPolicy("mod_item")),
            [("mod external;", 1), ("mod inline { fn run() {} }", 2)],
        )
        self.assertEqual(get_adapter("rust").imports(ParsedSyntax(file), []), [("mod external;", 1)])


class LanguageSupportTest(unittest.TestCase):
    def test_unrecognized_filenames_return_none(self):
        for name in ["main.atlas_unknown_language", "no-extension"]:
            with self.subTest(name=name):
                self.assertIsNone(detect_language(Path(name)))

    def test_discovery_propagates_language_detection_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("pass\n")
            with (
                patch("atlas.parsing.discovery.detect_language_from_path", side_effect=RuntimeError("detection failed")),
                self.assertRaisesRegex(RuntimeError, "detection failed"),
            ):
                discover_files(root)

    def test_discovery_excludes_c_and_cpp_without_narrowing_other_grammars(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in [
                "main.c",
                "main.h",
                "main.cpp",
                "main.hpp",
                "main.cc",
                "main.cxx",
            ]:
                (root / name).write_text("void run() {}")
                self.assertIsNone(detect_language(root / name), name)
            for name in [
                "main.py",
                "main.kt",
                "main.go",
                "main.java",
                "main.rs",
                "main.js",
                "main.ts",
                "main.ex",
                "main.rb",
                "main.agda",
                "data.json",
            ]:
                (root / name).write_text("")
                self.assertIsNotNone(detect_language(root / name), name)
            files = discover_files(root)
            self.assertEqual(len(files), 11)
            self.assertFalse({"c", "cpp"} & {file.language for file in files})

    def test_call_parser_failure_propagates(self):
        source = SourceFile("main.py", Path("main.py"), "python", b"pass\n")
        with patch("atlas.parsing.parser.get_parser", side_effect=RuntimeError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                parse_file(source)

    def test_native_processing_failure_propagates(self):
        source = SourceFile("main.py", Path("main.py"), "python", b"pass\n")
        with patch("atlas.parsing.parser.process", side_effect=RuntimeError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                parse_file(source)

    def test_direct_extraction_rejects_c_cpp_before_parsing_or_queries(self):
        for language in ["c", "cpp"]:
            with self.subTest(language=language):
                file = SourceFile("main", Path("main"), language, b"void run() {}")
                with patch("atlas.parsing.parser.process") as process:
                    with patch("atlas.parsing.parser.get_parser") as parser:
                        with self.assertRaisesRegex(
                            ValueError, "Unsupported Python importer"
                        ):
                            parse_file(file)
                        process.assert_not_called()
                        parser.assert_not_called()
                _declaration_query.cache_clear()
                with patch("atlas.parsing.structure.get_tags_query") as query:
                    with self.assertRaisesRegex(
                        ValueError, "Unsupported Python importer"
                    ):
                        extract_structure(ParsedSyntax(file))
                    query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
