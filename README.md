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
| Complexity | Separate cyclomatic and weighted complexity, nested-decision penalties, nested-loop counts, maximum decision depth, and per-file callable counts/weighted complexity sums. |
| Size and parameters | Physical line counts for files and functions/methods, plus declared input parameter counts for supported callable syntax. |
| Circular imports | Groups of files in runtime import cycles, with an example cycle and source evidence; type-only imports do not establish cycles. |
| Dependency metrics | Fan-in (direct dependents), fan-out (direct dependencies), transitive change impact (all direct/indirect dependents), and internal instability, counting distinct internal peers. |
| Parse diagnostics | Parsing failures retained in the graph, alongside unresolved external targets and relationship confidence. |

Reports contain quantitative measurements, including zeros and unavailable values, without applying thresholds or reading `atlas.json`. Cyclomatic complexity is `1 + decisions + short-circuit operators`; weighted complexity adds penalties for decisions deeper than two levels and loops nested inside another loop.

Lines include comments and blanks; callable line counts cover the full declaration. Parameters are declared inputs, not call-site arguments: defaults, destructuring patterns, and variadics each count as one; receivers and type parameters are excluded. Parameter counting supports Python, JavaScript, TypeScript/TSX, Go, Rust, Java, Kotlin, and Elixir. Unsupported syntax/languages leave counts unavailable, not zero (`N/A` in Markdown, `null` in JSON).

Dependency metrics include tests and type-only dependencies, exclude self/external dependencies, and count distinct peers at each item's level. Change impact excludes the item itself. Internal instability is `fan-out / (fan-in + fan-out)`; isolated items have no defined instability (`N/A`), not zero.

Atlas supports grammars recognized by its pinned Tree-sitter language pack, **except C and C++**. Python, JavaScript/JSX, TypeScript/TSX, Java, Kotlin, Go, Rust, and Elixir have specialized adapters; other supported grammars use generic extraction. Resolution is static and conservative, not compiler/type inference. Unresolved imports cannot establish cycles, and passing checks does not prove the code is problem-free.

### Project checks

`atlas check -f /path/to/project` analyzes current sources and reads `atlas.json` only from that folder's root. No config file is required: omitted keys inherit these defaults, and `null` disables an individual check.

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

For example, this `atlas.json` overrides four defaults:

```json
{
  "maxParameters": 5,
  "maxNestedLoops": null,
  "maxChangeImpact": 20,
  "maxInstability": 0.8
}
```

Equality passes; values above an enabled maximum fail. Unavailable metrics for enabled checks also fail, except undefined instability for isolated items. Parse errors fail checks even when all limits are disabled. Limits must be nonnegative numbers (integers except instability, which ranges from 0 to 1); invalid config or unknown keys are command errors.

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

Re-run `atlas index -f /path/to/project` (or `atlas report -f /path/to/project --save`) and refresh the UI after source changes. Saving matches an existing project by its canonical local folder location, preserving its registered name; otherwise it registers a project using the folder name with a suffix if needed. Manual registration in the UI is optional. `atlas index` always saves and prints the repository ID, schema version, and graph statistics as JSON.

Python owns the SQLite schema and migrations. The default database is `$XDG_DATA_HOME/atlas/atlas.sqlite`, falling back to `~/.local/share/atlas/atlas.sqlite`. Set the same absolute `DATABASE_PATH` for migrations, CLI, and UI to share a different database.

Migrations are explicit: CLI commands and the UI do not apply them automatically. After installation or upgrades, run `atlas-migrate` before using `--save`, indexing, listing projects, or starting the UI. From the checkout root, use `uv run --project atlas atlas-migrate`; from `dashboard/`, `bun run db:migrate` runs the same migration command. Back up existing databases before upgrading. The normalized-storage upgrade preserves project registrations but drops legacy graph blobs without backfilling; reindex those projects after migrating. Reports and checks without `--save` need no database or migrations.

The UI has **no authentication**; keep it on a trusted local network.

## CLI and AI-agent integration

Run against the whole target project, not just changed files:

