# Python CLI testing strategy

Use code-sample snapshot tests as the primary coverage for indexing, `check`, `report`, and graph navigation. Expand the shared sample projects in `atlas/tests/code_samples/` and their snapshots in `atlas/tests/snapshots/` to exercise as much of this logic as possible through the production pipeline, rather than adding isolated unit tests or inline code snippets.

For features and regressions in these areas, extend the relevant samples and snapshot assertions. Review snapshot changes against the intended behavior; do not regenerate baselines just to make a failing test pass. Existing coverage includes `test_coffee.py`, `test_coffee_pipeline.py`, and the `test_coffee_*_snapshots.py` suites.

Logic outside indexing, `check`, `report`, and graph navigation must have unit tests. Do not require separate unit tests for logic covered by the code-sample snapshots in those four areas.

# Mutation manifests

Mutation generation is opt-in in the target root's `atlas.json`:

```json
{"mutations": {"rules": ["arithmetic.add-to-subtract", "logical.or-to-and"]}}
```

`mutations.rules` is a list of rule IDs, not the old rule-to-replacement dictionary (which is rejected). Omitted rules or `[]` disable generation; duplicates are harmless. Selecting an ID enables every applicable language mapping. See `atlas/MUTATIONS.md` for the complete catalog.

```sh
uv run --project atlas atlas mutations --rules # Inspect rules and language mappings
uv run --project atlas atlas mutations -f . # Analyze fresh sources without saving
uv run --project atlas atlas index -f . # Save candidates after migrations
uv run --project atlas atlas mutations -f . --saved # Verify saved candidates against source
```

Saved mode never refreshes the index; missing or stale source fails the entire request, so reindex after changes. Output contains independent single-edit alternatives against original source, never sequential patches. These commands only generate manifests: do not apply mutations or execute them.

# Checks

Always run these commands from the repository root to validate your changes.

## Importer

```sh
(cd atlas && uv run pytest -n auto) # Run importer tests in parallel
(cd atlas && uv run pyright) # Check Python types
(cd atlas && uv run ruff check .) # Lint importer code
```

`pytest-xdist` selects the worker count with `-n auto`; use `-n 4` to limit it to four workers. Omit `-n` for a serial run. Keep files, databases, and ports isolated between tests. Session-scoped fixtures run once per worker.

## Dashboard

```sh
(cd dashboard && bun run build) # Regenerate routes and verify the production build
(cd dashboard && bun test) # Run dashboard tests
(cd dashboard && bun run typecheck) # Check TypeScript types
(cd dashboard && bun lint --fix) # Lint dashboard code and apply fixes
```

# Atlas

Run atlas against the entire project being worked on, not just the changed files.

For this project, from the repository root:

```sh
uv run --project atlas atlas check --f . # Analyze this entire project without saving
```

For another project:

```sh
uv run --project /path/to/atlas/atlas atlas check --f /path/to/project # Analyze another entire project without saving
```
