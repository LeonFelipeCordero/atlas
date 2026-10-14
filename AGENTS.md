# Python CLI testing strategy

Use code-sample snapshot tests as the primary coverage for indexing, `check`, `report`, and graph navigation. Expand the shared sample projects in `atlas/tests/fixtures/coffee/` and their snapshots in `atlas/tests/snapshots/` to exercise as much of this logic as possible through the production pipeline, rather than adding isolated unit tests or inline code snippets.

For features and regressions in these areas, extend the relevant samples and snapshot assertions. Review snapshot changes against the intended behavior; do not regenerate baselines just to make a failing test pass. Existing coverage includes `test_coffee.py`, `test_coffee_pipeline.py`, and the `test_coffee_*_snapshots.py` suites.

Logic outside indexing, `check`, `report`, and graph navigation must have unit tests. Do not require separate unit tests for logic covered by the code-sample snapshots in those four areas.

# Checks

Always run these commands from the repository root to validate your changes.

## Importer

```sh
(cd atlas && uv run pytest) # Run importer tests
(cd atlas && uv run pyright) # Check Python types
(cd atlas && uv run ruff check .) # Lint importer code
```

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
uv run --project atlas atlas report --f . # Analyze this entire project without saving
```

For another project:

```sh
uv run --project /path/to/atlas/atlas atlas report --f /path/to/project # Analyze another entire project without saving
```
