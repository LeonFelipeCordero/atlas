## Complexity: `brewing/brewer.rs::score`

Files:
- `brewing/brewer.rs:22`

Findings:
- Nested-loop count is 1 (limit: 0).

## Circular dependency: `Circular imports`

Files:
- `brewing/recipe.rs`
- `reporting/report.rs`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/recipe.rs → reporting/report.rs → brewing/recipe.rs.