```sh
atlas report -f .                  # Fresh quantitative metrics; no database access
atlas report -f . --format json     # Structured measurements for scripts
atlas check -f .                    # Fresh configured checks; no database access
atlas check -f . --format json      # Structured findings; exits 1 when checks fail
atlas-migrate                      # Apply migrations before database-backed commands
atlas index -f .                    # Register/update by folder location and save
atlas report -f . --save            # Measure and save the analyzed graph
atlas check -f . --save             # Check and save, even when checks fail
atlas projects                     # List registered projects as JSON
```

The analyzed folder defaults to `.`; `-f`, `--f`, and `--folder` are equivalent. `report`, `check`, and `index` always analyze current sources; saved-project selectors (`-p`/`--project`) and `--skip-save` are no longer supported. Saving is opt-in for both reports and checks.

Markdown is the default, with file paths and callable line numbers. Report JSON contains `summary`, `nodes` (each with `metrics`), `circularImports`, and `diagnostics`; it is a measurements report, not a full graph export. Check JSON has the shape `{"findings": [...]}`; a clean check returns `{"findings": []}` or “All checks passed.” in Markdown.

Reports do not fail because of measured values or parse diagnostics; command errors still return a nonzero exit code. **Checks exit 0 when all checks pass and 1 when findings exist.** For a shell script or CI gate, use `atlas check` directly. If piping its output, preserve the exit status:

```sh
set -o pipefail
atlas check -f . --format json | tee atlas-check.json
```

For an AI coding agent with shell access, add this instruction to its project rules (for example, `AGENTS.md`):

```text
After changes, run `atlas report -f .` and `atlas check -f .` from the target repository root.
Review measurements and configured-check findings; fix relevant findings and rerun.
Analyze the entire project. Do not treat passing checks as a substitute for tests.
```

The agent uses the same CLI; no native agent plugin or MCP server is provided. Use `--format json` when the agent/tool needs structured output.

## Contribute

Keep changes focused, add regression tests for analyzer behavior, and open a pull request against `main`.

`atlas/src/atlas/` separates parsing, metrics/configured checks, domain contracts, CLI, services, and persistence. `dashboard/` contains the Bun/React UI and server routes. Python alone owns database migrations; Bun reads normalized graph facts and registers repositories in the shared database.

From the repository root:

```sh
uv sync --project atlas --group dev
(cd dashboard && bun install)

(cd atlas && uv run pytest)
(cd atlas && uv run pyright)
(cd atlas && uv run ruff check .)
(cd dashboard && bun run build)
(cd dashboard && bun test)
(cd dashboard && bun run typecheck)
(cd dashboard && bun lint --fix)
uv run --project atlas atlas report -f .
uv run --project atlas atlas check -f .
```

CI runs Python checks only for `atlas/` changes and dashboard checks only for `dashboard/` changes. Either folder, `.atlasignore`, or `.gitignore` changes trigger a full-project `atlas check --f . --format json`, whose exit status enforces the configured limits. Each workflow also runs when its own file changes; docs-only changes skip CI. Production Python modules are limited to 600 lines, with architecture boundaries enforced by tests.

The dashboard uses TypeScript 7 for `tsc` via the `@typescript/native` alias, while ESLint uses the TypeScript 6 compatibility API via the `typescript` alias. This follows Microsoft's [side-by-side setup](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/#running-side-by-side-with-typescript-6.0) until typescript-eslint supports the new compiler API.

Coffee samples in `atlas/tests/fixtures/coffee/` intentionally contain complexity/size/parameter violations and import cycles; do not simplify them or remove their reference-note ledgers. Tests compare graphs and reports with checked-in snapshots. Regenerate both formats only after reviewing fixture/analyzer changes: `(cd atlas && uv run python -m tests.update_coffee_snapshots)`.

For schema changes, edit `atlas/src/atlas/persistence/models.py`, generate a revision with `(cd atlas && uv run alembic revision --autogenerate -m "describe change")`, review it, then apply it with `(cd atlas && uv run atlas-migrate)`. Report security issues as described in [SECURITY.md](SECURITY.md).
