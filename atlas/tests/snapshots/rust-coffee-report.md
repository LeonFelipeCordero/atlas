## Complexity: `brewing/brewer.rs::score`

Files:
- `brewing/brewer.rs:22`

Findings:
- Nested-loop count is 1 (limit: 0).

## Complexity: `brewing/brewer.rs::classify`

Files:
- `brewing/brewer.rs:36`

Findings:
- Cyclomatic complexity is 9 (limit: 8).

## Complexity: `brewing/brewer.rs::ready`

Files:
- `brewing/brewer.rs:50`

Findings:
- Decision nesting depth is 4 (limit: 3).

## Size: `brewing/brewer.rs`

Files:
- `brewing/brewer.rs`

Findings:
- File line count is 601 (limit: 600).

## Size: `brewing/brewer.rs::calibrate`

Files:
- `brewing/brewer.rs:64`

Findings:
- Function line count is 104 (limit: 100).
- Parameter count is 8 (limit: 7).

## Circular dependency: `Circular imports`

Files:
- `brewing/recipe.rs`
- `reporting/report.rs`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/recipe.rs → reporting/report.rs → brewing/recipe.rs.
