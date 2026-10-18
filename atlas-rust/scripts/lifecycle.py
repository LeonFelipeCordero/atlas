"""Isolated first-write, replacement, and actual Alembic revision fixtures."""
from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from cases import Case
from common import require
from database import connect, quote

REVISIONS = ("0001_initial", "0002_graph_nodes", "0003_graph_relations", "0004_drop_graph_artifact", "0005_mutation_candidates")


def cases() -> list[Case]:
    return [Case("index.first", ("index",), True),
            *(Case(f"index.replace.{change}", ("index",), True) for change in ("changed", "deleted")),
            *(Case("migrate.from." + revision, (), True, True) for revision in REVISIONS)]


def prepare(pair) -> None:
    from project import Project
    name = pair.case.name
    if name not in {case.name for case in cases()}:
        return
    project = Project(pair.project.run, pair.project.root, pair.folder)
    if name == "index.first":
        require(project.oracle(["migrate"]), "empty migrated database")
    elif name.startswith("migrate.from."):
        require(project.oracle(["historical", name.removeprefix("migrate.from."), str(pair.project.baseline)]), "historical database")
    else:
        replacement(project, name)
    pair.project = project


def replacement(project, name: str) -> None:
    original = project.root
    project.root = project.folder / "source" / original.name
    shutil.copytree(original, project.root, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    # A known file guarantees removed nodes/edges even for an empty input project.
    fixture = project.root / "parity_lifecycle_fixture.py"
    if fixture.exists() or fixture.is_symlink():
        raise ValueError("Lifecycle fixture name already exists")
    fixture.write_text("def obsolete():\n    return 1\n\ndef caller():\n    return obsolete()\n")
    project.prepare()
    verify_replacement_baseline(project)
    if name.endswith("deleted"):
        fixture.unlink()
    else:
        fixture.write_text("def replacement(value):\n    return value + 2\n")


def verify_replacement_baseline(project) -> None:
    if not project.ready():
        raise ValueError("Replacement baseline indexing failed")
    with connect(project.baseline) as database:
        row = database.execute("SELECT 1 FROM graph_nodes WHERE path=? AND name='obsolete'", ("parity_lifecycle_fixture.py",)).fetchone()
    if row is None:
        raise ValueError("Project configuration excluded the replacement fixture")


def historical(path: Path, revision: str, baseline: Path) -> None:
    """Run Python's real upgrade chain to a revision, then populate its real columns."""
    from alembic import command
    from alembic.config import Config
    from atlas.persistence import database
    with closing(sqlite3.connect(path)) as sqlite:
        sqlite.execute("PRAGMA journal_mode=WAL")
    engine = database.create_engine(path)
    try:
        with engine.connect() as connection, connection.begin():
            config = Config()
            config.set_main_option("script_location", str(Path(database.__file__).parent / "migrations"))
            config.attributes["connection"] = connection
            command.upgrade(config, revision)
        populate(path, baseline)
    finally:
        engine.dispose()


def populate(path: Path, baseline: Path) -> None:
    with connect(baseline) as source, closing(sqlite3.connect(path)) as target, target:
        tables = [row[0] for row in target.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'alembic_version'")]
        for table in tables:
            copy_table(source, target, table)
        # Include a populated legacy graph without normalized metadata at every revision.
        legacy_name = target.execute("SELECT name FROM repositories LIMIT 1").fetchone()[0] + ":legacy"
        target.execute("INSERT INTO repositories VALUES ('legacy', ?, '/legacy', 1000)", (legacy_name,))
        columns = [row[1] for row in target.execute("PRAGMA table_info(repository_graphs)")]
        if "artifact" in columns:
            target.execute("INSERT INTO repository_graphs(repository_id, imported_at, artifact) VALUES ('legacy', 2000, '{\"nodes\":[]}')")
        else:
            target.execute("INSERT INTO repository_graphs(repository_id, imported_at) VALUES ('legacy', 2000)")
        if target.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Invalid historical fixture foreign keys")


def copy_table(source: sqlite3.Connection, target: sqlite3.Connection, table: str) -> None:
    all_columns = [row[1] for row in target.execute(f"PRAGMA table_info({quote(table)})")]
    columns = [column for column in all_columns if column != "artifact"]
    names = ','.join(map(quote, columns))
    records = source.execute(f"SELECT {names} FROM {quote(table)}").fetchall()
    if "artifact" in all_columns:
        columns.append("artifact")
        records = [(*record, '{"legacy":"must be discarded, not backfilled"}') for record in records]
    target.executemany(f"INSERT INTO {quote(table)} ({','.join(map(quote, columns))}) VALUES ({','.join('?' for _ in columns)})", records)
