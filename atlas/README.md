# Atlas

Atlas analyzes repositories with Tree-sitter, builds version-2 graph artifacts in memory, and stores the current graph per repository in SQLite. It supports languages recognized by the pinned `tree-sitter-language-pack`, except C and C++. Those grammars are excluded from discovery and direct extraction.

## Setup and usage

From the repository root:

```sh
uv sync --project atlas --group dev
(cd dashboard && bun install && bun run db:migrate && bun run dev)
```

Register a repository in the web UI, then index its local source path in another terminal. The Bun UI server reads and registers directly in the same SQLite file; no Python HTTP server is required:

```sh
uv run --project atlas atlas index /path/to/project --project 'PROJECT_NAME'
# Or, from inside the project: atlas index --project 'PROJECT_NAME'
```

`--project` accepts only a unique registered project name, not an ID. Names are unique under SQLite's ASCII case-insensitive comparison, and lookup uses the same comparison. Quote names containing spaces or shell characters. `index` analyzes in memory and transactionally upserts the saved graph, without writing an artifact file. It prints a JSON summary:

```json
{
  "repositoryId": "registered-id",
  "schemaVersion": 2,
  "stats": { "files": 199, "symbols": 1241, "nodes": 2110, "edges": 7005 }
}
```

Set `DATABASE_PATH` to share a database among Python commands and the Bun server, or pass `--database PATH` before the command or to `migrate`, `projects`, `index`, and `report`. Python and Bun default to `$XDG_DATA_HOME/atlas/atlas.sqlite`, falling back to `~/.local/share/atlas/atlas.sqlite`. The database is central and independent of the source folder or working directory. Existing repository-root `data/atlas.sqlite` databases are not moved; set an absolute `DATABASE_PATH` to keep using one. Python alone owns the schema and migrations. Bun opens the migrated database without creating tables or running migrations. Migration revisions are packaged in `src/atlas/persistence/migrations/`; apply them with `atlas migrate` before starting Bun. For schema changes, edit `persistence/models.py`, run `uv run alembic revision --autogenerate -m "describe change"` from `atlas/`, and review the generated revision before applying it. Start with a fresh database when replacing an older one; re-register projects and reindex their source paths. Back up data before replacing it. Folder reports migrate automatically unless `--skip-save` is set; `index` and general service access still require explicit migration.

## List registered projects

```sh
atlas projects
# Select a shared database explicitly:
atlas projects --database /path/to/atlas.sqlite
```

`projects` prints a JSON array of all registered projects, including those not yet indexed. Each entry contains `id`, `name`, `location`, `createdAt`, and `importedAt` (Unix milliseconds; `null` when never indexed). Use the `name` with `--project` for indexing or reporting; IDs remain internal storage and API identifiers. No `--project` is required; an empty database returns `[]`. Global `--database` and `DATABASE_PATH` also work. Listing does not index or modify saved graphs; migrate the database first.

## Human- and LLM-readable project report

Analyze a folder, or read the latest saved index by unique registered project name:

```sh
atlas report --f ./                            # Analyze current directory and save
atlas report --f /workspace/projects/atlas   # Analyze target folder and save
atlas report --p PROJECT_NAME                  # Read saved analysis only
atlas report -f ./ --skip-save                 # Analyze without database access
atlas report                                  # Error: folder or project required
# Optional structured output and database override:
atlas report -f ./ --format json --database /path/to/atlas.sqlite
# Existing global project syntax also works:
uv run --project atlas atlas --project 'PROJECT_NAME' report
```

Folder aliases are `-f`, `--f`, and `--folder`; project aliases are `-p`, `--p`, and `--project`. Specify exactly one source; folder and project options cannot be combined, including a global `--project`. `--skip-save` requires a folder. Project lookup accepts names only, not IDs, and uses SQLite's ASCII case-insensitive comparison.

Folder mode analyzes fresh source in memory, builds the report, migrates the central database, and saves the graph. It matches repositories by resolved absolute location (including symlink aliases), preserving existing IDs and names. An unregistered folder is registered under its basename; if another location already uses that name, a suffix such as `name (2)` is added. Registration and graph saving are atomic. Analysis failures leave existing results untouched; save failures roll back the writes and fail the command. No database or graph artifact is written inside the source folder unless you explicitly select a database path there. `--skip-save` does not open, create, migrate, or update any database.

