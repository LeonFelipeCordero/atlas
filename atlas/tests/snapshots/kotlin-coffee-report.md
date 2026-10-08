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

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.kt`
- `reporting/Report.kt`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.kt → reporting/Report.kt → brewing/Recipe.kt.
