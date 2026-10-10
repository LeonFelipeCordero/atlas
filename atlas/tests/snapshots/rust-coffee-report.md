# Metrics

- files: 3
- modules: 5
- types: 0
- callables: 14
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/brewer.rs` | `brewing/brewer.rs` | 601 | 8 | 8 | 30 |
| `brewing/recipe.rs` | `brewing/recipe.rs` | 13 | 2 | 2 | 4 |
| `reporting/report.rs` | `reporting/report.rs` | 12 | 4 | 4 | 4 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/brewer.rs::brew` | `brewing/brewer.rs:6` | 8 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/brewer.rs::brew.<anonymous>` | `brewing/brewer.rs:11` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.rs::retry` | `brewing/brewer.rs:15` | 6 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/brewer.rs::score` | `brewing/brewer.rs:22` | 12 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/brewer.rs::classify` | `brewing/brewer.rs:36` | 12 | 1 | 9 | 9 | 0 | 0 | 1 |
| `brewing/brewer.rs::ready` | `brewing/brewer.rs:50` | 12 | 4 | 5 | 7 | 2 | 0 | 4 |
| `brewing/brewer.rs::calibrate` | `brewing/brewer.rs:64` | 104 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.rs::main` | `brewing/brewer.rs:169` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.rs::portions` | `brewing/recipe.rs:3` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/recipe.rs::preview` | `brewing/recipe.rs:11` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::total` | `reporting/report.rs:3` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::total.<anonymous>` | `reporting/report.rs:4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::render` | `reporting/report.rs:7` | 6 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::render.<anonymous>` | `reporting/report.rs:9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `rust` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 1 | 1 | 1 | 0.50 |
| `brewing/brewer.rs` | `brewing/brewer.rs` | 0 | 2 | 0 | 1.00 |
| `brewing/brewer.rs::recipe` | `brewing/brewer.rs:2` | 0 | 0 | 0 | N/A |
| `brewing/brewer.rs::report` | `brewing/brewer.rs:4` | 0 | 0 | 0 | N/A |
| `brewing/brewer.rs::brew` | `brewing/brewer.rs:6` | 1 | 1 | 1 | 0.50 |
| `brewing/brewer.rs::brew.<anonymous>` | `brewing/brewer.rs:11` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.rs::retry` | `brewing/brewer.rs:15` | 0 | 0 | 0 | N/A |
| `brewing/brewer.rs::score` | `brewing/brewer.rs:22` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.rs::classify` | `brewing/brewer.rs:36` | 0 | 0 | 0 | N/A |
| `brewing/brewer.rs::ready` | `brewing/brewer.rs:50` | 0 | 0 | 0 | N/A |
| `brewing/brewer.rs::calibrate` | `brewing/brewer.rs:64` | 0 | 0 | 0 | N/A |
| `brewing/brewer.rs::main` | `brewing/brewer.rs:169` | 0 | 1 | 0 | 1.00 |
| `brewing/recipe.rs` | `brewing/recipe.rs` | 2 | 1 | 2 | 0.33 |
| `brewing/recipe.rs::portions` | `brewing/recipe.rs:3` | 4 | 0 | 4 | 0.00 |
| `brewing/recipe.rs::preview` | `brewing/recipe.rs:11` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 1 | 1 | 1 | 0.50 |
| `reporting/report.rs` | `reporting/report.rs` | 2 | 1 | 2 | 0.33 |
| `reporting/report.rs::total` | `reporting/report.rs:3` | 1 | 0 | 4 | 0.00 |
| `reporting/report.rs::total.<anonymous>` | `reporting/report.rs:4` | 0 | 1 | 0 | 1.00 |
| `reporting/report.rs::render` | `reporting/report.rs:7` | 2 | 1 | 3 | 0.33 |
| `reporting/report.rs::render.<anonymous>` | `reporting/report.rs:9` | 0 | 1 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/recipe.rs`
- `reporting/report.rs`

Example cycle: `brewing/recipe.rs` → `reporting/report.rs` → `brewing/recipe.rs`