`report` prints findings-only Markdown to stdout, readable by humans and LLMs. Each section identifies what the finding is about, repository-relative file paths (with one-based line numbers for functions/methods), and a plain-language explanation. There are no repository metadata, counts, diagnostics, stable keys, signatures, or unrelated metrics.

```markdown
## Complexity: `App.process`

Files:

- `src/app.py:42`

Findings:

- Cyclomatic complexity is 12 (limit: 8).
- Decision nesting depth is 4 (limit: 3).

## Circular dependency: `Circular imports`

Files:

- `src/a.py`
- `src/b.py`

Findings:

- These files form a circular import dependency.
- Example cycle: src/a.py → src/b.py → src/a.py.
```

For structured tooling, use `atlas report --project 'PROJECT_NAME' --format json`. The indented JSON contains only `{"findings": [...]}`. Each finding has `type` (`complexity`, `size`, or `circular_dependency`), `subject`, `files` (`path` and, when available, `line`), and `details` (readable explanations). Unknown callable locations use `null`; Markdown displays `Unknown file` and omits unavailable lines. Empty reports print `No findings.` in Markdown or `{"findings": []}` in JSON. This replaces the previous metadata-heavy JSON contract.

Project mode does not reindex, change the saved graph, or require the source files to exist. Use folder mode for current results. Missing projects or projects without an index produce an error on stderr and a nonzero exit code; findings themselves do not cause failure. Command-local options override global options; `DATABASE_PATH` remains the database fallback.

Each function/method appears once per finding category, showing only exceeded metrics and their limits. Complexity findings come first, then size findings, then circular dependencies. Within each metric category, findings sort by path, start line, and stable key. Complexity rules are **independent** and strictly greater than:

| Metric                                                           | Threshold |
| ---------------------------------------------------------------- | --------- |
| `cyclomaticComplexity` (total, including penalties)              | 8         |
| `loopNestedComplexity` (nested-loop count)                       | 0         |
| `maxDecisionDepth` (decision nesting, not graph hierarchy depth) | 3         |

A nested-loop finding is included even when total complexity is 8 or less. Boundary values do not match. Missing metrics do not trigger a rule; older indexes may require reindexing to obtain metrics. All indexed files, including tests, are considered; UI-only filtering does not apply. Use `.atlasignore` to omit intentional fixtures from fresh analysis and indexing.

Size findings use these independent, strict thresholds:

| Node | Metric | Threshold |
| ---- | ------ | --------- |
| Function/method | `lineCount` | 100 |
| File | `lineCount` | 600 |
| Function/method | `parameterCount` | 7 |

`lineCount` counts physical lines, including comments and blanks. Callable counts cover the declaration span (signature and body, including nested declarations), not just executable statements. Empty files have zero lines; a final newline does not add another line. `parameterCount` counts declared input parameters, not call-site arguments: defaults, destructuring patterns, and variadics each count as one. Type parameters, receivers, comments, and syntax separators are excluded. Parameter counting has explicit grammar support for Python, JavaScript, TypeScript/TSX, Go, Rust, Java, Kotlin, and Elixir. Other languages, unsupported syntax, and implicit Kotlin lambda inputs leave the metric unavailable rather than zero. Metrics are stored in node properties, so existing databases need no schema migration; reindex to populate older graphs. File findings have a path; callable findings also include the declaration start line.

```markdown
## Size: `src/app.py::process`

Files:

- `src/app.py:42`

Findings:

- Function line count is 101 (limit: 100).
- Parameter count is 8 (limit: 7).
```

Circular dependency findings list all files in each stored import group and a representative closed cycle using paths, not graph IDs. A group is a strongly connected component, not an enumeration of every possible cycle. Legacy snapshots lacking cycle analysis are analyzed from stored import edges without reindexing. Detailed import evidence and parse diagnostics remain in the saved graph, not the report. Resolver and parsing limitations still apply; no findings is not proof that unparsed or unresolved code is problem-free.

## In-memory artifact contract

`analyze_repository(Path(...))` returns `GraphArtifact` without opening the database. Its fields are:

- `schemaVersion`: contract version required by consumers.
- `repository`: source path, name, index time, and detected languages.
- `stats`: file, symbol, node, edge, external-node, and parse-error counts.
- `nodes`: repository, file, symbol, and unresolved external entities.
- `edges`: `CONTAINS`, `IMPORTS`, `CALLS`, `REFERENCES`, and `INHERITS` relationships.
- `views`: dependency graphs projected at the module, file, type, and callable levels.
- `diagnostics`: parsing failures with path, language, severity, and message.
- `circularDependencies`: optional file-import cycle analysis (version 1).

