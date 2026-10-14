# Repository registration → imported graph

## Evidence and runtime

Graphify’s existing directed AST graph retrieved `registerRepository`, `importRepositoryArtifact`, `getArchitecture`, `GraphExplorer`, and their source files. Expansion used graph-vocabulary tokens: repository, register, architecture, artifact, import, database, route, graph, render, cache, error, runtime. Budgeted queries were truncated; `explain repositories.servers.ts` exposed extracted imports/containment. A directed path from repository-form to database was absent—not proof the HTTP workflow is absent. The cross-process connections below are **source interpretation**, verified by targeted reads, not claimed AST call edges.

Current commands use Bun/TypeScript: `graph-code` runs `graph_code_ts/cli.ts`; `architecture:import` runs `scripts/import-architecture.ts`; production starts `.output/server/index.mjs` (`package.json:5–26`). The TS CLI invokes `indexRepository` and reports errors/status (`graph_code_ts/cli.ts:103–164`). Analysis discovers files, parses, resolves connections, builds an artifact; indexing writes it (`graph_code_ts/indexer.ts:31–39,59–65`). Python is not called in that runtime chain. The waiting-page copy still recommends the “existing Python indexer” (`src/routes/graph.$repositoryId.tsx:124–128`): legacy guidance, not runtime evidence.

```mermaid
flowchart TD
  Browser[RepositoryForm] -->|POST name/location| Register[/api/repositories]
  Register -->|registerRepository| DB[(SQLite repositories)]
  Source[Local source directory] --> TS[Bun TS indexer]
  TS --> JSON[Schema-v2 JSON file]
  JSON --> Import[Separate terminal architecture:import]
  Import -->|validate + transactional upsert| GraphDB[(SQLite repository_graphs)]
  DB --> GET[/GET api/architecture?repositoryId/]
  GraphDB --> GET
  GET --> Query[React Query graph cache]
  Query --> Explorer[GraphExplorer projection]
  Explorer --> Canvas[Lazy ReactFlow canvas]
```

## Registration and independent import

The form posts `{name, location}`, invalidates only `['repositories']` on success, and displays mutation errors. Location is reference-only; nothing is cloned or analyzed (`src/components/repository-form.tsx:12–22,33–37,66–72`). POST parses JSON, returns 201, or 400 for malformed JSON (`src/routes/api/repositories.ts:18–29`). Registration trims/limits name and location, creates UUID/timestamp, and returns `importedAt:null`; duplicate names return 409 (`src/lib/repositories.servers.ts:17–47`). Names have a case-insensitive unique index (`src/lib/database/schema.ts:10–20`).

Import reads a supplied JSON file and project ID/name directly in the terminal, not through an HTTP upload; failure prints an error and sets exit code 1 (`scripts/import-architecture.ts:4–21`). Schema-v2 validation checks nodes, hierarchy, edges and cycles, returning the original artifact without rebuilding metadata (`src/lib/architecture-artifact.ts:378–429`). Import validates before its transaction, prefers exact ID then case-insensitive name, returns 404 for no repository, and replaces that repository’s artifact/timestamp through an upsert (`src/lib/repositories.servers.ts:85–117`).

Persistence is Bun SQLite/Drizzle, `DATABASE_PATH` or cwd-relative `data/graph-explorer.sqlite`, with migrations, WAL and foreign keys (`src/lib/database.servers.ts:8–32`). Each repository has one JSON artifact row plus import timestamp (`src/lib/database/schema.ts:23–30`). Separate processes must resolve the same database path.

## Retrieval, rendering, failure and staleness

GET rejects missing ID with 400; unknown repository is 404, registered/unimported is JSON null; unexpected service errors become generic 500 (`src/routes/api/architecture.ts:11–23`; `src/lib/repositories.servers.ts:67–81,120–125`).

The graph query is keyed by repository ID with retries disabled. Refresh refetches graph and repository list; null shows import instructions, errors show retry, and data mounts an explorer keyed by ID/import timestamp (`src/routes/graph.$repositoryId.tsx:18–33,71–102`). Terminal import sends no browser invalidation. Cached data can remain visible, including alongside a refetch error; no polling is configured here. QueryClient has no custom defaults; exact library-default timing remains unverified (`src/router.tsx:5–12`).

Explorer hides test files, projects current scope, and lazy-loads the canvas (`src/components/graph/graph-explorer.tsx:13,28–40,74–94`). Projection aggregates direct relationships and outgoing boundaries without mutating the artifact (`src/lib/project-graph.ts:213–247`). ReactFlow lays out nodes, renders directed edges, and handles selection/drilldown (`src/components/graph/graph-canvas.tsx:104–173`). Runtime success, deployment database configuration, and render-error recovery were not exercised; application execution was prohibited.
