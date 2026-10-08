## Complexity: `brewing/Brewer.js::Brewer.score`

Files:
- `brewing/Brewer.js:22`

Findings:
- Nested-loop count is 1 (limit: 0).

## Complexity: `brewing/Brewer.js::Brewer.classify`

Files:
- `brewing/Brewer.js:36`

Findings:
- Cyclomatic complexity is 9 (limit: 8).

## Complexity: `brewing/Brewer.js::Brewer.ready`

Files:
- `brewing/Brewer.js:50`

Findings:
- Decision nesting depth is 4 (limit: 3).

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.js`
- `reporting/Report.js`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.js → reporting/Report.js → brewing/Recipe.js.