Nodes use `stableKey`, `parentStableKey`, `ancestorStableKeys`, and `depth` to expose the complete hierarchy. `type` contains the concrete node type, such as `class`, `method`, or `file`, while `level` groups nodes into `module`, `file`, `type`, `callable`, and `symbol` layers. Directory-backed module nodes make package relationships available even when a language has no explicit module declaration.

Direct edges use `sourceStableKey` and `targetStableKey` and include the type, kind, and level of both endpoints. Each view rolls those direct relationships up to one hierarchy level and records relationship and confidence counts. For example:

```json
{
  "sourceStableKey": "module:api",
  "targetStableKey": "module:core",
  "type": "DEPENDS_ON",
  "level": "module",
  "count": 3,
  "relationshipCounts": {
    "CALLS": 2,
    "IMPORTS": 1
  }
}
```

Artifact stable keys are separate from database-generated repository identifiers.

```json
{
  "sourceStableKey": "symbol:src/service.ts::Service.run:71",
  "targetStableKey": "symbol:src/helper.ts::helper:0",
  "type": "CALLS",
  "confidence": "INFERRED",
  "path": "src/service.ts",
  "line": 8,
  "evidence": "helper()"
}
```

`EXTRACTED` means the relation appears directly in syntax. `INFERRED` means the resolver matched a path or an unambiguous symbol name. Unresolved and ambiguous targets remain explicit external nodes.

Call resolution combines AST-backed lexical scopes with explicit imports and conservative language-specific rules. It resolves imported static members, namespace export aliases, lexical `self`/`this` and immediate construction. Java/Kotlin declared packages need not match physical folders; Python relative dotted imports and Rust path/inline modules retain their module identity. Elixir call edges can target multiple clauses of one module/function/arity identity.

Python absolute imports resolve from the analyzed root, conventional `src/` directories (including namespace packages), and package roots inferred from contiguous `__init__.py` files, including nested projects. Comma-separated imports and `from package import child_module` retain each module's connection and namespace binding. Duplicate module names across source roots stay unresolved; runtime `.py` implementations are not made ambiguous by `.pyi` stubs. Existing package attributes prevent guessed child-module links. Custom runtime `sys.path` changes and arbitrary configured source directories are not inferred. After upgrading, rerun a folder report without `--skip-save` or reindex to replace the dashboard's saved graph; `No findings.` means no report-rule violations, not no dependencies.

Shadowing, rebinding, duplicate aliases and ambiguous targets do not produce guessed links. Unknown object receivers, arbitrary factories, inherited-member dispatch, re-exports and build-system manifests remain unsupported rather than matching unrelated methods by name. The legacy unique bare-name fallback is still heuristic, including cross-directory Go calls in the shared graph fixture. This is not universal type inference or compiler validation.

Explicit callable references contribute dependency edges. Rust macro invocations are captured without expansion; recognized evaluating standard-expression macros expose only syntactically valid payload calls. Stringification/unknown DSL payloads produce no guessed inner runtime calls, and payload-local bindings or opaque object receivers remain unresolved. Regression fixtures test both positive resolution and false-positive counterexamples across the eight retained sample languages.

## Circular file imports

Newly analyzed artifacts include `circularDependencies` without changing `schemaVersion: 2` or existing nodes, edges, views, and stats. Older in-memory artifacts may omit it; legacy `GraphArtifact` construction defaults it to `None`. An analyzed acyclic graph has `{"version": 1, "groups": []}`.

```json
{
  "circularDependencies": {
    "version": 1,
    "groups": [
      {
        "id": "import-cycle:<sha256 of sorted member keys>",
        "nodeStableKeys": ["file:a.py", "file:b.py"],
        "exampleCycle": ["file:a.py", "file:b.py", "file:a.py"],
        "edges": [
          {
            "sourceStableKey": "file:a.py",
            "targetStableKey": "file:b.py",
            "type": "IMPORTS",
            "path": "a.py",
            "line": 1,
            "evidence": "import b",
            "confidence": "INFERRED"
          },
          {
            "sourceStableKey": "file:b.py",
            "targetStableKey": "file:a.py",
            "type": "IMPORTS",
            "path": "b.py",
            "line": 1,
            "evidence": "import a",
            "confidence": "INFERRED"
          }
        ]
      }
    ]
  }
}
```

