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

## Size: `brewing/brewer.ex`

Files:
- `brewing/brewer.ex`

Findings:
- File line count is 601 (limit: 600).

## Size: `brewing/brewer.ex::Coffee.Brewing.Brewer.calibrate`

Files:
- `brewing/brewer.ex:63`

Findings:
- Function line count is 104 (limit: 100).
- Parameter count is 8 (limit: 7).

## Circular dependency: `Circular imports`

Files:
- `brewing/recipe.ex`
- `reporting/report.ex`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/recipe.ex → reporting/report.ex → brewing/recipe.ex.
