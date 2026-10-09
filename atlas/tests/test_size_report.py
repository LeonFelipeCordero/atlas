"""Size findings share fresh/saved reporting and preserve older indexes."""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json

from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.domain.report import build_artifact_report, render_markdown
from atlas.indexer import analyze_repository


def node(name: str, kind: str = "function", **properties):
    return {
        "stableKey": f"symbol:{name}", "name": name, "qualifiedName": name,
        "kind": kind, "type": kind, "path": "app.py", "startLine": 10,
        "properties": properties,
    }


def test_size_thresholds_are_strict_independent_and_kind_specific() -> None:
    artifact = {"nodes": [
        node("boundary", lineCount=100, parameterCount=7),
        node("long", lineCount=101),
        node("wide", "method", parameterCount=8),
        node("both", lineCount=101, parameterCount=8),
        node("file_boundary", "file", lineCount=600, parameterCount=99),
        node("long_file", "file", lineCount=601),
        node("type", "class", lineCount=601, parameterCount=8),
        node("legacy"),
    ]}
    original = deepcopy(artifact)
    findings = build_artifact_report(artifact)["findings"]
    assert [finding["subject"] for finding in findings] == ["both", "long", "long_file", "wide"]
    assert findings[0] == {
        "type": "size", "subject": "both", "files": [{"path": "app.py", "line": 10}],
        "details": [
            "Function line count is 101 (limit: 100).",
            "Parameter count is 8 (limit: 7).",
        ],
    }
    assert findings[2]["files"] == [{"path": "app.py"}]
    assert findings[2]["details"] == ["File line count is 601 (limit: 600)."]
    assert findings[3]["details"] == ["Parameter count is 8 (limit: 7)."]
    assert artifact == original


def test_size_markdown_and_complexity_findings_coexist() -> None:
    report = build_artifact_report({"nodes": [node("both", lineCount=101, cyclomaticComplexity=9)]})
    assert [finding["type"] for finding in report["findings"]] == ["complexity", "size"]
    assert "## Size: `both`\n\nFiles:\n- `app.py:10`" in render_markdown(report)
    assert "Function line count is 101 (limit: 100)." in render_markdown(report)


def test_size_findings_sort_by_path_line_and_key() -> None:
    nodes = [
        {**node("last", lineCount=101), "path": "z.py"},
        {**node("later", lineCount=101), "startLine": 20},
        node("first", parameterCount=8),
    ]
    findings = build_artifact_report({"nodes": nodes})["findings"]
    assert [finding["subject"] for finding in findings] == ["first", "later", "last"]


def test_receivers_decorator_comments_and_attributes_at_parameter_threshold(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "class C:\n"
        "    def f(me,a,b,c,d,e,f,g): pass\n"
        "    @classmethod\n"
        "    def c(klass,a,b,c,d,e,f,g): pass\n"
        "    @staticmethod # explanation\n"
        "    def s(self,a,b,c,d,e,f,g): pass\n"
        "    def v(*args: int, a=1,b=2,c=3,d=4,e=5,f=6,g=7): pass\n"
    )
    (tmp_path / "app.rs").write_text(
        "fn f(#[allow(unused_variables)] a:i32,b:i32,c:i32,d:i32,e:i32,f:i32,g:i32) {}\n"
    )
    report = build_artifact_report(asdict(analyze_repository(tmp_path)))
    assert [finding["subject"] for finding in report["findings"]] == ["app.py::C.s", "app.py::C.v"]
    assert all(finding["details"] == ["Parameter count is 8 (limit: 7)."] for finding in report["findings"])


def test_cli_fresh_and_saved_size_reports_match_without_sources(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    source = root / "app.py"
    source.write_text("def wide(a, b, c, d, e, f, g, h):\n" + "    pass\n" * 100 + "\n" * 500)
    database = tmp_path / "atlas.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    fresh = runner.invoke(main, ["report", "-f", str(root), "--format", "json"])
    assert fresh.exit_code == 0, fresh.output
    findings = json.loads(fresh.output)["findings"]
    assert len(findings) == 2
    assert findings[0]["details"] == ["File line count is 601 (limit: 600)."]
    assert findings[1]["details"] == [
        "Function line count is 101 (limit: 100).", "Parameter count is 8 (limit: 7).",
    ]
    source.unlink()
    with repository_service(database) as service:
        assert service.report("source") == json.loads(fresh.output)
