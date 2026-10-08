# Checks

Run these commands from the repository root.

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
uv run --project atlas atlas report --f . --skip-save # Analyze this entire project without saving
```

For another project:

```sh
uv run --project /path/to/atlas/atlas atlas report --f /path/to/project --skip-save # Analyze another entire project without saving
```
