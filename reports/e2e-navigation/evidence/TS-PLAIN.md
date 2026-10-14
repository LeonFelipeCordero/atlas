# Repository registration → imported architecture → graph

Source root: `snapshot/doc-gen`. Citations below are relative to it. Static source investigation only; no application execution.

```mermaid
flowchart TD
  Browser[Browser repository form] -->|POST /api/repositories| Register[Validate and register]
  Register --> DB[(Bun SQLite / Drizzle)]
  DB -->|GET /api/repositories| List[Repository list]
  List --> Page[/graph/$repositoryId]
  Terminal[Separate terminal: Bun TS indexer] --> JSON[Schema-v2 graph.json]
  JSON --> Import[architecture:import file project-ID-or-name]
  Import -->|validate + transactional upsert| DB
  Page -->|GET /api/architecture?repositoryId=ID| Read[Read stored snapshot]
  DB --> Read
  Read --> Explorer[Filter tests; project direct relationships]
  Explorer --> Canvas[Dagre layout + React Flow]
```

## Actual runtime and separation

The manifest selects Bun/Vite/TanStack Start for the web app, `bun graph_code_ts/cli.ts` for `graph-code`, and `bun scripts/import-architecture.ts` for imports (`package.json:8-26`; `vite.config.ts:18-28`). The TS CLI calls `indexRepository`, whose pipeline validates the directory, discovers/parses files, resolves connections, builds the artifact, and writes it (`graph_code_ts/cli.ts:143-166`; `graph_code_ts/indexer.ts:31-38,59-65`). This is a separate manual producer, not invoked by registration.

Python remains a separately packaged `graph-code` executable (`graph_code/pyproject.toml:20-24`). The waiting-page instruction saying “existing Python indexer” is inconsistent with the root manifest’s current TS command (`src/routes/graph.$repositoryId.tsx:122-127`). Import accepts schema-v2 JSON rather than invoking either extractor.

## Browser and persistence

The form POSTs `{name, location}`; success invalidates `['repositories']` and closes the form. Location is explicitly reference-only, with no cloning/access (`src/components/repository-form.tsx:12-23,56-70`). POST parses JSON, returns 201 on registration, or 400 for malformed JSON (`src/routes/api/repositories.ts:19-29`). Registration trims/limits fields, generates UUID/time, and inserts; duplicate case-insensitive names return 409 (`src/lib/repositories.servers.ts:17-48`; `src/lib/database/schema.ts:10-21`). List GET left-joins import timestamps; rows link to the graph route (`src/lib/repositories.servers.ts:50-65`; `src/components/repository-row.tsx:9-28`).

The terminal importer resolves/reads the file and calls the shared import service directly—not an HTTP upload (`scripts/import-architecture.ts:4-17`). Artifact validation precedes a transaction that resolves exact ID first, then case-insensitive name, and replaces the repository’s single graph row with a fresh import timestamp (`src/lib/repositories.servers.ts:86-120`). Validation checks schema, nodes, hierarchy, references and cycles while retaining the original artifact (`src/lib/architecture-artifact.ts:121-419`). SQLite stores the complete JSON artifact under a foreign-key repository ID (`src/lib/database/schema.ts:23-30`). Server and terminal must target the same database: `DATABASE_PATH` or cwd-relative `data/graph-explorer.sqlite`; opening enables WAL/foreign keys and runs cwd-relative migrations (`src/lib/database.servers.ts:8-32`).

## Retrieval, display, failures and staleness

Architecture GET requires an ID (400), returns 404 for an unknown repository, and JSON null for registered-but-unimported (`src/routes/api/architecture.ts:10-23`; `src/lib/repositories.servers.ts:67-83`). Unexpected server errors become generic 500; CLI file/validation/database failures print errors and exit 1 (`src/lib/repositories.servers.ts:123-128`; `scripts/import-architecture.ts:18-21`). Failed imports do not replace the stored snapshot.

The graph query is keyed by repository ID with retries disabled. Loading, errors and null/waiting states are distinct; cached data can still render alongside a refetch error (`src/routes/graph.$repositoryId.tsx:19-34,71-100`). Refresh refetches graph and list; a changed import timestamp remounts the explorer, resetting navigation (`:31-34,93-101`). No polling, push invalidation, or explicit query stale-time is configured; library defaults govern automatic refetch/cache retention (`src/router.tsx:5-12`). Exact deployed cache behavior is unverified.

Explorer derives a test-hidden artifact, projects direct edges rather than stored views, and lazily renders the canvas (`src/components/graph/graph-explorer.tsx:13,28-40,74-91`; `src/lib/project-graph.ts:192-267`). Dagre positions feed React Flow; clicks select and double-clicks navigate (`src/components/graph/graph-layout.ts:4-40`; `src/components/graph/graph-canvas.tsx:104-190`). Rendering failures reach the root error boundary (`src/routes/__root.tsx:39-44`). Deployment environment, database availability and actual imported content remain unknown.
