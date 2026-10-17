# Native parity and benchmarks

Python is the reference. No test updates snapshots. Rust tests invoke Rust APIs and the native executable, never Python. `tests/code_samples` and `tests/snapshots` are symlinks to `atlas/tests/`; do not replace them with copies.

```text
Python fixtures/snapshots ──> cargo test ──> native artifact/report/check/mutations
Read-only project ──> isolated SQLite clones ──> Python CLI ↔ native CLI
                                      └──────> schema + every row + read-only checks
```

## Native snapshots

Run from the repository root:

```sh
cargo test --manifest-path atlas-rust/Cargo.toml --test parity --test parity_families --test parity_pipeline --test parity_navigation --test parity_inventory
cargo test --manifest-path atlas-rust/Cargo.toml --test parity_pipeline typescript::same_source_grammar_variants -- --exact
cargo test --manifest-path atlas-rust/Cargo.toml --test parity_families typescript_script_members -- --exact
cargo test --manifest-path atlas-rust/Cargo.toml --test parity python::artifact -- --exact
cargo test --manifest-path atlas-rust/Cargo.toml --test parity python::report -- --exact
cargo test --manifest-path atlas-rust/Cargo.toml --test parity rust::mutation_operators -- --exact
```

The five native parity targets contain 159 tests and cover all 73 unchanged Python golden files. `parity` has 56 artifact/report/check/CLI/mutation tests. `parity_families` adds 11 safety-review, script-member, and JVM callable-selection tests. `parity_pipeline` adds 81 extraction/analysis/staged-graph tests across all nine languages. `parity_navigation` adds eight complete navigation goldens plus two normalization guards. `parity_inventory` rejects new or missing golden files until native coverage is extended.

Each coffee language checks the complete artifact, report JSON/Markdown, check JSON/Markdown, and the complete four-command CLI bundle, including exact exit codes/stderr. Artifacts include all candidates, spans, hashes, edges, views, diagnostics, and circular dependencies. Report/check API tests also use the canonical graph/report as input to isolate failures from parsing.

Pipeline tests reproduce `coffee_pipeline.py`, `project_snapshot_support.py`, and `source_snapshot_fixture.py`: every parsed file, source byte, content hash, optional declaration field, call, import, inheritance, enriched symbol, resolved connection, and external node. They compare native/tag-only/merged structures, all native structure fields, excluded-language bytes and C syntax, and every explicit or JSX shared-grammar variant. Serialization uses the original lowercase byte hex and exact Python `StructureKind` representation; it retains null/empty fields that native serde otherwise omits. No numeric rounding, array sorting, field dropping, or new goldens are used.

Navigation goldens execute all 189 canonical requests against graphs analyzed from physical samples and stored in isolated native SQLite databases. Existing golden `filters` supply requests only; no golden graph/response populates storage. Responses receive the original `normalize_responses` metadata placeholders and root normalization only after checking every response against the saved graph's identical, nonempty repository ID, revision, and timestamp. Node keys, graph fields, provenance, ordering, diagnostics, and source lines remain exact. The developer CLI comparison below remains stricter about live UUID equality.

Artifact normalization matches `coffee_snapshot`: remove `repository.indexedAt`; replace only the repository path and root node absolute path. Arrays, fields, IDs, hashes, evidence, confidence, numbers, and nulls stay unchanged. Native CLI subprocesses fail after 60 seconds. Set `ATLAS_PARITY_TIMEOUT_SECS` to change that bound; timeout is never a passing result.

## CLI parity and timing

```sh
uv sync --project atlas --group dev
cargo build --manifest-path atlas-rust/Cargo.toml --release --bins
uv run --project atlas python atlas-rust/scripts/parity.py --help
uv run --project atlas python atlas-rust/scripts/parity.py --sample python --variants --list-actions
uv run --project atlas python atlas-rust/scripts/parity.py --sample python --variants --warmups 0 --repetitions 1
uv run --project atlas python atlas-rust/scripts/parity.py --sample python --actions 'report.json.fresh' --max-cases 1 --warmups 0 --repetitions 1
uv run --project atlas python atlas-rust/scripts/parity.py --sample rust --actions 'navigation.*' --warmups 0 --repetitions 1
uv run --project atlas python atlas-rust/scripts/parity.py --sample python --actions 'mutations.variant.*' --variants --warmups 0 --repetitions 1
```

Repeat `--sample`, `--project`, or `--actions` to combine selections. Use `--rust-bin` and `--rust-migrate` for debug builds. Filters are case-name globs, not command prefixes. `--max-cases` bounds all selected cases per project, including interop and variants; setup and reference scenario selection are not timed cases.

Benchmark real projects without changing their sources or their databases:

```sh
uv run --project atlas python atlas-rust/scripts/parity.py \
  --projects-dir ~/workspace/projects --max-projects 2 \
  --actions 'report.*' --warmups 1 --repetitions 3 --timeout 90 \
  --inventory /tmp/atlas-project-inventory.json

uv run --project atlas python atlas-rust/scripts/parity.py \
  --project ~/workspace/projects/VU --actions 'report.json.fresh' \
  --warmups 0 --repetitions 1 --timeout 15

# All projects and CLI cases. No case/action filters; allow a substantial run budget.
uv run --project atlas python atlas-rust/scripts/parity.py \
  --projects-dir ~/workspace/projects --warmups 1 --repetitions 3 --timeout 90
```

