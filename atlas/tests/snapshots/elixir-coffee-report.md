## Complexity: `brewing/brewer.ex::Coffee.Brewing.Brewer.classify`

Files:
- `brewing/brewer.ex:28`

Findings:
- Cyclomatic complexity is 9 (limit: 8).

## Complexity: `brewing/brewer.ex::Coffee.Brewing.Brewer.ready`

Files:
- `brewing/brewer.ex:42`

Findings:
- Decision nesting depth is 4 (limit: 3).

## Circular dependency: `Circular imports`

Files:
- `brewing/recipe.ex`
- `reporting/report.ex`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/recipe.ex → reporting/report.ex → brewing/recipe.ex.
