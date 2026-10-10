# Metrics

- files: 3
- modules: 6
- types: 2
- callables: 14
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.kt` | `brewing/Brewer.kt` | 601 | 9 | 9 | 31 |
| `brewing/Recipe.kt` | `brewing/Recipe.kt` | 11 | 2 | 2 | 4 |
| `reporting/Report.kt` | `reporting/Report.kt` | 9 | 3 | 3 | 3 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.kt::CoffeeMaker.brew` | `brewing/Brewer.kt:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.kt::Brewer.brew` | `brewing/Brewer.kt:11` | 5 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.kt::Brewer.brew.<anonymous>` | `brewing/Brewer.kt:13` | 1 | N/A | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.kt::Brewer.retry` | `brewing/Brewer.kt:17` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.kt::Brewer.score` | `brewing/Brewer.kt:22` | 10 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/Brewer.kt::Brewer.classify` | `brewing/Brewer.kt:34` | 12 | 1 | 9 | 9 | 0 | 0 | 1 |
| `brewing/Brewer.kt::Brewer.ready` | `brewing/Brewer.kt:48` | 12 | 4 | 5 | 7 | 2 | 0 | 4 |
| `brewing/Brewer.kt::Brewer.calibrate` | `brewing/Brewer.kt:61` | 104 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.kt::main` | `brewing/Brewer.kt:167` | 4 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.kt::portions` | `brewing/Recipe.kt:5` | 5 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/Recipe.kt::preview` | `brewing/Recipe.kt:11` | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.kt::render` | `reporting/Report.kt:5` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.kt::render.<anonymous>` | `reporting/Report.kt:6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.kt::render.<anonymous>` | `reporting/Report.kt:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `kotlin` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 1 | 1 | 1 | 0.50 |
| `brewing/Brewer.kt` | `brewing/Brewer.kt` | 0 | 2 | 0 | 1.00 |
| `brewing/Brewer.kt::coffee.brewing` | `brewing/Brewer.kt:1` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::CoffeeMaker` | `brewing/Brewer.kt:6` | 1 | 0 | 1 | 0.00 |
| `brewing/Brewer.kt::CoffeeMaker.brew` | `brewing/Brewer.kt:7` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::Brewer` | `brewing/Brewer.kt:10` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.kt::Brewer.brew` | `brewing/Brewer.kt:11` | 1 | 1 | 1 | 0.50 |
| `brewing/Brewer.kt::Brewer.brew.<anonymous>` | `brewing/Brewer.kt:13` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.kt::Brewer.retry` | `brewing/Brewer.kt:17` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::Brewer.score` | `brewing/Brewer.kt:22` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.kt::Brewer.classify` | `brewing/Brewer.kt:34` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::Brewer.ready` | `brewing/Brewer.kt:48` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::Brewer.calibrate` | `brewing/Brewer.kt:61` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::main` | `brewing/Brewer.kt:167` | 0 | 1 | 0 | 1.00 |
| `brewing/Recipe.kt` | `brewing/Recipe.kt` | 2 | 1 | 2 | 0.33 |
| `brewing/Recipe.kt::coffee.brewing` | `brewing/Recipe.kt:1` | 0 | 0 | 0 | N/A |
| `brewing/Recipe.kt::portions` | `brewing/Recipe.kt:5` | 4 | 0 | 4 | 0.00 |
| `brewing/Recipe.kt::preview` | `brewing/Recipe.kt:11` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 1 | 1 | 1 | 0.50 |
| `reporting/Report.kt` | `reporting/Report.kt` | 2 | 1 | 2 | 0.33 |
| `reporting/Report.kt::coffee.reporting` | `reporting/Report.kt:1` | 0 | 0 | 0 | N/A |
| `reporting/Report.kt::render` | `reporting/Report.kt:5` | 2 | 0 | 3 | 0.00 |
| `reporting/Report.kt::render.<anonymous>` | `reporting/Report.kt:6` | 0 | 1 | 0 | 1.00 |
| `reporting/Report.kt::render.<anonymous>` | `reporting/Report.kt:7` | 0 | 1 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/Recipe.kt`
- `reporting/Report.kt`

Example cycle: `brewing/Recipe.kt` → `reporting/Report.kt` → `brewing/Recipe.kt`
