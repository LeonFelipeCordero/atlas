"""Snapshot serialization preserves byte boundaries and record ordering."""

from dataclasses import dataclass
from pathlib import Path

from tests.coffee_fixture import coffee_sources
from tests.source_snapshot_fixture import snapshot_value


@dataclass
class Record:
    path: Path
    source: bytes
    calls: list[str]


def test_bytes_paths_and_native_record_order_are_lossless():
    source = coffee_sources("python")[0].source.replace(b"\n", b"\r\n")
    value = snapshot_value(Record(Path("brewing/brewer.py"), source, ["brew", "retry", "brew"]))
    assert value["path"] == "brewing/brewer.py"
    assert bytes.fromhex(value["source"]["hex"]) == source
    assert value["calls"] == ["brew", "retry", "brew"]


def test_only_unordered_collections_are_sorted():
    assert snapshot_value({"targets": {"recipe", "brew"}}) == {"targets": ["brew", "recipe"]}
    assert snapshot_value(("recipe", "brew", "recipe")) == ["recipe", "brew", "recipe"]
