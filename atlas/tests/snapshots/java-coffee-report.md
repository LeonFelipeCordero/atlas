## Complexity: `brewing/Brewer.java::Brewer.score`

Files:
- `brewing/Brewer.java:24`

Findings:
- Nested-loop count is 1 (limit: 0).

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.java`
- `reporting/Report.java`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.java → reporting/Report.java → brewing/Recipe.java.
