"""Size measurements stay quantitative; only configured checks impose limits."""

from dataclasses import asdict
from datetime import date, timedelta
import json
from pathlib import Path
from shutil import copytree, rmtree

from click.testing import CliRunner

from atlas.bootstrap import migrate_database, repository_service
from atlas.cli import main
from atlas.indexer import analyze_repository
from atlas.metrics.check import build_check
from atlas.metrics.config import CheckConfig
from atlas.metrics.report import build_artifact_report
from tests.coffee_fixture import FIXTURE_ROOT

VARIANTS = Path(__file__).parent / "fixtures/variants/cli"


def size_config() -> CheckConfig:
    return CheckConfig(maxWeightedComplexity=None, maxDecisionDepth=None, maxNestedLoops=None,
                       maxCircularImportGroups=None)


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


def assert_receiver_findings(findings: list[dict], service: str, station: str) -> None:
    relevant = [finding for finding in findings if finding["subject"].startswith((service, station))]
    assert {finding["subject"] for finding in relevant} == {f"{service}.estimate", f"{service}.place"}
    assert all(finding["rule"] == "maxParameters" and finding["actual"] == 4 and finding["limit"] == 3
               for finding in relevant)


def test_receivers_decorator_comments_and_attributes_at_parameter_threshold(tmp_path: Path) -> None:
    copytree(FIXTURE_ROOT / "python", tmp_path / "python")
    copytree(FIXTURE_ROOT / "rust", tmp_path / "rust")
    copytree(VARIANTS / "receiver-threshold", tmp_path, dirs_exist_ok=True)
    report = build_artifact_report(asdict(analyze_repository(tmp_path)))
    metrics = {node["subject"]: node["metrics"] for node in report["nodes"] if node["level"] == "callable"}
    service = "python/src/coffee/orders/service.py::OrderService"
    station = "rust/brewing/station.rs::BrewingStation"
    assert metrics[f"{service}.preview"]["parameterCount"] == 3
    assert metrics[f"{service}.stocked"]["parameterCount"] == 3
    assert metrics[f"{station}.ready"]["parameterCount"] == 3
    assert metrics[f"{station}.prepare"]["parameterCount"] == 3
    assert_receiver_findings(build_check(report, size_config())["findings"], service, station)


def daily_export_source() -> str:
    """Expand a real export layout just beyond the file and callable boundaries."""
    template = (VARIANTS / "daily-order-export/order_export.py").read_text()
    rows = [f'        f"{{day}};{{station}};{{orders.get(\'espresso-{index:03d}\', 0)}};{{currency}}",'
            for index in range(98)]
    source = template.replace("        # DAILY_ORDER_ROWS", "\n".join(rows))
    rate_count = 602 - len(source.splitlines())
    rates = [f'    ("{date(2025, 1, 1) + timedelta(days=index)}", "EUR", 1.0),'
             for index in range(rate_count)]
    return source.replace("    # EXCHANGE_RATE_ROWS", "\n".join(rates))


def test_cli_fresh_and_saved_measurements_match_without_sources(tmp_path: Path) -> None:
    root = copytree(FIXTURE_ROOT / "python", tmp_path / "source")
    source = root / "src/coffee/reporting/order_export.py"
    source.write_text(daily_export_source())
    database = tmp_path / "atlas.sqlite"
    migrate_database(database)
    runner = CliRunner(env={"DATABASE_PATH": str(database)})
    fresh = runner.invoke(main, ["report", "-f", str(root), "--save", "--format", "json"])
    assert fresh.exit_code == 0, fresh.output
    report = json.loads(fresh.output)
    measurements = {node["subject"]: node["metrics"] for node in report["nodes"]}
    path = "src/coffee/reporting/order_export.py"
    assert measurements[path]["lineCount"] == 601
    assert measurements[f"{path}::export_daily_orders"]["lineCount"] == 101
    assert measurements[f"{path}::export_daily_orders"]["parameterCount"] == 4
    findings = build_check(report, size_config())["findings"]
    assert {finding["rule"] for finding in findings if finding["subject"].startswith(path)} == {
        "maxFileLines", "maxFunctionLines", "maxParameters",
    }
    rmtree(root / "src")
    with repository_service(database) as service:
        assert service.report("source") == report