The Python analyzer uses only resolved raw `IMPORTS` edges, across indexed languages, not the mixed `DEPENDS_ON` views. Symbol endpoints project through their parents to files. External or missing endpoints, containment, calls, inheritance, and explicitly type-only imports are ignored. TypeScript `import type` and named imports containing only `type` specifiers retain their graph edges with optional `typeOnly: true` metadata but do not establish runtime cycles; mixed type/runtime imports still do. A group is a strongly connected component with at least two files, or a direct file-to-itself import; projecting symbols within one file never creates a self-import group.

Each group includes all internal projected import edges, preserving each original `path`, `line`, `evidence`, `confidence`, and `type` when present, including multiple import occurrences. `exampleCycle` is one closed directed chain, not an enumeration of all cycles. Members, groups, edges, and witnesses have deterministic ordering; IDs hash only sorted member keys, so evidence changes do not change group IDs. Iterative SCC and witness traversals avoid recursion limits and take linear graph work after sorting. Results inherit the resolver's heuristic limitations; unresolved imports cannot establish cycles.

## Dependency metrics

Fresh analysis adds optional `fanIn`, `fanOut`, and `transitiveChangeImpact` properties to every internal node in the module, file, type, and callable projections. Counts are nonnegative integers; isolated projected nodes receive zero. Repository, other-symbol, and external/unresolved nodes do not receive these metrics. Older artifacts can omit the properties without changing `schemaVersion: 2`; reindex to obtain them.

For a dependency `A → B`, A depends on B. `fanIn` counts distinct direct internal source peers; `fanOut` counts distinct direct internal target peers. `transitiveChangeImpact` counts unique peers that can reach the selected node through one or more dependency edges: its direct and indirect dependents. The selected node itself is excluded, including in cycles. In a diamond `A → B, A → C, B → D, C → D`, D's impact is 3, not 4. In a two-node cycle each node's impact is 1.

Metrics use the existing same-level `DEPENDS_ON` views: all non-`CONTAINS` relationships contribute, including type-only imports as compile-time dependencies. External/unresolved endpoints and intra-level self edges are excluded; repeated call sites and different relationship types between the same peers count once. No finding thresholds or report changes are associated with these properties. This differs from runtime-only circular import detection.

The analyzer reuses iterative SCC traversal, condenses cycles, and propagates reverse-reachability bitsets in source-first topological order. Bits represent original nodes so cycles and overlapping paths are counted exactly. Reachability sets are discarded after propagation rather than retaining an all-pairs closure; a long chain needs only one live bitset. Wide/dense graphs can still require multiple frontier bitsets. Results describe the resolved static graph, not guaranteed runtime impact.

## Function and method complexity

Indexing adds complexity fields to `properties` on **function and method nodes only**. No complexity is computed or rolled up for classes, files, modules, packages, repositories, constructors, or dependency views.

```json
{
  "baseCyclomaticComplexity": 5,
  "nestedCyclomaticComplexity": 2,
  "loopNestedComplexity": 1,
  "cyclomaticComplexity": 8,
  "maxDecisionDepth": 4
}
```

This example represents `for > for > if > if`. The calculation is:

```text
base = 1 + decision points + short-circuit logical operators
nested extra = number of decision points at nesting depth > 2
loop extra = number of loops with at least one enclosing loop
total = base + nested extra + loop extra
```

Each deep decision adds one, rather than adding its depth minus two. A single chain of three, four, or five decisions therefore adds one, two, or three; separate deep branches each contribute. A loop nested under multiple loops still adds only one loop penalty. An intervening `if` does not break loop ancestry. Sequential decisions do not increase nesting. Else-if/elif branches remain at the original if's depth, and plain else/default/wildcard arms add no decision.

The syntax-based analyzer recognizes common Tree-sitter loop, if, conditional/ternary, catch/except, and non-default case/match-arm nodes. Short-circuit `&&`, `||`, `and`, and `or` operators increase base complexity, but not structural nesting. Nested functions, lambdas, and classes are excluded from their enclosing callable; named functions, methods and extracted anonymous callbacks receive their own metrics. Empty functions start at one. Callable body selection excludes signatures/default arguments, including Kotlin's function-body wrapper. Elixir guards are retained; nested reducer callbacks have independent metrics rather than being counted as syntax loops.

