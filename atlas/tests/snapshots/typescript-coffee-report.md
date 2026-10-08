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

## Size: `brewing/Brewer.ts`

Files:
- `brewing/Brewer.ts`

Findings:
- File line count is 601 (limit: 600).

## Size: `brewing/Brewer.ts::Brewer.calibrate`

Files:
- `brewing/Brewer.ts:61`

Findings:
- Function line count is 104 (limit: 100).
- Parameter count is 8 (limit: 7).

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.ts`
- `reporting/Report.ts`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.ts → reporting/Report.ts → brewing/Recipe.ts.
