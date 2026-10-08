<p align="center">
  <img src="assets/atlas.png" alt="Atlas, a friendly cartoon giant holding the world" width="200" height="200">
</p>

<h1 align="center">Atlas</h1>

<p align="center">
  <a href="https://github.com/LeonFelipeCordero/atlas/actions/workflows/ci.yml"><img src="https://github.com/LeonFelipeCordero/atlas/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-89718e.svg" alt="License: MIT"></a>
</p>

Atlas maps a local codebase and highlights complex functions, oversized files/functions, excessive parameters, and circular imports. Use its CLI for human- or AI-readable findings, or its web UI to explore dependencies and potential change impact.

Python parses files with Tree-sitter, resolves repository-local relationships, and builds a code graph. Analysis runs locally, on demand; graphs can be saved to SQLite, which the Bun/React UI reads directly. No cloud service, Python HTTP server, cloning, or background indexing.

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10+. Install from this checkout:

```sh
git clone https://github.com/LeonFelipeCordero/atlas.git
cd atlas
uv tool install ./atlas
atlas report -f /path/to/project --skip-save
```

If `atlas` is not on your `PATH`, run `uv tool update-shell` and restart your shell. Alternatively, run without installing the CLI:

```sh
uv run --project atlas atlas report -f /path/to/project --skip-save
```

## What it analyzes

| Feature | What you get |
| --- | --- |
| Code structure | Folders, files, types, functions, and methods in a navigable hierarchy. |
| Relationships | Imports, calls, callable references, inheritance, and containment; dependency views at module, file, type, and callable levels. |
| Complexity | Function/method decision points, short-circuit operators, deep-decision penalties, nested-loop penalties, and maximum decision depth. |
| Size and parameters | Physical line counts for files and functions/methods, plus declared input parameter counts for supported callable syntax. |
| Circular imports | Groups of files in runtime import cycles, with an example cycle and source evidence; type-only imports do not establish cycles. |
| Dependency metrics | Fan-in (direct dependents), fan-out (direct dependencies), and transitive change impact (all direct/indirect dependents), counting distinct internal peers. |
| Parse diagnostics | Parsing failures retained in the graph, alongside unresolved external targets and relationship confidence. |

Reports contain complexity, size, and circular-import findings. Complexity rules trigger independently when total cyclomatic complexity **> 8**, nested-loop count **> 0**, or decision depth **> 3**. Total complexity is `1 + decisions + short-circuit operators + deep-decision penalties + nested-loop penalties`.

Size rules trigger independently for files **> 600 lines**, functions/methods **> 100 lines**, or functions/methods with **> 7 input parameters**. Lines include comments and blanks; callable counts cover the full declaration. Parameters are declared inputs, not call-site arguments: defaults, destructuring patterns, and variadics each count as one; receivers and type parameters are excluded. Parameter counting supports Python, JavaScript, TypeScript/TSX, Go, Rust, Java, Kotlin, and Elixir. Unsupported syntax/languages leave counts unavailable, not zero. Other graph metrics have no report thresholds.

Atlas supports grammars recognized by its pinned Tree-sitter language pack, **except C and C++**. Python, JavaScript/JSX, TypeScript/TSX, Java, Kotlin, Go, Rust, and Elixir have specialized adapters; other supported grammars use generic extraction. Resolution is static and conservative, not compiler/type inference. Unresolved imports cannot establish cycles, and “No findings” does not prove the code is problem-free.

### Exclude files

Atlas honors `.gitignore`. Add `.atlasignore` for analysis-only exclusions:

```gitignore
*.generated.ts
/vendor/
/scratch/
```

Nested ignore files and Git-style patterns, including `!` exceptions, are supported. Exceptions cannot restore Git-ignored files or files inside an excluded parent. Without a root `.gitignore`, built-in dependency/build/generated-directory exclusions apply. Reanalyze to update saved results.

## Web UI