This is a static syntax estimate, not a constructed control-flow graph. Shared node names cover common grammars (regressions include Python, JavaScript, TypeScript, Java, Kotlin, Go, Rust, and Elixir), but unusual grammar-specific control-flow nodes may be missed. Older artifacts can lack these additive properties; schema version remains 2.

## Code boundaries

- `discovery.py` validates the repository, detects language-pack grammars (excluding C and C++), and discovers files under ignore rules.
- `adapters/` is a Python package whose `__init__.py` registers the Java, Kotlin, Go, Rust, JavaScript, TypeScript, Elixir and Python policies in `<language>.py`. JSX uses the JavaScript policy and TSX uses the TypeScript policy. Other supported grammars retain generic fallback behavior. `base.py` defines the normalized extraction contract and shared metric policy; `resolution.py` provides scan-local indexes and generic resolution hooks.
- `extraction/` owns Tree-sitter processing: `syntax.py` contains shared traversal and declaration/call/import/inheritance helpers; `structure.py` merges native metadata and adapter queries; `parser.py` converts extracted facts into domain records; `resolution_syntax.py` handles generic lexical AST inspection; `complexity.py` accumulates callable-only syntax metrics using adapter policies.
- `domain/` owns graph records and post-extraction analysis: `models.py` defines strict Pydantic schemas; `resolver.py` assembles relationships and unresolved external targets; `artifact.py` creates in-memory projections, aggregates statistics and validates; `cycles.py` computes deterministic file-import cycle metrics and shared iterative SCCs; `dependency_metrics.py` computes distinct peers and reverse-reachable impact in dependency projections; `report.py` selects complexity violations and formats stored graph reports. Language-specific resolution stays in adapters.
- `domain/repositories.py` owns repository interfaces, Pydantic transport-independent DTOs and application errors. `services/` validates input and orchestrates indexing; `persistence/` owns SQLAlchemy models, queries, transactions, sessions, and packaged Alembic migrations. ORM rows never leave Python persistence, and storage failures become domain `RepositoryError` values.
- `bootstrap.py` is the composition root: it constructs service → repository → SQLite and exposes explicit migration wiring. Python CLI commands import bootstrap and operate through services, never persistence or database libraries. AST tests in `tests/test_database_boundaries.py` enforce these boundaries, including local, relative, aliased, and type-only imports; services and domain code cannot import bootstrap or CLI to bypass them. Only persistence may import SQLAlchemy, SQLite, or Alembic; only bootstrap may import persistence from outside that package. Bun server routes still read/register in that same database directly.
- `cli/commands.py` exposes Click commands through `cli/__init__.py`. Both `atlas` and `python -m atlas` use the same CLI.
- `indexer.py` orchestrates discovery, extraction, resolution, and in-memory artifact building.

Import parsing helpers from `atlas.extraction.parser`, records from `atlas.domain.models`, and artifact helpers from `atlas.domain.artifact`. Use `atlas.indexer.analyze_repository` for an in-memory graph.

Production modules are limited to 600 physical lines; architecture checks recursively enforce module/function limits and an acyclic import graph across all packages. There is no coffee-language allowlist. Data, documentation, configuration, and other files are analyzed whenever the language pack recognizes their grammar, except explicitly unsupported C/C++. When a root `.gitignore` exists, indexing follows it and nested `.gitignore` files, including negations, for both tracked and untracked files—even outside a Git repository. Otherwise it falls back to the hardcoded dependency/build directory exclusions and any folder matching `*generated*` (case-sensitive). `.git` metadata is always excluded.

