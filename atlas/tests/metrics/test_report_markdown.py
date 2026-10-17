"""Literal Markdown output, metric formatting, and optional report sections."""

import pytest

from atlas.metrics.report_markdown import code, location, render_markdown, value_text


@pytest.fixture
def report():
    return {"summary": {"files": 0}, "nodes": [], "circularImports": [], "diagnostics": []}


@pytest.mark.parametrize(("source", "expected"), [
    ("plain", "`plain`"), ("a|b\nc\rd", "`a\\|b c d`"),
    ("`edge`", "`` `edge` ``"), ("a``b", "```a``b```"), ("", "``"),
])
def test_code_escapes_table_breaks_and_chooses_unused_fence(source, expected):
    assert code(source) == expected


@pytest.mark.parametrize(("node", "expected"), [
    ({}, "Unknown file"), ({"path": "a.py", "line": 0}, "a.py:0"),
    ({"path": "a.py", "line": None}, "a.py"), ({"path": "", "line": 2}, "Unknown file:2"),
])
def test_location_preserves_zero_and_uses_unknown_path(node, expected):
    assert location(node) == expected


@pytest.mark.parametrize(("value", "expected"), [(None, "N/A"), (0, "0"), (0.0, "0.00"), (1.236, "1.24"), ("raw", "raw")])
def test_value_text_distinguishes_unavailable_zero_and_float(value, expected):
    assert value_text(value) == expected


def test_empty_report_has_no_optional_sections(report):
    assert render_markdown(report) == "# Metrics\n\n- files: 0"


def test_size_and_dependency_tables_have_exact_labels_order_and_values(report):
    report["nodes"] = [
        {"kind": "file", "subject": "a|b", "path": "a.py", "line": 1,
         "metrics": {"lineCount": 0, "functionCount": 1, "measuredFunctionCount": 0, "weightedComplexitySum": 0,
                     "fanIn": 0, "fanOut": 2, "transitiveChangeImpact": 3, "instability": 1.0}},
        {"kind": "method", "subject": "run", "path": None, "line": None,
         "metrics": {"parameterCount": 0, "cyclomaticComplexity": 1, "weightedComplexity": 4,
                     "nestedDecisionPenalty": 2, "nestedLoops": 1, "maxDecisionDepth": 3}},
    ]

    assert render_markdown(report) == (
        "# Metrics\n\n- files: 0\n\n## Files\n\n"
        "| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| `a\\|b` | `a.py:1` | 0 | 1 | 0 | 0 |\n\n## Callables\n\n"
        "| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| `run` | `Unknown file` | N/A | 0 | 1 | 4 | 2 | 1 | 3 |\n\n## Dependencies\n\n"
        "| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| `a\\|b` | `a.py:1` | 0 | 2 | 3 | 1.00 |\n\n"
        "Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. "
        "Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.")


def test_cycles_and_diagnostics_render_literal_paths_in_order(report):
    report["circularImports"] = [{"groupSize": 2, "internalDependencyCount": 3,
                                  "files": ["a.py", "b.py"], "exampleCycle": ["a.py", "b.py", "a.py"]}]
    report["diagnostics"] = [{"path": None, "message": "parse failed"}, {"path": "a|b.py", "message": "bad node"}]

    assert render_markdown(report) == (
        "# Metrics\n\n- files: 0\n\n## Circular imports\n\n### Group 1\n\n"
        "Files: 2. Internal dependencies: 3.\n- `a.py`\n- `b.py`\n\n"
        "Example cycle: `a.py` → `b.py` → `a.py`\n\n## Analysis diagnostics\n\n"
        "- `Unknown file`: parse failed\n- `a\\|b.py`: bad node")


def test_mutation_candidates_sort_counts_but_preserve_site_order_and_byte_columns(report):
    report["mutationCandidates"] = [
        {"path": "café.py", "span": {"startLine": 2, "startColumn": 0}, "kind": "unary", "operator": None, "originalText": "`x`"},
        {"path": "a.py", "span": {"startLine": 1, "startColumn": 4}, "kind": "binary", "operator": "|", "originalText": "a|b\nc"},
        {"path": "b.py", "span": {"startLine": 3, "startColumn": 2}, "kind": "binary", "operator": "+", "originalText": "a+b"},
    ]

    assert render_markdown(report) == (
        "# Metrics\n\n- files: 0\n\n## Mutation candidates\n\n"
        "Identified source sites only; no mutations generated or tests executed.\n\n"
        "binary: 2, unary: 1\n\n| Location (byte columns) | Kind | Operator | Original source |\n"
        "| --- | --- | --- | --- |\n"
        "| `café.py:2:0` | `unary` | `—` | `` `x` `` |\n"
        "| `a.py:1:4` | `binary` | `\\|` | `a\\|b c` |\n"
        "| `b.py:3:2` | `binary` | `+` | `a+b` |")
