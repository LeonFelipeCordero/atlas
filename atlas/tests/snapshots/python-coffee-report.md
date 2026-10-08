## Complexity: `src/coffee/brewing/brewer.py::Brewer.score`

Files:
- `src/coffee/brewing/brewer.py:39`

Findings:
- Nested-loop count is 1 (limit: 0).

## Complexity: `src/coffee/brewing/brewer.py::Brewer.classify`

Files:
- `src/coffee/brewing/brewer.py:49`

Findings:
- Cyclomatic complexity is 9 (limit: 8).

## Complexity: `src/coffee/brewing/brewer.py::Brewer.ready`

Files:
- `src/coffee/brewing/brewer.py:70`

Findings:
- Decision nesting depth is 4 (limit: 3).

## Circular dependency: `Circular imports`

Files:
- `src/coffee/brewing/recipe.py`
- `src/coffee/reporting/report.py`

Findings:
- These files form a circular import dependency.
- Example cycle: src/coffee/brewing/recipe.py → src/coffee/reporting/report.py → src/coffee/brewing/recipe.py.
