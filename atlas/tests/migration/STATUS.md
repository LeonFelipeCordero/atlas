# Shared sample snapshot coverage

The positive corpus is nine realistic coffee-shop projects in `tests/fixtures/coffee/`: Python, Java, Kotlin, Go, Rust, JavaScript, TypeScript, Elixir and TSX. Their 63 source/configuration files implement brewing, orders, stock, receipts and UI flows. Numeric padding and deliberately oversized calibration functions are gone. Go uses real packages and `go.mod`; Rust uses a standard crate/module tree.

## One source project, every seam

`coffee_pipeline.py` collects ordered source bytes and hashes, parser records **before** metric enrichment, raw native metadata, tags-only and native-merged structures, enriched declarations, resolved connections, and production CLI report/check output in JSON and Markdown. `tests/snapshots/coffee/<language>/` holds extraction, analysis and CLI bundles. Complete graph, Markdown and saved-navigation baselines remain alongside them. The shared order contract is additionally captured by the actual TSX parser plus native/tags-only structures, without copying the TypeScript source; its migration entry points to that explicit grammar variant.

`uv run python -m tests.update_coffee_snapshots --navigation` regenerates all those seams. It deliberately does **not** regenerate the feature contracts or independently reviewed inventories.

The 280 contracts in `coffee_features_{oo,systems,scripts}.json` pin exact signatures, kinds, decorators, per-overload parameter/complexity records and outgoing relationships. Tests require each feature to reach parser, enrichment, native-merged structure, resolution, graph and applicable CLI metrics. Tags-only enum/constructor/impl-ownership differences are explicit expectations. Exact path-keyed inventories in `coffee_scenarios.py` prevent discovery omissions from disappearing from both sides of a comparison. Contract-regression tests reject extra receiver counts, lost generic inheritance/recursion, missing graph/CLI records and omitted source files.

Language-specific source includes Python decorators/full parameter signatures/pattern matching; Java generics, overloads, receivers and references; Kotlin companions, extension receivers and nested lambdas; Go methods, grouped inputs and closures; Rust inherent implementations, receivers, modules, closures and macro payloads; Elixir guards, clauses, captures and pipelines; script function/generator carriers, destructuring and defaults; TypeScript callable interface shapes, overloads and type-only imports; TSX components, namespaces, prop shadowing and event handlers.

## Consolidation and retained probes

`coffee_consolidation.json` and `coffee_resolution_consolidation.json` in `tests/` account for 131 parsing/metric and 64 receiver/import variants respectively. They distinguish replaced, partial and retained cases, name concrete project/declaration/assertion destinations, and explain retained discriminators. `migration/coffee_consolidation.json` records the 54 removed fixture-project destinations. Their 117 redundant snapshots are removed, along with 56 coffee-only micro baselines, one duplicate TSX import baseline and 64 static CLI source-state replays. There are now 27 full-project seam bundles instead.

The remaining focused corpus is not concatenated into healthy projects. Malformed/byte-exact input, missing/stale native metadata, ambiguous roots or identities, reassignment/mutation, forbidden architecture/SQL constructs, unsupported grammar carriers and exact metric discriminators remain independent. Stateful CLI transcripts still cover configuration, errors, fresh/save/reindex effects, rollback and isolation. Literal default size boundaries remain in dedicated tests rather than padding the domain examples.

Some valid language constructs still resolve externally under current production policies, notably Go module-prefixed imports, Elixir grouped aliases and selected inherited/injected receivers. These have exact source-grounded external-target assertions; snapshots do not disguise them as successful internal resolution. No production behavior or thresholds were changed.

`inventory.txt` preserves historical function provenance. The inventory gate now also verifies every concrete referenced fixture/snapshot destination exists. Byte-preserving Git attributes cover both source corpora; fixture and derived-bundle exclusions keep full-repository checks and the existing cold-process budget focused on implementation code. README and dashboard are unchanged.

## Validation

Full importer suite: **3,306 passed**, **635 subtests passed**, same nine existing SQLite migration warnings. Pyright: zero errors/warnings. Ruff and strict whole-project Atlas check: clean, with no threshold changes. Full-project Atlas report: zero parse errors. Language-specific compilation/runtime smoke checks also passed where available.
