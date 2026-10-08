## Complexity: `brewing/Brewer.js::Brewer.score`

Files:
- `brewing/Brewer.js:22`

Findings:
- Nested-loop count is 1 (limit: 0).

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.js`
- `reporting/Report.js`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.js → reporting/Report.js → brewing/Recipe.js.
