## Complexity: `brewing/Brewer.ts::Brewer.score`

Files:
- `brewing/Brewer.ts:20`

Findings:
- Nested-loop count is 1 (limit: 0).

## Complexity: `brewing/Brewer.ts::Brewer.classify`

Files:
- `brewing/Brewer.ts:34`

Findings:
- Cyclomatic complexity is 9 (limit: 8).

## Complexity: `brewing/Brewer.ts::Brewer.ready`

Files:
- `brewing/Brewer.ts:48`

Findings:
- Decision nesting depth is 4 (limit: 3).

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.ts`
- `reporting/Report.ts`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.ts → reporting/Report.ts → brewing/Recipe.ts.
