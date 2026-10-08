## Complexity: `src/coffee/brewing/brewer.py::Brewer.score`

Files:
- `src/coffee/brewing/brewer.py:39`

Findings:
- Nested-loop count is 1 (limit: 0).

## Circular dependency: `Circular imports`

Files:
- `src/coffee/brewing/recipe.py`
- `src/coffee/reporting/report.py`

Findings:
- These files form a circular import dependency.
- Example cycle: src/coffee/brewing/recipe.py → src/coffee/reporting/report.py → src/coffee/brewing/recipe.py.
