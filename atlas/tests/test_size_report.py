"""Size measurements stay quantitative; only configured checks impose limits."""

from dataclasses import asdict
import json
from pathlib import Path

from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.indexer import analyze_repository
from atlas.metrics.check import build_check
from atlas.metrics.config import CheckConfig
from atlas.metrics.report import build_artifact_report


def size_config() -> CheckConfig:
    return CheckConfig(maxWeightedComplexity=None, maxDecisionDepth=None, maxNestedLoops=None)


def node(name: str, kind: str = "function", **properties):
    return {
        "stableKey": f"symbol:{name}", "name": name, "qualifiedName": name,
        "kind": kind, "type": kind, "level": "file" if kind == "file" else "callable",
        "path": "app.py", "startLine": 10, "parentStableKey": None, "properties": properties,
    }


def test_size_limits_are_strict_and_kind_specific() -> None:
    report = build_artifact_report({"nodes": [
        node("boundary", lineCount=100, parameterCount=3),
        node("both", lineCount=101, parameterCount=4),
        node("file_boundary", "file", lineCount=600, parameterCount=99),
        node("long_file", "file", lineCount=601),
        node("type", "class", lineCount=601, parameterCount=4),
    ]})
    findings = build_check(report, size_config())["findings"]
    assert [(finding["subject"], finding["rule"]) for finding in findings] == [
        ("both", "maxFunctionLines"), ("both", "maxParameters"), ("long_file", "maxFileLines"),
    ]
    assert findings[1]["actual"] == 4 and findings[1]["limit"] == 3


def test_receivers_decorator_comments_and_attributes_at_parameter_threshold(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "class C:\n"
        "    def f(me,a,b,c): pass\n"
        "    @classmethod\n"
        "    def c(klass,a,b,c): pass\n"
        "    @staticmethod # explanation\n"
        "    def s(self,a,b,c): pass\n"
        "    def v(*args: int, a=1,b=2,c=3): pass\n"
    )
    (tmp_path / "app.rs").write_text("fn f(#[allow(unused_variables)] a:i32,b:i32,c:i32) {}\n")
    report = build_artifact_report(asdict(analyze_repository(tmp_path)))
    findings = build_check(report, size_config())["findings"]
    assert [finding["subject"] for finding in findings] == ["app.py::C.s", "app.py::C.v"]
    assert all(finding["actual"] == 4 and finding["limit"] == 3 for finding in findings)


def test_cli_fresh_and_saved_measurements_match_without_sources(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    source = root / "app.py"
    source.write_text("def wide(a, b, c, d):\n" + "    pass\n" * 100 + "\n" * 500)
    database = tmp_path / "atlas.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    fresh = runner.invoke(main, ["report", "-f", str(root), "--save", "--format", "json"])
    assert fresh.exit_code == 0, fresh.output
    report = json.loads(fresh.output)
    measurements = {node["subject"]: node["metrics"] for node in report["nodes"]}
    assert measurements["app.py"]["lineCount"] == 601
    assert measurements["app.py::wide"]["lineCount"] == 101
    assert measurements["app.py::wide"]["parameterCount"] == 4
    assert {finding["rule"] for finding in build_check(report, size_config())["findings"]} == {
        "maxFileLines", "maxFunctionLines", "maxParameters",
    }
    source.unlink()
    with repository_service(database) as service:
        assert service.report("source") == report
