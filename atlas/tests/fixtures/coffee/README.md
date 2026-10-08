# Coffee graph samples

Preserved from the retired TypeScript importer: Java, Kotlin, Go, Rust, JavaScript, TypeScript, Elixir and Python versions of the same coffee workflow. Each language has two source files in `brewing/` and one in `reporting/`; Python uses `src/coffee/brewing/` and `src/coffee/reporting/` as a namespace package. The separate `tsx/` supplement exercises JSX component references and calls.

The samples cover imports, calls, recursion, inheritance, callbacks, nested complexity and the dependency cycle between Recipe and Report. Python additionally covers absolute dotted imports, module aliases, comma-separated module imports, named imports with aliases, relative named imports, multiline relative child-module imports, and absolute/parent-relative child-module imports. `import_styles` exercises each namespace or alias with real calls; semantic tests verify local file and callable targets independently of the snapshot. Generated artifacts and caches must stay outside the language roots.

Report findings are intentional: `classify` has eight sequential decisions (cyclomatic complexity 9), `ready` has four nested decisions (depth 4), and `score` has nested loops. Recipe and Report form an import cycle. In every language, `calibrate` has eight declared input parameters and more than 100 physical declaration lines, while its Brewer file exceeds 600 physical lines. Sequential calibration adjustments exercise length independently of branching (complexity stays 1); a marked reference-note ledger outside the callable exercises file length independently of callable length. Python's receiver does not count toward the eight inputs.

Together these cover all current report checks. Elixir's functional reductions are not measured as nested loops; Go's same-package calls are not an import cycle. The deliberately repetitive, oversized, and deeply nested fixtures must not be simplified, split, or have their reference notes trimmed: that would remove regression coverage. These fixture-only style violations are intentional; the root `.atlasignore` excludes them from normal full-repository reports.

Python tests index these directories with the production repository indexer used by the CLI. Full graph baselines live in `../../snapshots/`; comparison removes the indexing timestamp and normalizes absolute repository paths after indexing. CLI report baselines are the corresponding `*-coffee-report.md` files, compared against complete Markdown output. Separate JSON report assertions require both size findings, exact file/callable locations, and all three size limits to be exceeded in every language. Tests never rewrite baselines.

From `atlas/`:

```sh
uv run pytest tests/test_coffee.py tests/test_tsx_coffee.py tests/test_coffee_report_snapshots.py
# Regenerate only after reviewing fixture or analyzer changes:
uv run python -m tests.update_coffee_snapshots # Regenerates graph JSON and CLI report Markdown
```
