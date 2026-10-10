# Metrics

- files: 3
- modules: 3
- types: 4
- callables: 15
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.js` | `brewing/Brewer.js` | 601 | 9 | 9 | 31 |
| `brewing/Recipe.js` | `brewing/Recipe.js` | 15 | 2 | 2 | 4 |
| `reporting/Report.js` | `reporting/Report.js` | 12 | 4 | 4 | 4 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.js::Brewing.brew` | `brewing/Brewer.js:6` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.js::Brewer.brew` | `brewing/Brewer.js:12` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.js::Brewer.brew.<anonymous>` | `brewing/Brewer.js:14` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.js::Brewer.retry` | `brewing/Brewer.js:17` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.js::Brewer.score` | `brewing/Brewer.js:22` | 12 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/Brewer.js::Brewer.classify` | `brewing/Brewer.js:36` | 12 | 1 | 9 | 9 | 0 | 0 | 1 |
| `brewing/Brewer.js::Brewer.ready` | `brewing/Brewer.js:50` | 12 | 4 | 5 | 7 | 2 | 0 | 4 |
| `brewing/Brewer.js::Brewer.calibrate` | `brewing/Brewer.js:63` | 104 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.js::main` | `brewing/Brewer.js:169` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.js::Recipe.portions` | `brewing/Recipe.js:4` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/Recipe.js::Recipe.preview` | `brewing/Recipe.js:12` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.js::Report.total` | `reporting/Report.js:4` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.js::Report.total.<anonymous>` | `reporting/Report.js:5` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.js::Report.render` | `reporting/Report.js:8` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.js::Report.render.<anonymous>` | `reporting/Report.js:9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `javascript` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 1 | 1 | 1 | 0.50 |
| `brewing/Brewer.js` | `brewing/Brewer.js` | 0 | 2 | 0 | 1.00 |
| `brewing/Brewer.js::Brewing` | `brewing/Brewer.js:5` | 1 | 0 | 1 | 0.00 |
| `brewing/Brewer.js::Brewing.brew` | `brewing/Brewer.js:6` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::Brewer` | `brewing/Brewer.js:11` | 0 | 3 | 0 | 1.00 |
| `brewing/Brewer.js::Brewer.brew` | `brewing/Brewer.js:12` | 1 | 1 | 1 | 0.50 |
| `brewing/Brewer.js::Brewer.brew.<anonymous>` | `brewing/Brewer.js:14` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.js::Brewer.retry` | `brewing/Brewer.js:17` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::Brewer.score` | `brewing/Brewer.js:22` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.js::Brewer.classify` | `brewing/Brewer.js:36` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::Brewer.ready` | `brewing/Brewer.js:50` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::Brewer.calibrate` | `brewing/Brewer.js:63` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::main` | `brewing/Brewer.js:169` | 0 | 1 | 0 | 1.00 |
| `brewing/Recipe.js` | `brewing/Recipe.js` | 2 | 1 | 2 | 0.33 |
| `brewing/Recipe.js::Recipe` | `brewing/Recipe.js:3` | 2 | 1 | 2 | 0.33 |
| `brewing/Recipe.js::Recipe.portions` | `brewing/Recipe.js:4` | 4 | 0 | 4 | 0.00 |
| `brewing/Recipe.js::Recipe.preview` | `brewing/Recipe.js:12` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 1 | 1 | 1 | 0.50 |
| `reporting/Report.js` | `reporting/Report.js` | 2 | 1 | 2 | 0.33 |
| `reporting/Report.js::Report` | `reporting/Report.js:3` | 2 | 1 | 2 | 0.33 |
| `reporting/Report.js::Report.total` | `reporting/Report.js:4` | 1 | 0 | 4 | 0.00 |
| `reporting/Report.js::Report.total.<anonymous>` | `reporting/Report.js:5` | 0 | 1 | 0 | 1.00 |
| `reporting/Report.js::Report.render` | `reporting/Report.js:8` | 2 | 1 | 3 | 0.33 |
| `reporting/Report.js::Report.render.<anonymous>` | `reporting/Report.js:9` | 0 | 1 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/Recipe.js`
- `reporting/Report.js`

Example cycle: `brewing/Recipe.js` → `reporting/Report.js` → `brewing/Recipe.js`
