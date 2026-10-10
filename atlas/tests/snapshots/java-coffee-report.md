# Metrics

- files: 3
- modules: 6
- types: 4
- callables: 16
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.java` | `brewing/Brewer.java` | 601 | 9 | 9 | 31 |
| `brewing/Recipe.java` | `brewing/Recipe.java` | 20 | 2 | 2 | 4 |
| `reporting/Report.java` | `reporting/Report.java` | 20 | 3 | 3 | 3 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.java::Brewing.brew` | `brewing/Brewer.java:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.java::Brewer.brew` | `brewing/Brewer.java:11` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.java::Brewer.brew.<anonymous>` | `brewing/Brewer.java:15` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.java::Brewer.retry` | `brewing/Brewer.java:19` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.java::Brewer.score` | `brewing/Brewer.java:24` | 12 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/Brewer.java::Brewer.classify` | `brewing/Brewer.java:38` | 12 | 1 | 9 | 9 | 0 | 0 | 1 |
| `brewing/Brewer.java::Brewer.ready` | `brewing/Brewer.java:52` | 12 | 4 | 5 | 7 | 2 | 0 | 4 |
| `brewing/Brewer.java::Brewer.calibrate` | `brewing/Brewer.java:66` | 104 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.java::Brewer.main` | `brewing/Brewer.java:171` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.java::Recipe.portions` | `brewing/Recipe.java:9` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/Recipe.java::Recipe.preview` | `brewing/Recipe.java:17` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.java::Report.total` | `reporting/Report.java:10` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.java::Report.render` | `reporting/Report.java:14` | 6 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.java::Report.render.<anonymous>` | `reporting/Report.java:16` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `java` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 1 | 1 | 1 | 0.50 |
| `brewing/Brewer.java` | `brewing/Brewer.java` | 0 | 2 | 0 | 1.00 |
| `brewing/Brewer.java::coffee.brewing` | `brewing/Brewer.java:1` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewing` | `brewing/Brewer.java:6` | 1 | 0 | 1 | 0.00 |
| `brewing/Brewer.java::Brewing.brew` | `brewing/Brewer.java:7` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer` | `brewing/Brewer.java:10` | 0 | 3 | 0 | 1.00 |
| `brewing/Brewer.java::Brewer.brew` | `brewing/Brewer.java:11` | 1 | 1 | 1 | 0.50 |
| `brewing/Brewer.java::Brewer.brew.<anonymous>` | `brewing/Brewer.java:15` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.java::Brewer.retry` | `brewing/Brewer.java:19` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer.score` | `brewing/Brewer.java:24` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.java::Brewer.classify` | `brewing/Brewer.java:38` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer.ready` | `brewing/Brewer.java:52` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer.calibrate` | `brewing/Brewer.java:66` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer.main` | `brewing/Brewer.java:171` | 0 | 1 | 0 | 1.00 |
| `brewing/Recipe.java` | `brewing/Recipe.java` | 2 | 1 | 2 | 0.33 |
| `brewing/Recipe.java::coffee.brewing` | `brewing/Recipe.java:1` | 0 | 0 | 0 | N/A |
| `brewing/Recipe.java::Recipe` | `brewing/Recipe.java:6` | 2 | 1 | 2 | 0.33 |
| `brewing/Recipe.java::Recipe.Recipe` | `brewing/Recipe.java:7` | 0 | 0 | 0 | N/A |
| `brewing/Recipe.java::Recipe.portions` | `brewing/Recipe.java:9` | 4 | 0 | 8 | 0.00 |
| `brewing/Recipe.java::Recipe.preview` | `brewing/Recipe.java:17` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 1 | 1 | 1 | 0.50 |
| `reporting/Report.java` | `reporting/Report.java` | 2 | 1 | 2 | 0.33 |
| `reporting/Report.java::coffee.reporting` | `reporting/Report.java:1` | 0 | 0 | 0 | N/A |
| `reporting/Report.java::Report` | `reporting/Report.java:7` | 2 | 1 | 2 | 0.33 |
| `reporting/Report.java::Report.Report` | `reporting/Report.java:8` | 0 | 0 | 0 | N/A |
| `reporting/Report.java::Report.total` | `reporting/Report.java:10` | 1 | 1 | 4 | 0.50 |
| `reporting/Report.java::Report.render` | `reporting/Report.java:14` | 2 | 1 | 3 | 0.33 |
| `reporting/Report.java::Report.render.<anonymous>` | `reporting/Report.java:16` | 0 | 1 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/Recipe.java`
- `reporting/Report.java`

Example cycle: `brewing/Recipe.java` → `reporting/Report.java` → `brewing/Recipe.java`
