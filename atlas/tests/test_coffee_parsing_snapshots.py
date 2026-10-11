"""Parser-only metadata variants reuse the existing coffee source corpus."""

import pytest
from tree_sitter_language_pack import ProcessConfig, process

from atlas.parsing.structure import extract_structure
from atlas.parsing.syntax import ParsedSyntax
from tests.coffee_fixture import LANGUAGES, coffee_sources
from tests.source_snapshot_fixture import assert_case_snapshot

CASES = [
    (language, source, native)
    for language in LANGUAGES
    for source in coffee_sources(language)
    for native in (False, True)
]


def coffee_parsing_id(language, source, native):
    path_id = (
        source.path.removeprefix("src/coffee/").replace("/", "--").replace(".", "-")
    )
    return f"{language}-{path_id}-native-{'on' if native else 'off'}"


def coffee_structure(source, native):
    existing = (
        process(
            source.source.decode(), ProcessConfig(language=source.language)
        ).structure
        if native
        else []
    )
    return extract_structure(ParsedSyntax(source), existing)


@pytest.mark.parametrize(
    "language,source,native",
    CASES,
    ids=[coffee_parsing_id(*case) for case in CASES],
)
def test_coffee_parser_metadata_snapshot(language, source, native):
    assert_case_snapshot(
        "coffee-parsing",
        coffee_parsing_id(language, source, native),
        coffee_structure(source, native),
    )
