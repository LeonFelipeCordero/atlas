## Circular dependency: `Circular imports`

Files:
- `brewing/recipe.ex`
- `reporting/report.ex`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/recipe.ex → reporting/report.ex → brewing/recipe.ex.
