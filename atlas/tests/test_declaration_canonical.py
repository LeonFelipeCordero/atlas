"""Declaration identity regressions independent of the coffee snapshots."""

import unittest
from dataclasses import replace
from unittest.mock import patch

from tree_sitter_language_pack import ProcessConfig, StructureItem, process

from atlas.parsing.structure import _declaration_query, extract_structure
from tests.parsing_fixture import parsing_syntax


def merged(source: str, language: str) -> list[StructureItem]:
    return extract_structure(
        parsing_syntax(source, language),
        process(source, ProcessConfig(language=language)).structure,
    )


def names(items: list[StructureItem]) -> list[str | None]:
    return [item.name for item in items]


class CanonicalDeclarationTests(unittest.TestCase):
    def test_kotlin_unnamed_native_overloads_preserve_metadata_and_utf8(self) -> None:
        source = '/* café 😀 */ @Deprecated("old")\nfun élève(value: Int): Int { fun helper() = value; return helper() }\nfun élève(value: String) = value.length\nclass Owner { fun élève() = 0 }'
        native = process(source, ProcessConfig(language="kotlin")).structure
        native[0] = replace(
            native[0], doc_comment="native docs", decorators=["native annotation"]
        )
        original = repr(native)
        items = extract_structure(parsing_syntax(source, "kotlin"), native)
        self.assertEqual(names(items), ["élève", "élève", "Owner"])
        self.assertEqual(names(items[0].children), ["helper"])
        self.assertEqual(names(items[2].children), ["élève"])
        self.assertEqual(items[0].doc_comment, "native docs")
        self.assertEqual(items[0].decorators, ["native annotation"])
        self.assertEqual(items[0].signature, native[0].signature)
        self.assertEqual(repr(native), original)
        span = items[0].span
        assert span is not None
        self.assertEqual(
            source.encode()[span.start_byte : span.end_byte].decode(),
            items[0].signature,
        )
        self.assertNotEqual(items[0].span, items[1].span)

    def test_ts_interface_callable_properties_not_types_or_fields(self) -> None:
        source = """interface Transformer {
  transform: <T>(input: T) => T;
  optional?: ((((value: string) => number)));
  "quoted": () => void;
  [Symbol.iterator]: () => Iterator<string>;
  transform(value: string): string;
  transform(value: number): number;
  count: number;
  nested: { callback: () => void };
  factory: new () => Transformer;
}
"""
        for language in ("typescript", "tsx"):
            with self.subTest(language=language):
                self.assert_interface_properties(source, language)

    def assert_interface_properties(self, source, language):
        items = merged(source, language)
        self.assertEqual(names(items), ["Transformer"])
        children = items[0].children
        self.assertEqual(
            names(children),
            [
                "transform",
                "optional",
                '"quoted"',
                "[Symbol.iterator]",
                "transform",
                "transform",
            ],
        )
        self.assertTrue(
            all(
                str(item.kind).lower() == "method" and not item.children
                for item in children
            )
        )
        for item in children:
            span = item.span
            assert span is not None
            self.assertEqual(
                source.encode()[span.start_byte : span.end_byte].decode(),
                item.signature,
            )

    def test_java_constructor_kind_and_python_decorator_metadata(self) -> None:
        items = merged("class Owner { private Owner() {} void run() {} }", "java")
        self.assertEqual(
            [str(item.kind).lower() for item in items[0].children],
            ["constructor", "method"],
        )
        self.assertEqual(items[0].children[0].visibility, "private")
        source = "@register('café')\nclass Owner:\n @staticmethod\n @annotate(level=1)\n def run():\n  def inner(): pass\n"
        for items in (
            merged(source, "python"),
            extract_structure(parsing_syntax(source, "python")),
        ):
            self.assertEqual(items[0].decorators, ["@register('café')"])
            run = items[0].children[0]
            self.assertEqual(run.decorators, ["@staticmethod", "@annotate(level=1)"])
            self.assertEqual(names(run.children), ["inner"])
            self.assertFalse(run.children[0].decorators)

    def test_python_native_decorated_wrapper_canonicalizes_to_definition(self) -> None:
        source = "@register\nclass Owner:\n @staticmethod\n def run(): pass\n"
        native = process(source, ProcessConfig(language="python")).structure[0]
        assert native.span is not None
        wrapper = replace(
            native,
            span=replace(native.span, start_byte=0, start_line=0, start_column=0),
            doc_comment="class docs",
        )
        items = extract_structure(parsing_syntax(source, "python"), [wrapper])
        self.assertEqual(names(items), ["Owner"])
        self.assertEqual(items[0].span, native.span)
        self.assertEqual(items[0].decorators, ["@register"])
        self.assertEqual(items[0].doc_comment, "class docs")
        self.assertEqual(names(items[0].children), ["run"])

    def test_missing_tags_and_unrelated_native_languages(self) -> None:
        native = [StructureItem(name="Owner", children=[StructureItem(name="run")])]
        _declaration_query.cache_clear()
        try:
            with patch(
                "atlas.parsing.structure.get_tags_query", return_value=None
            ):
                self.assertIs(extract_structure(parsing_syntax(b"", "csharp"), native), native)
                self.assertEqual(extract_structure(parsing_syntax(b"", "csharp")), [])
        finally:
            _declaration_query.cache_clear()
        items = merged("module Demo\n class Owner\n  def run\n  end\n end\nend", "ruby")
        self.assertEqual(names(items), ["Demo"])
        self.assertEqual(names(items[0].children), ["Owner"])
        self.assertEqual(names(items[0].children[0].children), ["run"])


if __name__ == "__main__":
    unittest.main()