`.atlasignore` adds analysis-specific exclusions independently of Git, even when no root `.gitignore` or `.atlasignore` exists. Each `.atlasignore` applies to its own directory and descendants, using the same Git ignore matcher: blank lines and `#` comments, wildcards (`*`, `?`, `**`), root-relative `/` anchors, trailing `/` directories, escaped leading `#`/`!`, and `!` negations. Later rules and nested `.atlasignore` files can override earlier `.atlasignore` patterns, but cannot restore Git-ignored paths or fallback-excluded directories. Ignored directories are not traversed: reinclude the parent before trying to reinclude a child. Files are excluded before reading and parsing, so their symbols, metrics, diagnostics, and import cycles are absent from the graph. Reindex or run a fresh folder report to replace saved results; project reports do not reread ignore files. Rules above the analyzed folder are not loaded, allowing tests to analyze excluded fixtures directly. See the [repository example](../README.md#exclude-files-from-analysis).

### Adapter contract

```text
source files → parser / native metadata / bundled queries
                              ↓
                       language adapter hooks
                              ↓
             normalized declarations / calls / imports
                              ↓
                 shared hierarchy / resolution ← resolution adapters
                              ↓
                     shared graph / projections
```

`LanguageAdapter` is a frozen record of small functions and grammar settings, not a class hierarchy. Declaration hooks return `DeclarationCarrier(node, name, kind, decorators)`; call hooks return `(node, byte_offset, opaque_payload, enclosing_roots)`. Call normalization returns `(name, bare_target, qualifier)` while shared code retains spans and evidence. Imports stay `(source_text, one_based_line)` and inheritance stays target-name strings. Normalized carriers feed the existing `StructureItem` metadata and graph records; schema version and resolution evidence/confidence are unchanged.

Kotlin supplements packages, companions and callbacks and corrects declaration names/kinds; Java normalizes constructors; Go pairs callback bindings by assignment position; Elixir excludes declaration heads while capturing pipeline calls. Rust selects external-module imports (excluding inline module bodies) and keeps safe, unexpanded macro payloads. Python decorators and JavaScript/TypeScript callback carriers are normalized without moving shared hierarchy into adapters. `process()` metadata is still supplemented by `extract_structure()`, including recovery of Kotlin methods missing from native children.

Call relationships are normalized by adapters too: explicit callable references and JSX component tags become `REFERENCES`, not immediate `CALLS`. Intrinsic tags, fragments and closing tags do not create dependencies; ordinary calls in JSX expressions are still extracted. `tests/fixtures/coffee/tsx/` exercises imported and namespace components plus shadowed props independently of snapshots.

To specialize another supported grammar, register its extraction hooks and optional resolution policy in `adapters.py`. Metric policies report decisions, scopes, alternatives and loops to the shared accumulator. Directory containment and dependency projections remain in `artifact.py`.

The architecture adapts [Graphify's](https://github.com/Graphify-Labs/graphify) explicit language dispatch, common extraction contract, and shared/private helper separation—not its source code, graph schema, or simpler resolution heuristics. Resolution inputs remain explicit and repository-local; there is no ambient scan-root state. Existing snapshots are compatibility checks, supplemented by source-grounded semantic and false-positive tests rather than treated as an oracle.

## Library usage

```python
from pathlib import Path
from atlas.indexer import analyze_repository

artifact = analyze_repository(Path("/path/to/project"))
```

Domain objects and `GraphArtifact` use Pydantic v2 dataclasses: positional constructors and `dataclasses.asdict()` remain supported. Constructors and attribute assignments reject invalid types without coercion. Artifact construction validates nested fields, relationship/confidence values, positive source positions, nonnegative counts, unique node keys, and parent/edge references. Call `validate_artifact(artifact)` to revalidate a snapshot after in-place list/dictionary edits. Filesystem checks and parsing/resolution guards remain. Schema version and optional fields are unchanged.

## Development

```sh
cd atlas
uv sync
uv run pytest
uv run pyright
uv run ruff check .
```

The Python Tree-sitter binding is constrained to 0.25: 0.26 crashes while indexing Kotlin with language pack 1.20. Re-sync the environment after dependency changes.

### Shared coffee snapshots

Python analyzes eight language samples (Java, Kotlin, Go, Rust, JavaScript, TypeScript, Elixir and Python) from `tests/fixtures/coffee/` against its own complete baselines in `tests/snapshots/`. The samples are copied from the TypeScript importer and include a separate TSX fixture. Tests use the production in-memory analyzer, which the indexing service also invokes. Snapshot comparison omits the indexing timestamp and normalizes repository paths after indexing to stay checkout-independent. Tests never update snapshots.

```sh
# From atlas/:
uv run python -m unittest tests.test_coffee -v
# Explicit regeneration after reviewing analyzer or sample changes:
uv run python -m tests.update_coffee_snapshots
```

All source-reviewed sample inventories and explicit call sites are captured; passing snapshots do not execute programs or imply universal language semantics.
