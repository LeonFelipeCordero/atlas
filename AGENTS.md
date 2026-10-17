# Python CLI testing strategy

The snapshot testing it's to have a high coverage of features per language without having to add many tests. Also helps to consolidate testing via the samples. Use it wisely to include new features, metrics, or commands. If some new language feature is to be added, include in the code samples.

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