Every process gets a temporary `DATABASE_PATH` and `XDG_DATA_HOME`. No command applies mutations. Configuration/stale-source variants copy only reference samples into temporary directories. The harness disables Python bytecode writes. Keep `--output` outside source projects; existing run directories are rejected.

Each CLI subprocess has its own timeout. Both implementations timing out still fails parity. A failed reference baseline index is recorded, graph-dependent cases are marked blocked failures, and independent actions continue. Later projects still run. When native indexing succeeds, native-origin graph reading can still run after reference indexing failed. The VU receiver-alias expansion timeout is a reference limitation, not an accepted native parity result.

### Coverage

The generic matrix has 230 cases per project: 40 analysis/storage/migration cases, 110 navigation/source cases, and 80 help/invalid-input cases. It includes all folder aliases, attached short-option values, cwd defaults, group option terminators, and literal or value-position `--help` arguments; JSON/Markdown/default formats; save variants; rule catalog; fresh/saved mutations; fresh/repeated migrations; projects; project name/ID/cwd selection; valid/stale revisions; find and child paging; context/path in all directions and relationship types; depth/node/edge limits; source JSON/text, batches, duplicates, start-line and max-line limits; decimal whitespace/underscores and Arabic-Indic/fullwidth/mathematical digits; exact 100-digit source start lines in JSON/text; malformed decimal forms and overflow bounds; help and invalid argument bounds.

Both readers run against the same Python-produced database and the same native-produced database. Native-origin reader cases use the `interop.native.` prefix. Eight coffee languages also replay the unchanged `CoffeeNavigation` assertions and query scenarios from `atlas/tests/coffee_navigation.py`: real declaration selection, core calls, callbacks, recursion, imports/cycles, inheritance, unresolved targets, verified source, and shortest paths. TSX has no canonical navigation scenario; its full generic matrix still runs. Aggregate UUID-masking helpers from the reference scenario are not used.

`--variants` adds 34 sample cases: all rules enabled for coffee and operator fixtures; disabled/duplicate rules; changed/deleted/symlink sources; eight malformed configurations; disabled checks; and dependency thresholds. These variants never change a real project configuration.

### Strict database comparison

The harness compares every table and row, Alembic revision data, columns, keys, indexes/collations, foreign keys, DDL, WAL mode, integrity checks, and foreign-key checks. DDL text differences and foreign-key declaration-order differences currently fail too; inspect the reported schema paths when migrations are semantically similar but spelled differently. JSON payloads compare as JSON, preserving array order. SQL row order is represented by all stored columns, including graph ordinals.

Repository registration uses one shared seeded UUID in isolated clones. For a successful native write, the harness verifies a fresh canonical UUID4 graph revision and supplies that same entropy to the Python oracle's UUID function. It does not rewrite either output or database. Repository IDs and graph revisions compare exactly. Only known root-location fields and non-null timestamps normalize during result/data comparison. Timestamp type differences still fail. Evidence and source lines never normalize. The developer-only Python wrapper is not part of the native runtime.

### Output and interpretation

The default output directory is a new `/tmp/atlas-parity-results-*` directory. `metadata.json` records commands/options, runtime/package versions, platform/CPU/load, source checkout state, executable/lock hashes, and environment inputs. `measurements.jsonl` records every warmup/measured command, stdout, stderr, exit code, timeout, duration, and complete parity diffs. `report.json` contains language/file coverage, blocked/setup failures, diffs, and median/min/max timings. Warmups also enforce parity.

Timings include process startup, CLI work, and the small Python developer wrapper. They exclude database cloning, schema inspection, and prerequisite setup. Native runs first in each pair; use multiple runs on a quiet machine for performance conclusions. This measures CLI wall time, not peak memory or parser-only CPU time. Filtered/bounded runs do not prove unselected coverage. No external project benchmark has been accepted merely because both commands failed.

## Harness and repository validation

```sh
uv run --project atlas python -m unittest discover -s atlas-rust/scripts -p 'test_*.py' -v
uv run --project atlas ruff check atlas-rust/scripts
uv run --project atlas pyright atlas-rust/scripts
uv run --project atlas atlas check --f . --format json
(cd atlas && uv run pytest -n 4)
(cd atlas && uv run pyright)
(cd atlas && uv run ruff check .)
```

Harness self-tests check type/null/array-order sensitivity, timestamp/root-only normalization, schema/data changes, UUID validation, controlled-entropy full-row round trips, output corruption, bounded timeouts, equal-timeout rejection, and continuation after a reference setup timeout. CI runs formatting, Clippy, native tests, every CLI case and sample variant across all nine languages, the harness tests, and the whole-repository Python Atlas check. Python dependencies follow the existing unlocked `uv sync --group dev` convention; Rust uses its tracked Cargo lockfile.

All current golden families are covered, including the full internal extraction and analysis seams. Raw processing metrics that have no original golden are not invented as new expectations. Permission/race/symlink security permutations from the Python test suite are not all reproduced by the CLI matrix. The harness adds no expected failures, snapshot regeneration, or approximation mode.
