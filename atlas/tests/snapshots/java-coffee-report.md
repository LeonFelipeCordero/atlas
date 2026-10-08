## Complexity: `brewing/Brewer.java::Brewer.score`

Files:
- `brewing/Brewer.java:24`

Findings:
- Nested-loop count is 1 (limit: 0).

## Complexity: `brewing/Brewer.java::Brewer.classify`

Files:
- `brewing/Brewer.java:38`

Findings:
- Cyclomatic complexity is 9 (limit: 8).

## Complexity: `brewing/Brewer.java::Brewer.ready`

Files:
- `brewing/Brewer.java:52`

Findings:
- Decision nesting depth is 4 (limit: 3).

## Circular dependency: `Circular imports`

Files:
- `brewing/Recipe.java`
- `reporting/Report.java`

Findings:
- These files form a circular import dependency.
- Example cycle: brewing/Recipe.java → reporting/Report.java → brewing/Recipe.java.