Requires [Bun](https://bun.sh/). From the checkout root, analyze and save a project, then start the dashboard:

```sh
uv run --project atlas atlas report -f /path/to/project
cd dashboard
bun install
bun run db:migrate
bun run dev
```

Open **http://localhost:3000**. Drill from folders into files and functions, navigate with breadcrumbs, search the contents list, and inspect incoming/outgoing connections, complexity, line/parameter counts, and dependency metrics. The graph supports pan/zoom and hides test files visually; metrics still use the full index, including tests and type-only dependencies.

Re-run the folder report or index command and refresh the UI after source changes. Reindex older graphs to populate size/parameter metrics; unavailable values are not zero, and this feature needs no schema migration. Index a folder directly, with no registration or project parameter required:

```sh
uv run --project atlas atlas index -f /path/to/project
```

Indexing updates the project at the same canonical folder location, including projects registered in the UI. Otherwise it creates a project named after the folder, adding a suffix if that name is already taken. `-f ./` indexes the current working directory. `--f` and `--folder` are aliases for `-f`.

UI registration requires a local folder, stores its canonical absolute path, and rejects URLs and duplicate canonical locations. For an older URL-based or relative-location registration, index its local checkout and open the new folder-based project. Legacy relative locations are not matched against the CLI’s working directory. If older registrations share a folder, indexing fails without changing either graph; use a distinct local checkout for each project.

Python owns the SQLite schema and migrations. The default database is `$XDG_DATA_HOME/atlas/atlas.sqlite`, falling back to `~/.local/share/atlas/atlas.sqlite`. Set an absolute `DATABASE_PATH` for both CLI and UI to share a different database; CLI commands also accept `--database PATH`. Indexing and folder reports migrate automatically when saving; run `atlas migrate` before starting the UI if no folder has been saved yet, and back up existing databases before upgrading.

The UI has **no authentication**; keep it on a trusted local network.

## CLI and AI-agent integration

Run against the whole target project, not just changed files:

```sh
atlas index -f .                               # Register/update and save; JSON graph summary
atlas report -f .                              # Fresh analysis; register/update and save
atlas report -f . --skip-save                  # Fresh analysis; no database access
atlas report -f . --skip-save --format json    # Structured findings for scripts
atlas projects                                # List registered projects as JSON
atlas report -p 'My project'                   # Read saved findings; no reanalysis
```

`index` requires a folder (`-f`) and does not accept a project selector or positional path. For `report`, choose exactly one source: a folder (`-f`) or a saved project name (`-p`). Markdown is the default, with file paths, callable line numbers, and explanations. JSON has the shape `{"findings": [...]}`; a clean report returns `{"findings": []}`.

For a shell script or CI gate, check the JSON explicitly: **findings do not cause a nonzero exit code**, but command errors do. This Bash example requires `jq`:

```sh
set -o pipefail
atlas report -f . --skip-save --format json | jq -e '.findings == []'
```

For an AI coding agent with shell access, add this instruction to its project rules (for example, `AGENTS.md`):

```text
After changes, run `atlas report -f . --skip-save` from the target repository root.
Review reported complexity, size/parameter limits, and circular imports; fix relevant findings and rerun.
Analyze the entire project. Do not treat “No findings” as a substitute for tests.
```

The agent uses the same CLI; no native agent plugin or MCP server is provided. Use `--format json` when the agent/tool needs structured output. Reports are findings-only, not a full graph export.

## Contribute

Keep changes focused, add regression tests for analyzer behavior, and open a pull request against `main`.

`atlas/src/atlas/` contains discovery, language adapters, extraction, graph analysis, CLI, services, and persistence. `dashboard/` contains the Bun/React UI and server routes. Python alone owns database migrations; Bun reads/registers repositories in the shared database.

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
uv run --project atlas atlas report -f . --skip-save
```

CI runs Python checks, dashboard checks, and a full-project Atlas report requiring zero findings. Production Python modules are limited to 600 lines, with architecture boundaries enforced by tests.

Coffee samples in `atlas/tests/fixtures/coffee/` intentionally contain complexity/size/parameter violations and import cycles; do not simplify them or remove their reference-note ledgers. Tests compare graphs and reports with checked-in snapshots. Regenerate both formats only after reviewing fixture/analyzer changes: `(cd atlas && uv run python -m tests.update_coffee_snapshots)`.

For schema changes, edit `atlas/src/atlas/persistence/models.py`, generate a revision with `(cd atlas && uv run alembic revision --autogenerate -m "describe change")`, review it, then run migrations. Report security issues as described in [SECURITY.md](SECURITY.md).
