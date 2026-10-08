# Coffee graph samples

Preserved from the retired TypeScript importer: Java, Kotlin, Go, Rust, JavaScript, TypeScript, Elixir and Python versions of the same coffee workflow. Each language has two source files in `brewing/` and one in `reporting/`; Python uses `src/coffee/brewing/` and `src/coffee/reporting/` as a namespace package. The separate `tsx/` supplement exercises JSX component references and calls.

The samples cover imports, calls, recursion, inheritance, callbacks, nested complexity and the dependency cycle between Recipe and Report. Python additionally covers absolute dotted imports, module aliases, comma-separated module imports, named imports with aliases, relative named imports, multiline relative child-module imports, and absolute/parent-relative child-module imports. `import_styles` exercises each namespace or alias with real calls; semantic tests verify local file and callable targets independently of the snapshot. Generated artifacts and caches must stay outside the language roots.

Python tests index these directories with the production repository indexer used by the CLI. Full graph baselines live in `../../snapshots/`; comparison removes the indexing timestamp and normalizes absolute repository paths after indexing. Tests never rewrite baselines.

From `atlas/`:

```sh
uv run python -m unittest tests.test_coffee tests.test_tsx_coffee
# Regenerate only after reviewing fixture or analyzer changes:
uv run python -m tests.update_coffee_snapshots
```
