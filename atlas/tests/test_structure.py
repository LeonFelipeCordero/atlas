from tests.source_snapshot_fixture import case_bytes

import unittest
from dataclasses import replace
from unittest.mock import patch

from tree_sitter_language_pack import ProcessConfig, get_tags_query, process

from atlas.parsing.structure import _declaration_query, extract_structure
from tests.parsing_fixture import parsing_syntax


class StructureTagsTest(unittest.TestCase):
    def setUp(self) -> None:
        _declaration_query.cache_clear()

    def tearDown(self) -> None:
        _declaration_query.cache_clear()

    def test_uses_bundled_tags_with_graph_metadata_and_nesting(self) -> None:
        source = case_bytes('parsing', 'structure-uses_bundled_tags_with_graph_metadata_and_nesting-kotlin', 'sample.kt')
        with patch(
            "atlas.parsing.structure.get_tags_query", wraps=get_tags_query
        ) as tags:
            structure = extract_structure(parsing_syntax(source, "kotlin"))
            tags.assert_called_once_with("kotlin")

        self.assertEqual([item.name for item in structure], ["demo", "Service"])
        service = structure[1]
        self.assertEqual([item.name for item in service.children], ["run", "Factory"])
        run, factory = service.children
        self.assertEqual(run.visibility, "private")
        self.assertEqual(run.decorators, ['@Deprecated("old")'])
        span = run.span
        assert span is not None
        self.assertEqual(span.start_line, 2)
        self.assertEqual(span.end_line, 7)
        self.assertEqual(
            source[span.start_byte : span.end_byte].decode(), run.signature
        )
        self.assertEqual([item.name for item in run.children], ["helper"])
        self.assertEqual([item.name for item in factory.children], ["create"])
        self.assertEqual(factory.kind, "class")

    def test_unnamed_companion_is_a_container_without_duplicate_declarations(
        self,
    ) -> None:
        structure = extract_structure(parsing_syntax(
            case_bytes('parsing', 'structure-unnamed_companion_is_a_container_without_duplicate_declarations-kotlin', 'sample.kt'),
            "kotlin",
        ))
        self.assertEqual(len(structure), 1)
        self.assertEqual([item.name for item in structure[0].children], ["Companion"])
        self.assertEqual(
            [item.name for item in structure[0].children[0].children], ["create"]
        )

    def test_java_methods_constructors_overloads_and_nested_types(self) -> None:
        source = case_bytes('parsing', 'structure-java_methods_constructors_overloads_and_nested_types-java', 'sample.java')
        native = process(source.decode(), ProcessConfig(language="java")).structure
        structure = extract_structure(parsing_syntax(source, "java"), native)
        self.assertEqual(
            [item.name for item in structure], ["demo", "Runner", "Service"]
        )
        self.assertEqual(structure[1].kind, "interface")
        self.assertEqual([item.name for item in structure[1].children], ["run"])
        service = structure[2]
        self.assertEqual(
            [item.name for item in service.children],
            ["Service", "run", "run", "Nested"],
        )
        self.assertEqual(service.children[1].visibility, "private")
        self.assertEqual(service.children[1].decorators, ["@Deprecated"])
        self.assertEqual(
            [item.name for item in service.children[3].children], ["Nested", "work"]
        )
        self.assertEqual(service.signature, native[2].signature)
        self.assertEqual(len(native[2].children), 3)  # Input structure is not mutated.

    def test_other_languages_use_the_same_nesting_and_keep_native_metadata(
        self,
    ) -> None:
        sources = {
            "python": case_bytes('parsing', 'structure-other_languages_use_the_same_nesting_and_keep_native_metadata-python', 'sample.py'),
            "ruby": case_bytes('parsing', 'structure-other_languages_use_the_same_nesting_and_keep_native_metadata-ruby', 'sample.rb'),
            "typescript": case_bytes('parsing', 'structure-other_languages_use_the_same_nesting_and_keep_native_metadata-typescript', 'sample.ts'),
        }
        for language, source in sources.items():
            with self.subTest(language=language):
                self.assert_language_nesting(source, language)

    def assert_language_nesting(self, source, language):
        native = process(source.decode(), ProcessConfig(language=language)).structure
        self.decorate_python_native(native, language)
        structure = extract_structure(parsing_syntax(source, language), native)
        service = structure[0].children[0] if language == "ruby" else structure[0]
        self.assertEqual(service.name, "Service")
        self.assertEqual([item.name for item in service.children], ["run"])
        if language == "python":
            self.assert_python_metadata(service)
        if language == "typescript":
            self.assertEqual([item.name for item in structure], ["Service", "helper"])

    def decorate_python_native(self, native, language):
        if language == "python":
            native[0].children[0] = replace(
                native[0].children[0],
                decorators=["staticmethod"],
                doc_comment="Run docs",
            )

    def assert_python_metadata(self, service):
        self.assertEqual(service.children[0].decorators, ["staticmethod"])
        self.assertEqual(service.children[0].doc_comment, "Run docs")
        self.assertEqual(
            [item.name for item in service.children[0].children], ["helper"]
        )

    def test_missing_bundled_tags_preserves_native_extraction(self) -> None:
        source = case_bytes('parsing', 'structure-missing_bundled_tags_preserves_native_extraction-csharp', 'sample.cs')
        native = process(source.decode(), ProcessConfig(language="csharp")).structure
        with patch("atlas.parsing.structure.get_tags_query", return_value=None):
            self.assertIs(extract_structure(parsing_syntax(source, "csharp"), native), native)

    def test_queries_are_cached_per_language(self) -> None:
        with patch(
            "atlas.parsing.structure.get_tags_query", wraps=get_tags_query
        ) as tags:
            for language in ["kotlin", "java", "kotlin", "java"]:
                _declaration_query(language)
            self.assertEqual(
                [call.args[0] for call in tags.call_args_list], ["kotlin", "java"]
            )


if __name__ == "__main__":
    unittest.main()
