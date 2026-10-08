## Complexity: `brewing/Brewer.kt::Brewer.score`

Files:
- `brewing/Brewer.kt:22`

Findings:
- Nested-loop count is 1 (limit: 0).

## Complexity: `brewing/Brewer.kt::Brewer.classify`

Files:
- `brewing/Brewer.kt:34`

Findings:
- Cyclomatic complexity is 9 (limit: 8).

## Complexity: `brewing/Brewer.kt::Brewer.ready`

Files:
- `brewing/Brewer.kt:48`

Findings:
- Decision nesting depth is 4 (limit: 3).

## Size: `brewing/Brewer.kt`

Files:
- `brewing/Brewer.kt`

Findings:
- File line count is 601 (limit: 600).

## Size: `brewing/Brewer.kt::Brewer.calibrate`

Files:
- `brewing/Brewer.kt:61`

Findings:
- Function line count is 104 (limit: 100).
- Parameter count is 8 (limit: 7).

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.kt`
- `reporting/Report.kt`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.kt → reporting/Report.kt → brewing/Recipe.kt.
