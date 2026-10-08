## Complexity: `brewing/Brewer.ts::Brewer.score`

Files:
- `brewing/Brewer.ts:20`

Findings:
- Nested-loop count is 1 (limit: 0).

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.ts`
- `reporting/Report.ts`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.ts → reporting/Report.ts → brewing/Recipe.ts.
