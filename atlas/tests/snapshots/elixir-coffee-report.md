# Metrics

- files: 3
- modules: 6
- types: 0
- callables: 18
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/brewer.ex` | `brewing/brewer.ex` | 601 | 12 | 12 | 29 |
| `brewing/recipe.ex` | `brewing/recipe.ex` | 13 | 2 | 2 | 4 |
| `reporting/report.ex` | `reporting/report.ex` | 10 | 4 | 4 | 4 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew` | `brewing/brewer.ex:5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew` | `brewing/brewer.ex:7` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew.<anonymous>` | `brewing/brewer.ex:8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.retry` | `brewing/brewer.ex:11` | 1 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.retry` | `brewing/brewer.ex:12` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score` | `brewing/brewer.ex:14` | 12 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score.<anonymous>` | `brewing/brewer.ex:15` | 10 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score.<anonymous>.<anonymous>` | `brewing/brewer.ex:16` | 8 | 2 | 3 | 3 | 0 | 0 | 1 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.classify` | `brewing/brewer.ex:28` | 12 | 1 | 9 | 9 | 0 | 0 | 1 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.ready` | `brewing/brewer.ex:42` | 19 | 4 | 5 | 7 | 2 | 0 | 4 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.calibrate` | `brewing/brewer.ex:63` | 104 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.main` | `brewing/brewer.ex:168` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.portions` | `brewing/recipe.ex:4` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.preview` | `brewing/recipe.ex:12` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.total.<anonymous>` | `reporting/report.ex:4` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.total` | `reporting/report.ex:4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.render` | `reporting/report.ex:6` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.render.<anonymous>` | `reporting/report.ex:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `elixir` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 0 | 2 | 0 | 1.00 |
| `brewing/brewer.ex` | `brewing/brewer.ex` | 0 | 2 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer` | `brewing/brewer.ex:1` | 0 | 2 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew` | `brewing/brewer.ex:5` | 1 | 1 | 1 | 0.50 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew` | `brewing/brewer.ex:7` | 1 | 1 | 1 | 0.50 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew.<anonymous>` | `brewing/brewer.ex:8` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.retry` | `brewing/brewer.ex:11` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.retry` | `brewing/brewer.ex:12` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score` | `brewing/brewer.ex:14` | 0 | 0 | 0 | N/A |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score.<anonymous>` | `brewing/brewer.ex:15` | 0 | 0 | 0 | N/A |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score.<anonymous>.<anonymous>` | `brewing/brewer.ex:16` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.classify` | `brewing/brewer.ex:28` | 0 | 0 | 0 | N/A |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.ready` | `brewing/brewer.ex:42` | 0 | 0 | 0 | N/A |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.calibrate` | `brewing/brewer.ex:63` | 0 | 0 | 0 | N/A |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.main` | `brewing/brewer.ex:168` | 0 | 2 | 0 | 1.00 |
| `brewing/recipe.ex` | `brewing/recipe.ex` | 2 | 1 | 2 | 0.33 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe` | `brewing/recipe.ex:1` | 4 | 1 | 4 | 0.20 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.portions` | `brewing/recipe.ex:4` | 4 | 0 | 4 | 0.00 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.preview` | `brewing/recipe.ex:12` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 0 | 1 | 0 | 1.00 |
| `reporting/report.ex` | `reporting/report.ex` | 2 | 1 | 2 | 0.33 |
| `reporting/report.ex::Coffee.Reporting.Report` | `reporting/report.ex:1` | 3 | 1 | 4 | 0.25 |
| `reporting/report.ex::Coffee.Reporting.Report.total.<anonymous>` | `reporting/report.ex:4` | 0 | 1 | 0 | 1.00 |
| `reporting/report.ex::Coffee.Reporting.Report.total` | `reporting/report.ex:4` | 1 | 0 | 5 | 0.00 |
| `reporting/report.ex::Coffee.Reporting.Report.render` | `reporting/report.ex:6` | 3 | 1 | 4 | 0.25 |
| `reporting/report.ex::Coffee.Reporting.Report.render.<anonymous>` | `reporting/report.ex:7` | 0 | 1 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/recipe.ex`
- `reporting/report.ex`

Example cycle: `brewing/recipe.ex` → `reporting/report.ex` → `brewing/recipe.ex`
