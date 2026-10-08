## Complexity: `brewing/Brewer.kt::Brewer.score`

Files:
- `brewing/Brewer.kt:22`

Findings:
- Nested-loop count is 1 (limit: 0).

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.kt`
- `reporting/Report.kt`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.kt → reporting/Report.kt → brewing/Recipe.kt.
