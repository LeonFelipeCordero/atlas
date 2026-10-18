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

## Mutation testing

Mutation testing is slow: each mutation starts its selected test commands. The full campaign for this repository is estimated to take 70–90 minutes on the development machine, based on a partial run, not a completed benchmark.

For routine changes, select only mutation targets that cover the changed code and affected consumers. Inspect `mutations.targets` in root `atlas.json`, including each target's `sources` and `command`. Include affected consumer targets when changing shared code. Do not run the full mutation campaign as a default validation step; use `--target all` only when explicitly requested or when a broad audit is justified.

From the repository root, for example:

```sh
uv run --project atlas atlas mutations run --folder . --target complexity,parsing
```

Replace the example targets with those relevant to the change. `--target` accepts comma-separated names or `all`. Omit it for interactive selection; non-interactive runs must pass it explicitly. This guidance applies to mutation execution only. Keep the normal checks above and below, and analyze the entire project with `atlas check`.

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

