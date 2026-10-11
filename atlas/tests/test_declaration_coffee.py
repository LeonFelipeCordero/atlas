"""Declaration spans and AST ownership across the complete language projects."""

import unittest

from tree_sitter_language_pack import ProcessConfig, StructureItem, get_parser, process

from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_fixture import LANGUAGES, coffee_sources
from tests.project_snapshot_support import structure_value
from tests.test_declaration_callbacks import flatten


def qualified_items(items: list[StructureItem]) -> list[tuple[str, StructureItem]]:
    qualified = {}
    result = []
    for item, parent in flatten(items):
        name = item.name or "<anonymous>"
        path = f"{qualified[id(parent)]}.{name}" if parent else name
        qualified[id(item)] = path
        result.append((path, item))
    return result


class CoffeeDeclarationTests(unittest.TestCase):
    def test_whole_project_spans_ownership_and_native_nonmutation(self) -> None:
        for language in LANGUAGES:
            self.assert_project_spans(language)

    def assert_project_spans(self, language):
        for file in coffee_sources(language):
            self.assert_source_variants(file)

    def assert_source_variants(self, file):
        native = process(file.source.decode(), ProcessConfig(language=file.language)).structure
        before = structure_value(native)
        for existing in ([], native):
            with self.subTest(language=file.language, filename=file.path, native=bool(existing)):
                items = extract_structure(ParsedSyntax(file), existing)
                self.assert_ast_spans(file.source, file.language, items)
                self.assertEqual(structure_value(native), before)

    def assert_ast_spans(
        self, source: bytes, language: str, items: list[StructureItem]
    ) -> None:
        root = get_parser(language).parse(source).root_node
        identities = set()
        nodes = {}
        for item, parent in flatten(items):
            span = item.span
            assert span is not None
            node = root.descendant_for_byte_range(span.start_byte, span.end_byte - 1)
            assert node is not None
            self.assertEqual(
                (span.start_byte, span.end_byte), (node.start_byte, node.end_byte)
            )
            self.assertEqual(
                (span.start_line, span.start_column), tuple(node.start_point)
            )
            self.assertEqual((span.end_line, span.end_column), tuple(node.end_point))
            identity = (node.id, item.name)
            self.assertNotIn(identity, identities)
            identities.add(identity)
            nodes[id(item)] = node
            if parent is None:
                continue
            self.assert_ast_ancestor(node, nodes[id(parent)])

    def assert_ast_ancestor(self, node, parent_node):
        ancestor = node.parent
        while ancestor is not None and ancestor.id != parent_node.id:
            ancestor = ancestor.parent
        self.assertIsNotNone(ancestor)

    def test_source_reviewed_kind_and_decorator_corrections(self) -> None:
        for language in ("java", "python", "typescript"):
            self.assert_source_corrections(language)

    def assert_source_corrections(self, language):
        entries = []
        for file in coffee_sources(language):
            source = file.source
            native = process(
                source.decode(), ProcessConfig(language=language)
            ).structure
            entries.extend(qualified_items(extract_structure(ParsedSyntax(file), native)))
        self.assert_corrections(language, dict(entries))

    def assert_corrections(
        self, language: str, by_name: dict[str, StructureItem]
    ) -> None:
        if language == "java":
            self.assertEqual(by_name["Recipe.Recipe"].kind, "constructor")
            self.assertEqual(by_name["Report.Report"].kind, "constructor")
        if language == "python":
            self.assertEqual(by_name["Brewing.brew"].decorators, ["@abstractmethod"])
            self.assertEqual(by_name["Recipe.portions"].decorators, ["@staticmethod"])
            self.assertEqual(by_name["Report.total"].decorators, ["@staticmethod"])
        if language == "typescript":
            self.assertEqual(by_name["Brewing.brew"].kind, "method")


if __name__ == "__main__":
    unittest.main()
