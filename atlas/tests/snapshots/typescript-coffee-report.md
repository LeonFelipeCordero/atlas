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
| `brewing/Brewer.ts` | `brewing/Brewer.ts` | 601 | 9 | 9 | 31 |
| `brewing/Recipe.ts` | `brewing/Recipe.ts` | 15 | 2 | 2 | 4 |
| `reporting/Report.ts` | `reporting/Report.ts` | 12 | 4 | 4 | 4 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.ts::Brewing.brew` | `brewing/Brewer.ts:6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.ts::Brewer.brew` | `brewing/Brewer.ts:10` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.ts::Brewer.brew.<anonymous>` | `brewing/Brewer.ts:12` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.ts::Brewer.retry` | `brewing/Brewer.ts:15` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.ts::Brewer.score` | `brewing/Brewer.ts:20` | 12 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/Brewer.ts::Brewer.classify` | `brewing/Brewer.ts:34` | 12 | 1 | 9 | 9 | 0 | 0 | 1 |
| `brewing/Brewer.ts::Brewer.ready` | `brewing/Brewer.ts:48` | 12 | 4 | 5 | 7 | 2 | 0 | 4 |
| `brewing/Brewer.ts::Brewer.calibrate` | `brewing/Brewer.ts:61` | 104 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.ts::main` | `brewing/Brewer.ts:167` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.ts::Recipe.portions` | `brewing/Recipe.ts:4` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/Recipe.ts::Recipe.preview` | `brewing/Recipe.ts:12` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.ts::Report.total` | `reporting/Report.ts:4` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.ts::Report.total.<anonymous>` | `reporting/Report.ts:5` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.ts::Report.render` | `reporting/Report.ts:8` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.ts::Report.render.<anonymous>` | `reporting/Report.ts:9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `typescript` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 1 | 1 | 1 | 0.50 |
| `brewing/Brewer.ts` | `brewing/Brewer.ts` | 0 | 2 | 0 | 1.00 |
| `brewing/Brewer.ts::Brewing` | `brewing/Brewer.ts:5` | 1 | 0 | 1 | 0.00 |
| `brewing/Brewer.ts::Brewing.brew` | `brewing/Brewer.ts:6` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::Brewer` | `brewing/Brewer.ts:9` | 0 | 3 | 0 | 1.00 |
| `brewing/Brewer.ts::Brewer.brew` | `brewing/Brewer.ts:10` | 1 | 1 | 1 | 0.50 |
| `brewing/Brewer.ts::Brewer.brew.<anonymous>` | `brewing/Brewer.ts:12` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.ts::Brewer.retry` | `brewing/Brewer.ts:15` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::Brewer.score` | `brewing/Brewer.ts:20` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.ts::Brewer.classify` | `brewing/Brewer.ts:34` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::Brewer.ready` | `brewing/Brewer.ts:48` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::Brewer.calibrate` | `brewing/Brewer.ts:61` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::main` | `brewing/Brewer.ts:167` | 0 | 1 | 0 | 1.00 |
| `brewing/Recipe.ts` | `brewing/Recipe.ts` | 2 | 1 | 2 | 0.33 |
| `brewing/Recipe.ts::Recipe` | `brewing/Recipe.ts:3` | 2 | 1 | 2 | 0.33 |
| `brewing/Recipe.ts::Recipe.portions` | `brewing/Recipe.ts:4` | 4 | 0 | 4 | 0.00 |
| `brewing/Recipe.ts::Recipe.preview` | `brewing/Recipe.ts:12` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 1 | 1 | 1 | 0.50 |
| `reporting/Report.ts` | `reporting/Report.ts` | 2 | 1 | 2 | 0.33 |
| `reporting/Report.ts::Report` | `reporting/Report.ts:3` | 2 | 1 | 2 | 0.33 |
| `reporting/Report.ts::Report.total` | `reporting/Report.ts:4` | 1 | 0 | 4 | 0.00 |
| `reporting/Report.ts::Report.total.<anonymous>` | `reporting/Report.ts:5` | 0 | 1 | 0 | 1.00 |
| `reporting/Report.ts::Report.render` | `reporting/Report.ts:8` | 2 | 1 | 3 | 0.33 |
| `reporting/Report.ts::Report.render.<anonymous>` | `reporting/Report.ts:9` | 0 | 1 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/Recipe.ts`
- `reporting/Report.ts`

Example cycle: `brewing/Recipe.ts` → `reporting/Report.ts` → `brewing/Recipe.ts`
