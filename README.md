# Atlas

A local-first explorer for Tree-sitter repository graphs. Python analyzes repositories and exclusively owns the SQLite schema, migrations, and indexing. The Bun/React app reads and registers repositories directly in that same SQLite file. No Python HTTP server, authentication, cloning, or background indexing.

## CI

Pull requests targeting `main` and pushes to `main` run three independent jobs: Python (pytest, Pyright, Ruff), Dashboard (tests, typecheck, lint, production build), and Atlas (fresh full-repository analysis). Atlas fails unless its JSON report contains zero findings; it uses `--skip-save` to avoid database writes. Dependency installation resolves from manifests because this code-only repository excludes lockfiles. Newer runs cancel older runs on the same ref.

## Run locally

From the project root:

```sh
uv sync --project atlas --group dev
cd dashboard
bun install
bun run db:migrate
bun run dev              # UI server at http://localhost:3000
```

Analyze any local folder and get a findings-only report; the CLI migrates the database and registers or updates the repository automatically:

```sh
uv run --project atlas atlas report --f /path/to/repository
# Installed CLI:
atlas report -f ./
atlas report -f ./ --skip-save   # Analyze only; no database access
atlas report --p PROJECT_NAME   # Read saved results without reanalyzing
```

Folder reports match existing repositories by resolved location. New projects use the folder name; duplicate names receive a suffix such as `name (2)`. Calling `report` without a folder or project fails, as does supplying both.

You can still register a repository in the UI and index using its unique registered name, or list saved projects. Names use ASCII case-insensitive matching; IDs are not accepted by `--project`. Quote names containing spaces or shell characters:

```sh
(cd dashboard && bun run architecture:index /path/to/repository --project 'PROJECT_NAME')
uv run --project atlas atlas projects
```

`projects` returns all registered projects as a JSON array with IDs, names, locations, and registration/index timestamps; `importedAt: null` means not yet indexed.

The report shows only what each finding is about, file paths and callable line numbers, and readable explanations. Functions/methods match **any** strict threshold: total cyclomatic complexity > 8, nested-loop count > 0, or maximum decision depth > 3. Circular imports include affected paths and an example cycle. Use `report --format json` for a compact structured findings object. Project reports read the saved graph without reindexing; folder reports analyze fresh source. See [report details](atlas/README.md#human--and-llm-readable-project-report).

Run Bun commands from `dashboard/` (or use `bun run --cwd dashboard SCRIPT` from the root). Python commands above run from the repository root. Tests use source fixtures and checked-in regression snapshots, not generated repository exports.

The index command prints `repositoryId`, `schemaVersion`, and `stats` as JSON. It analyzes the graph in memory and transactionally replaces the repository's saved graph; it does not create a JSON artifact file. Reindex and refresh the graph in the UI to see new results. The repository URL or path entered during registration is metadata, not a source fetch.

`DATABASE_PATH` selects the shared SQLite database for `db:migrate`, `architecture:index`, and the Bun server; Python CLI commands also accept `--database PATH`. Python and Bun default to `$XDG_DATA_HOME/atlas/atlas.sqlite` (or `~/.local/share/atlas/atlas.sqlite`), independent of the working directory and outside analyzed repositories. Use an absolute `DATABASE_PATH` when overriding it. Existing databases at `data/atlas.sqlite` remain usable by setting `DATABASE_PATH` to their absolute path; the CLI does not move them automatically. Folder reports migrate automatically unless `--skip-save` is set. Run migrations before starting the UI or using `index`: neither general service access nor Bun creates tables or runs migrations. Back up existing databases before upgrading. Migrations preserve stored graphs and backfill the relational analysis tables without reindexing. Keep the UI server on a trusted local network: there is no authentication.

## Exclude files from analysis

Add a `.atlasignore` file at the root of any folder you analyze. It uses `.gitignore` syntax to exclude files from importing, indexing, and fresh reports without removing them from Git:

```gitignore
# Intentional test fixtures
/atlas/tests/fixtures/coffee/
*.generated.ts
scratch/**
!scratch/keep.py
```

Nested `.atlasignore` files apply relative to their directory. Patterns support comments, wildcards, directory rules, and `!` exceptions; exceptions cannot restore files excluded by `.gitignore` or built-in fallback rules, or files inside an excluded parent directory. `.atlasignore` works without Git and does not change the existing `.gitignore` behavior. Reindex or run a folder report to update saved results; project reports read the previous index. This repository excludes the coffee fixtures, while tests can still analyze those fixture folders directly.

## Explore

```text
Repository → Folders at any depth → File → Functions
```

Use **Explore** or the contents list to enter a node; breadcrumbs navigate up. Select a node to inspect incoming/outgoing relationships, pan and zoom the graph, or search the current list by name/path. Single-child folder chains are compacted visually without losing ancestors. Test files and their dependencies are hidden from graph views, not deleted from the indexed graph. Dependency arrows point from source to target; outside-scope dependencies are dashed. Function and method complexity appears in the sidebar, with a UI-only sum for files. Selecting a folder, file, or callable also shows indexed **fan-in**, **fan-out**, and **transitive change impact**. These count distinct internal peers at the same module/file/type/callable level: direct dependents, direct dependencies, and all direct or indirect dependents, respectively. Counts use the full index (including tests and type-only dependencies), not just visible connections, exclude the selected node and unresolved external targets, and represent potential impact rather than proof that behavior changes. Reindex older repositories to populate these metrics; missing values are not shown as zero.

## Architecture and checks

- `atlas/src/atlas/`: discovery, Tree-sitter extraction, in-memory artifact model, SQLite persistence, and CLI. See [Atlas](atlas/README.md).
- `atlas/src/atlas/persistence/migrations/`: packaged Alembic revisions defining the SQLite schema, including normalized graph analysis tables. Apply with `bun run --cwd dashboard db:migrate`.
- `dashboard/`: self-contained Bun/React app, with its package manifest, public assets, and tooling configs. `bun run build` regenerates the ignored route tree before typechecking a fresh checkout.
- `dashboard/src/routes/` and `dashboard/src/lib/`: web screens and Bun server routes that directly read and register repositories in the shared SQLite database; TypeScript does not own the schema or migrations.
- `dashboard/src/components/graph/` and `dashboard/src/lib/project-graph.ts`: graph navigation, layout, and projections.

```text
Python index CLI → service → repository → shared SQLite
                       ↓          ↓
                    domain     SQLAlchemy
Python migrate CLI → Alembic ─────────→ same SQLite file
Bun UI server routes (read/register) ─→ same SQLite file
```

`domain/repositories.py` defines Pydantic DTOs and application errors; `services/repositories.py` owns validation and indexing orchestration; `persistence/repositories.py` owns queries and transactions. No ORM rows cross into the interface or service.

For schema changes, edit `persistence/models.py`, then generate and review a revision:

```sh
(cd atlas && uv run alembic revision --autogenerate -m "describe change")
bun run --cwd dashboard db:migrate
```

```sh
(cd atlas && uv run pytest && uv run pyright && uv run ruff check .)
cd dashboard
bun run build
bun test
bun run typecheck
bun lint --fix
```
