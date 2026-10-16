<p align="center">
  <img src="assets/atlas.png" alt="Atlas, a friendly cartoon giant holding the world" width="200" height="200">
</p>

<h1 align="center">Atlas</h1>

<p align="center">
  <a href="https://github.com/LeonFelipeCordero/atlas/actions/workflows/ci.yml"><img src="https://github.com/LeonFelipeCordero/atlas/actions/workflows/ci.yml/badge.svg?branch=main" alt="CLI CI status"></a>
  <a href="https://github.com/LeonFelipeCordero/atlas/actions/workflows/dashboard-ci.yml"><img src="https://github.com/LeonFelipeCordero/atlas/actions/workflows/dashboard-ci.yml/badge.svg?branch=main" alt="Dashboard CI status"></a>
  <a href="https://github.com/LeonFelipeCordero/atlas/actions/workflows/atlas-ci.yml"><img src="https://github.com/LeonFelipeCordero/atlas/actions/workflows/atlas-ci.yml/badge.svg?branch=main" alt="Atlas CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-89718e.svg" alt="License: MIT"></a>
</p>

Atlas maps a local codebase and measures complexity, size, parameters, circular imports, and dependency impact. Use `atlas report` for human- or AI-readable measurements, `atlas check` to enforce configurable limits, or its web UI to explore dependencies.

Python parses files with Tree-sitter, resolves repository-local relationships, and builds a code graph. Analysis runs locally, on demand, without database access by default. Saved graphs use normalized SQLite tables rather than whole-graph JSON blobs; the Bun/React UI reads those facts directly. No cloud service, Python HTTP server, cloning, or background indexing.

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10+. Install from this checkout:

```sh
git clone https://github.com/LeonFelipeCordero/atlas.git
cd atlas
uv tool install ./atlas
atlas report -f /path/to/project
```

If `atlas` is not on your `PATH`, run `uv tool update-shell` and restart your shell. Alternatively, run without installing the CLI:

```sh
uv run --project atlas atlas report -f /path/to/project
```

## What it analyzes

| Feature | What you get |
| --- | --- |
| Code structure | Folders, files, types, functions, and methods in a navigable hierarchy. |
| Relationships | Imports, calls, callable references, inheritance, and containment; dependency views at module, file, type, and callable levels. |
| Complexity | Cyclomatic/weighted complexity, decision depth, nested loops, and per-file totals. |
| Size and parameters | Physical line counts for files and functions/methods, plus declared input parameter counts for supported callable syntax. |
| Circular imports | Groups of files in runtime import cycles, with an example cycle and source evidence; type-only imports do not establish cycles. |
| Dependency metrics | Fan-in (direct dependents), fan-out (direct dependencies), transitive change impact (all direct/indirect dependents), and internal instability, counting distinct internal peers. |
| Parse diagnostics | Parsing failures retained in the graph, alongside unresolved external targets and relationship confidence. |

Reports show measurements, not pass/fail judgments. Unavailable values are `N/A` (or `null` in JSON), not zero. Lines include comments and blanks; parameters count declared inputs. Dependency metrics include tests and type-only dependencies.

Atlas supports grammars recognized by its pinned Tree-sitter language pack, **except C, C++, C#, PHP (including PHPDoc), and Ruby (including RBS)**. Python, JavaScript/JSX, TypeScript/TSX, Java, Kotlin, Go, Rust, and Elixir have specialized adapters; other supported grammars use generic extraction. Resolution is static and conservative, not compiler/type inference. Unresolved imports cannot establish cycles, and passing checks does not prove the code is problem-free.

### Project checks

`atlas check` enforces the defaults below. Override them in the analyzed folder's root `atlas.json`, for example `{"maxParameters": 5}`. Omitted keys keep their defaults; `null` disables a check.

| Config key | Default maximum | Applies to |
| --- | --- | --- |
| `maxFileLines` | 600 | Files |
| `maxFunctionLines` | 100 | Functions/methods |
| `maxParameters` | 3 | Functions/methods |
| `maxWeightedComplexity` | 8 | Functions/methods |
| `maxDecisionDepth` | 3 | Functions/methods |
| `maxNestedLoops` | 0 | Functions/methods |
| `maxCircularImportGroups` | 0 | Whole project |
| `maxChangeImpact` | `null` (disabled) | Files/modules |
| `maxInstability` | `null` (disabled) | Files/modules |

Checks fail when limits are exceeded or analysis is incomplete.

### Mutation manifests

`atlas mutations` generates JSON manifests for independent single-operator edits; it does not modify source or execute mutations. Opt in with rule IDs in the analyzed folder's root `atlas.json`:

```json
{
  "mutations": {
    "rules": ["arithmetic.add-to-subtract", "comparison.equal-to-not-equal"]
  }
}
```

Omitting `mutations.rules` or using `[]` disables generation. Duplicate IDs are harmless; each selected ID enables all its applicable language mappings. The old rule-to-replacement dictionary is rejected.

```sh
atlas mutations --rules          # List versioned rules and language/token mappings
atlas mutations -f .             # Analyze current sources without saving
atlas index -f .                 # Save current candidates (requires migrations)
atlas mutations -f . --saved     # Use saved candidates; verify current source
```

Saved mode never refreshes the index: missing or stale source fails the whole request; reindex after source changes. Each manifest is an alternative against the original file, not a patch to apply sequentially. See [the full catalog and manifest contract](atlas/MUTATIONS.md).

