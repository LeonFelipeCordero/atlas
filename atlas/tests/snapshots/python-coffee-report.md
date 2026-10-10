# Metrics

- files: 3
- modules: 5
- types: 4
- callables: 15
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `src/coffee/brewing/brewer.py` | `src/coffee/brewing/brewer.py` | 601 | 9 | 9 | 33 |
| `src/coffee/brewing/recipe.py` | `src/coffee/brewing/recipe.py` | 21 | 3 | 3 | 5 |
| `src/coffee/reporting/report.py` | `src/coffee/reporting/report.py` | 16 | 3 | 3 | 5 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `src/coffee/brewing/brewer.py::Brewing.brew` | `src/coffee/brewing/brewer.py:23` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/brewer.py::Brewer.brew` | `src/coffee/brewing/brewer.py:28` | 5 | 1 | 4 | 4 | 0 | 0 | 1 |
| `src/coffee/brewing/brewer.py::Brewer.retry` | `src/coffee/brewing/brewer.py:34` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/brewing/brewer.py::Brewer.score` | `src/coffee/brewing/brewer.py:39` | 8 | 1 | 5 | 7 | 1 | 1 | 3 |
| `src/coffee/brewing/brewer.py::Brewer.classify` | `src/coffee/brewing/brewer.py:49` | 19 | 1 | 9 | 9 | 0 | 0 | 1 |
| `src/coffee/brewing/brewer.py::Brewer.ready` | `src/coffee/brewing/brewer.py:70` | 7 | 4 | 5 | 7 | 2 | 0 | 4 |
| `src/coffee/brewing/brewer.py::Brewer.calibrate` | `src/coffee/brewing/brewer.py:79` | 105 | 8 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/brewer.py::import_styles` | `src/coffee/brewing/brewer.py:186` | 11 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/brewer.py::main` | `src/coffee/brewing/brewer.py:199` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/recipe.py::Recipe.portions` | `src/coffee/brewing/recipe.py:3` | 8 | 1 | 3 | 3 | 0 | 0 | 1 |
| `src/coffee/brewing/recipe.py::Recipe.preview` | `src/coffee/brewing/recipe.py:13` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/recipe.py::portions` | `src/coffee/brewing/recipe.py:20` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/reporting/report.py::Report.total` | `src/coffee/reporting/report.py:6` | 2 | 1 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/reporting/report.py::Report.render` | `src/coffee/reporting/report.py:10` | 3 | 1 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/reporting/report.py::render` | `src/coffee/reporting/report.py:15` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `python` | `.` | 0 | 0 | 0 | N/A |
| `src` | `src` | 0 | 0 | 0 | N/A |
| `src.coffee` | `src/coffee` | 0 | 0 | 0 | N/A |
| `src.coffee.brewing` | `src/coffee/brewing` | 1 | 1 | 1 | 0.50 |
| `src/coffee/brewing/brewer.py` | `src/coffee/brewing/brewer.py` | 0 | 2 | 0 | 1.00 |
| `src/coffee/brewing/brewer.py::Brewing` | `src/coffee/brewing/brewer.py:21` | 1 | 0 | 1 | 0.00 |
| `src/coffee/brewing/brewer.py::Brewing.brew` | `src/coffee/brewing/brewer.py:23` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::Brewer` | `src/coffee/brewing/brewer.py:27` | 0 | 3 | 0 | 1.00 |
| `src/coffee/brewing/brewer.py::Brewer.brew` | `src/coffee/brewing/brewer.py:28` | 1 | 2 | 1 | 0.67 |
| `src/coffee/brewing/brewer.py::Brewer.retry` | `src/coffee/brewing/brewer.py:34` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::Brewer.score` | `src/coffee/brewing/brewer.py:39` | 0 | 1 | 0 | 1.00 |
| `src/coffee/brewing/brewer.py::Brewer.classify` | `src/coffee/brewing/brewer.py:49` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::Brewer.ready` | `src/coffee/brewing/brewer.py:70` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::Brewer.calibrate` | `src/coffee/brewing/brewer.py:79` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::import_styles` | `src/coffee/brewing/brewer.py:186` | 1 | 2 | 1 | 0.67 |
| `src/coffee/brewing/brewer.py::main` | `src/coffee/brewing/brewer.py:199` | 0 | 2 | 0 | 1.00 |
| `src/coffee/brewing/recipe.py` | `src/coffee/brewing/recipe.py` | 2 | 1 | 2 | 0.33 |
| `src/coffee/brewing/recipe.py::Recipe` | `src/coffee/brewing/recipe.py:1` | 2 | 1 | 2 | 0.33 |
| `src/coffee/brewing/recipe.py::Recipe.portions` | `src/coffee/brewing/recipe.py:3` | 5 | 0 | 9 | 0.00 |
| `src/coffee/brewing/recipe.py::Recipe.preview` | `src/coffee/brewing/recipe.py:13` | 0 | 1 | 0 | 1.00 |
| `src/coffee/brewing/recipe.py::portions` | `src/coffee/brewing/recipe.py:20` | 1 | 1 | 2 | 0.50 |
| `src.coffee.reporting` | `src/coffee/reporting` | 1 | 1 | 1 | 0.50 |
| `src/coffee/reporting/report.py` | `src/coffee/reporting/report.py` | 2 | 1 | 2 | 0.33 |
| `src/coffee/reporting/report.py::Report` | `src/coffee/reporting/report.py:4` | 2 | 1 | 2 | 0.33 |
| `src/coffee/reporting/report.py::Report.total` | `src/coffee/reporting/report.py:6` | 1 | 1 | 6 | 0.50 |
| `src/coffee/reporting/report.py::Report.render` | `src/coffee/reporting/report.py:10` | 3 | 2 | 5 | 0.40 |
| `src/coffee/reporting/report.py::render` | `src/coffee/reporting/report.py:15` | 1 | 1 | 2 | 0.50 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `src/coffee/brewing/recipe.py`
- `src/coffee/reporting/report.py`

Example cycle: `src/coffee/brewing/recipe.py` → `src/coffee/reporting/report.py` → `src/coffee/brewing/recipe.py`
