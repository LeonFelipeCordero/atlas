# Metrics

- files: 3
- modules: 3
- types: 0
- callables: 12
- circularImportGroups: 0
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/brewer.go` | `brewing/brewer.go` | 601 | 8 | 8 | 32 |
| `brewing/recipe.go` | `brewing/recipe.go` | 18 | 2 | 2 | 4 |
| `reporting/report.go` | `reporting/report.go` | 22 | 2 | 2 | 4 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/brewer.go::brew` | `brewing/brewer.go:5` | 13 | 1 | 4 | 4 | 0 | 0 | 2 |
| `brewing/brewer.go::brew.accept` | `brewing/brewer.go:10` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.go::retry` | `brewing/brewer.go:19` | 6 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/brewer.go::score` | `brewing/brewer.go:26` | 12 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/brewer.go::classify` | `brewing/brewer.go:40` | 12 | 1 | 9 | 9 | 0 | 0 | 1 |
| `brewing/brewer.go::ready` | `brewing/brewer.go:54` | 12 | 4 | 5 | 7 | 2 | 0 | 4 |
| `brewing/brewer.go::calibrate` | `brewing/brewer.go:68` | 104 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.go::Main` | `brewing/brewer.go:174` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.go::portions` | `brewing/recipe.go:5` | 10 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/recipe.go::preview` | `brewing/recipe.go:16` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.go::total` | `reporting/report.go:8` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `reporting/report.go::render` | `reporting/report.go:16` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `go` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 1 | 1 | 1 | 0.50 |
| `brewing/brewer.go` | `brewing/brewer.go` | 0 | 2 | 0 | 1.00 |
| `brewing/brewer.go::brew` | `brewing/brewer.go:5` | 1 | 2 | 1 | 0.67 |
| `brewing/brewer.go::brew.accept` | `brewing/brewer.go:10` | 1 | 1 | 2 | 0.50 |
| `brewing/brewer.go::retry` | `brewing/brewer.go:19` | 0 | 0 | 0 | N/A |
| `brewing/brewer.go::score` | `brewing/brewer.go:26` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.go::classify` | `brewing/brewer.go:40` | 0 | 0 | 0 | N/A |
| `brewing/brewer.go::ready` | `brewing/brewer.go:54` | 0 | 0 | 0 | N/A |
| `brewing/brewer.go::calibrate` | `brewing/brewer.go:68` | 0 | 0 | 0 | N/A |
| `brewing/brewer.go::Main` | `brewing/brewer.go:174` | 0 | 1 | 0 | 1.00 |
| `brewing/recipe.go` | `brewing/recipe.go` | 2 | 1 | 2 | 0.33 |
| `brewing/recipe.go::portions` | `brewing/recipe.go:5` | 4 | 0 | 7 | 0.00 |
| `brewing/recipe.go::preview` | `brewing/recipe.go:16` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 1 | 1 | 1 | 0.50 |
| `reporting/report.go` | `reporting/report.go` | 2 | 1 | 2 | 0.33 |
| `reporting/report.go::total` | `reporting/report.go:8` | 1 | 1 | 4 | 0.50 |
| `reporting/report.go::render` | `reporting/report.go:16` | 2 | 2 | 3 | 0.50 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.