### Exclude files

Atlas honors `.gitignore`. Add `.atlasignore` for analysis-only exclusions:

```gitignore
*.generated.ts
/vendor/
/scratch/
```

Nested ignore files and Git-style patterns, including `!` exceptions, are supported. Exceptions cannot restore Git-ignored files or files inside an excluded parent. Without a root `.gitignore`, built-in dependency/build/generated-directory exclusions apply. Reanalyze to update saved results.

## Web UI

Requires [Bun](https://bun.sh/). From the checkout root, apply migrations before analyzing and saving a project, then start the dashboard:

```sh
uv run --project atlas atlas-migrate
uv run --project atlas atlas index -f /path/to/project
cd dashboard
bun install
bun run dev
```

Open **http://localhost:3000**. Drill from folders into files and functions, navigate with breadcrumbs, search the contents list, and inspect incoming/outgoing connections, complexity, line/parameter counts, and dependency metrics. The graph supports pan/zoom and hides test files visually; metrics still use the full index, including tests and type-only dependencies.

Re-run `atlas index -f /path/to/project` and refresh the UI after source changes. Projects are automatically registered or updated by their local folder location.

Python owns the SQLite schema and migrations. The default database is `$XDG_DATA_HOME/atlas/atlas.sqlite`, falling back to `~/.local/share/atlas/atlas.sqlite`. Set the same absolute `DATABASE_PATH` for migrations, CLI, and UI to share a different database.

Migrations are explicit: CLI commands and the UI do not apply them automatically. After installation or upgrades, run `atlas-migrate` before using `--save`, indexing, listing projects, or starting the UI. From the checkout root, use `uv run --project atlas atlas-migrate`; from `dashboard/`, `bun run db:migrate` runs the same migration command. Back up existing databases before upgrading. The normalized-storage upgrade preserves project registrations but drops legacy graph blobs without backfilling; reindex those projects after migrating. Reports and checks without `--save` need no database or migrations.

The UI has **no authentication**; keep it on a trusted local network.

## CLI and AI-agent integration

Run against the whole target project, not just changed files:

```sh
atlas report -f .   # Show measurements
atlas check -f .    # Enforce limits; use in CI
atlas-migrate      # Migrate before database-backed commands
atlas index -f .    # Register/update and save the graph
atlas projects     # List registered projects as JSON
```

Reports and checks analyze current sources without saving. Both default to Markdown; add `--format json` for structured output or `--save` to store the graph. The folder defaults to `.`.

`atlas check` exits 0 when checks pass and 1 when findings exist. `atlas report` does not enforce limits.

For an AI coding agent with shell access, add this instruction to its project rules (for example, `AGENTS.md`):

```text
After changes, run `atlas report -f .` and `atlas check -f .` from the target repository root.
Review measurements and configured-check findings; fix relevant findings and rerun.
Analyze the entire project. Do not treat passing checks as a substitute for tests.
```

Agents use the same CLI; no native agent plugin or MCP server is provided.

## Contribute

Keep changes focused, add regression tests for analyzer behavior, and open a pull request against `main`.

`atlas/src/atlas/` separates parsing, metrics/configured checks, domain contracts, CLI, services, and persistence. `dashboard/` contains the Bun/React UI and server routes. Python alone owns database migrations; Bun reads normalized graph facts and registers repositories in the shared database.

From the repository root:

```sh
uv sync --project atlas --group dev
(cd dashboard && bun install)

(cd atlas && uv run pytest -n auto)
(cd atlas && uv run pyright)
(cd atlas && uv run ruff check .)
(cd dashboard && bun run build)
(cd dashboard && bun test)
(cd dashboard && bun run typecheck)
(cd dashboard && bun lint --fix)
uv run --project atlas atlas report -f .
uv run --project atlas atlas check -f .
```

Python tests use `pytest-xdist` to run in parallel. `-n auto` selects the worker count from the available CPU cores; use `-n 4` for four workers or omit `-n` for a serial run. Tests must isolate files, databases, and ports. Session-scoped fixtures run once per worker.

CI runs Python checks only for `atlas/` changes and dashboard checks only for `dashboard/` changes. Either folder, `.atlasignore`, or `.gitignore` changes trigger a full-project `atlas check --f . --format json`, whose exit status enforces the configured limits. Each workflow also runs when its own file changes; docs-only changes skip CI. Production Python modules are limited to 600 lines, with architecture boundaries enforced by tests.

The dashboard uses TypeScript 7 for `tsc` via the `@typescript/native` alias, while ESLint uses the TypeScript 6 compatibility API via the `typescript` alias. This follows Microsoft's [side-by-side setup](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/#running-side-by-side-with-typescript-6.0) until typescript-eslint supports the new compiler API.

Coffee samples in `atlas/tests/fixtures/coffee/` intentionally contain complexity/size/parameter violations and import cycles; do not simplify them or remove their reference-note ledgers. Tests compare graphs and reports with checked-in snapshots. Regenerate both formats only after reviewing fixture/analyzer changes: `(cd atlas && uv run python -m tests.update_coffee_snapshots)`.

For schema changes, edit `atlas/src/atlas/persistence/models.py`, generate a revision with `(cd atlas && uv run alembic revision --autogenerate -m "describe change")`, review it, then apply it with `(cd atlas && uv run atlas-migrate)`. Report security issues as described in [SECURITY.md](SECURITY.md).
