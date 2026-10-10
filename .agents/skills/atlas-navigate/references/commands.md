# Atlas navigation commands

All graph commands return JSON on stdout; errors go to stderr with a nonzero exit code. Run `atlas graph --help` and subcommand `--help` when unsure. Do not pass `--format json`: graph output is already JSON.

Before project discovery, check database existence without opening or creating it. Use the Atlas environment's Python if `python3` is unavailable:

```sh
python3 -c 'import os; from pathlib import Path; p=Path(os.environ["DATABASE_PATH"]).expanduser() if os.environ.get("DATABASE_PATH") else Path(os.environ.get("XDG_DATA_HOME") or Path.home()/".local/share").expanduser()/"atlas/atlas.sqlite"; print(p); raise SystemExit(0 if p.is_file() else 1)'
```

If this exits nonzero, do not run `atlas projects`: it can create an empty database. Explain the prerequisite or fall back to local file navigation. With an existing database:

```sh
atlas projects
atlas graph --project "$PROJECT" overview
atlas graph --project "$PROJECT" find 'save_folder' --limit 5
```

Select an exact key from `find`, not merely the first match. Capture its graph revision and use it to keep later queries consistent:

```sh
atlas graph --project "$PROJECT" --revision "$REVISION" show "$KEY"
atlas graph --project "$PROJECT" --revision "$REVISION" children "$KEY" --limit 30
atlas graph --project "$PROJECT" --revision "$REVISION" context "$KEY" \
  --direction out --relations CALLS,REFERENCES --depth 2 --max-nodes 30 --max-edges 100
atlas graph --project "$PROJECT" --revision "$REVISION" context "$KEY" \
  --direction in --relations CALLS,REFERENCES --depth 1
atlas graph --project "$PROJECT" --revision "$REVISION" source "$KEY" --max-lines 80
atlas graph --project "$PROJECT" --revision "$REVISION" path "$FROM" "$TO"
```

`--project` is optional inside an indexed folder, including any subdirectory: `atlas graph overview` and `atlas graph find 'save_folder'` infer the nearest containing registered folder. From elsewhere, or when that folder has multiple registrations, `--project` accepts an explicit registered name or ID. No match returns an actionable error; navigation never indexes automatically. `--revision` is optional on the first query, then recommended. Group options precede the subcommand. Keep `DATABASE_PATH` unchanged between indexing and querying; otherwise Atlas uses its user-data database.

| Command | Purpose |
|---|---|
| `overview` | Index identity, coverage, counts, and initial project orientation |
| `find QUERY` | Bounded name, qualified-name, or path search; not semantic search |
| `show KEY` | Declaration details and containment ancestors |
| `children KEY` | Bounded immediate children, not all descendants |
| `context KEY` | Bounded dependency neighborhood with relationship evidence |
| `source KEY` | Hash-checked local source for a declaration or file |
| `path FROM TO` | Bounded directed relationship path, not an execution trace |

Context directions are `out`, `in`, and `both`. The default relations are `CALLS,REFERENCES`. Select `IMPORTS` for file/module dependencies and `INHERITS` for type relationships. Preserve type-only and unresolved-target distinctions. Use `children` for structural exploration rather than adding containment to a behavioral trace.

Every success includes `repositoryId`, `graphRevision`, `indexedAt`, effective `filters`, path-scoped `diagnostics`, and `diagnosticsTruncated`. Inspect these and `truncated` every time. `show.ancestors` is nearest-parent first. `context.boundaries` gives `stableKey`, `reason`, and `expandable`; expand only relevant keys. A `path.status` of `unknown` means limits prevented ruling out a connection; `not_found` is still only about the selected static relations.

Page `children` with its returned `nextOffset` using `--offset`. Page `source` with `source.nextStartLine` using `--start-line` (absolute 1-based line within the symbol/file bounds). Only `source.status: ok` returns verified `lines`, `startLine`, `endLine`, `truncated`, and `nextStartLine`. Other statuses include `changed`, `missing`, `unsafe`, `unreadable`, `unverified`, `unavailable`, `unsupported_encoding`, `span_unavailable`, and `too_large`; use the fallback rules in the skill. Source reads are capped at 8 MiB per file and 16 KiB of excerpt text; `too_large` returns these byte limits without source lines. For an oversized excerpt, retry fewer lines or read the relevant current source with bounded ordinary tools. Never treat truncated evidence as a complete function body.

Defaults: `find --limit 10`; `children --limit 30 --offset 0`; `context --depth 2 --max-nodes 30 --max-edges 100`; `source --max-lines 80`; `path --max-depth 6 --max-nodes 30 --max-edges 100`. Path also accepts `--direction` and `--relations`. Navigation errors are JSON on stderr with exit 1; invalid CLI usage exits 2.

The graph database is queried without implicit migration or reindexing. For authorized setup in an Atlas checkout:

```sh
uv run --project /absolute/path/to/atlas/atlas python -m atlas.persistence.database migrate
uv run --project /absolute/path/to/atlas/atlas atlas index --folder /absolute/project/path
```

Use the same `DATABASE_PATH` for these commands and queries. Initialization and indexing write data; do not run them merely because a read query failed.
