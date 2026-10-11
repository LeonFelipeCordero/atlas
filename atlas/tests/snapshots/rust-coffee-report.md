# Metrics

- files: 9
- modules: 12
- types: 5
- callables: 38
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `Cargo.toml` | `Cargo.toml` | 8 | 0 | 0 | 0 |
| `brewing/brewer.rs` | `brewing/brewer.rs` | 89 | 10 | 10 | 27 |
| `brewing/inventory.rs` | `brewing/inventory.rs` | 42 | 9 | 9 | 11 |
| `brewing/mod.rs` | `brewing/mod.rs` | 3 | 0 | 0 | 0 |
| `brewing/recipe.rs` | `brewing/recipe.rs` | 40 | 6 | 6 | 8 |
| `main.rs` | `main.rs` | 38 | 2 | 2 | 2 |
| `reporting/daily/totals.rs` | `reporting/daily/totals.rs` | 5 | 1 | 1 | 1 |
| `reporting/mod.rs` | `reporting/mod.rs` | 19 | 1 | 1 | 1 |
| `reporting/report.rs` | `reporting/report.rs` | 37 | 9 | 9 | 9 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/brewer.rs::Brewer.new` | `brewing/brewer.rs:11` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.rs::Brewer.brew` | `brewing/brewer.rs:15` | 9 | 1 | 3 | 3 | 0 | 0 | 2 |
| `brewing/brewer.rs::Brewer.remaining` | `brewing/brewer.rs:25` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.rs::brew` | `brewing/brewer.rs:30` | 11 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/brewer.rs::brew.<anonymous>` | `brewing/brewer.rs:37` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.rs::retry` | `brewing/brewer.rs:42` | 6 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/brewer.rs::score` | `brewing/brewer.rs:49` | 12 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/brewer.rs::classify` | `brewing/brewer.rs:62` | 8 | 1 | 4 | 4 | 0 | 0 | 1 |
| `brewing/brewer.rs::ready` | `brewing/brewer.rs:71` | 3 | 4 | 5 | 5 | 0 | 0 | 0 |
| `brewing/brewer.rs::calibrate` | `brewing/brewer.rs:76` | 14 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.rs::<anonymous>` | `brewing/inventory.rs:5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.rs::Inventory.new` | `brewing/inventory.rs:12` | 7 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.rs::Inventory.new.<anonymous>` | `brewing/inventory.rs:15` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.rs::Inventory.remaining` | `brewing/inventory.rs:20` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.rs::Inventory.reserve` | `brewing/inventory.rs:24` | 8 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/inventory.rs::Inventory.restock` | `brewing/inventory.rs:33` | 9 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.rs::Inventory.restock.<anonymous>` | `brewing/inventory.rs:34` | 7 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.rs::Inventory.restock.<anonymous>.adjusted_units` | `brewing/inventory.rs:35` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.rs::Inventory.restock.<anonymous>.<anonymous>` | `brewing/inventory.rs:38` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.rs::Recipe.new` | `brewing/recipe.rs:10` | 6 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.rs::Recipe.portions` | `brewing/recipe.rs:17` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.rs::Recipe.scale` | `brewing/recipe.rs:21` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.rs::Recipe.label` | `brewing/recipe.rs:25` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.rs::portions` | `brewing/recipe.rs:30` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/recipe.rs::preview` | `brewing/recipe.rs:38` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `main.rs::main` | `main.rs:10` | 29 | 0 | 1 | 1 | 0 | 0 | 0 |
| `main.rs::main.<anonymous>` | `main.rs:12` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/daily/totals.rs::portions` | `reporting/daily/totals.rs:3` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/mod.rs::daily.close` | `reporting/mod.rs:8` | 11 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::Report.new` | `reporting/report.rs:10` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::Report.new.<anonymous>` | `reporting/report.rs:12` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::Report.render` | `reporting/report.rs:16` | 4 | 0 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::Report.render.<anonymous>` | `reporting/report.rs:17` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::Report.estimate` | `reporting/report.rs:21` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::total` | `reporting/report.rs:27` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::total.<anonymous>` | `reporting/report.rs:28` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::render` | `reporting/report.rs:31` | 7 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.rs::render.<anonymous>` | `reporting/report.rs:34` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `rust` | `.` | 0 | 3 | 0 | 1.00 |
| `Cargo.toml` | `Cargo.toml` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 2 | 1 | 4 | 0.33 |
| `brewing/brewer.rs` | `brewing/brewer.rs` | 2 | 3 | 2 | 0.60 |
| `brewing/brewer.rs::Brewer` | `brewing/brewer.rs:6` | 0 | 0 | 0 | N/A |
| `brewing/brewer.rs::Brewer.new` | `brewing/brewer.rs:11` | 0 | 0 | 0 | N/A |
| `brewing/brewer.rs::Brewer.brew` | `brewing/brewer.rs:15` | 1 | 2 | 1 | 0.67 |
| `brewing/brewer.rs::Brewer.remaining` | `brewing/brewer.rs:25` | 1 | 1 | 1 | 0.50 |
| `brewing/brewer.rs::brew` | `brewing/brewer.rs:30` | 2 | 1 | 2 | 0.33 |
| `brewing/brewer.rs::brew.<anonymous>` | `brewing/brewer.rs:37` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.rs::retry` | `brewing/brewer.rs:42` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.rs::score` | `brewing/brewer.rs:49` | 1 | 1 | 1 | 0.50 |
| `brewing/brewer.rs::classify` | `brewing/brewer.rs:62` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.rs::ready` | `brewing/brewer.rs:71` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.rs::calibrate` | `brewing/brewer.rs:76` | 1 | 0 | 1 | 0.00 |
| `brewing/inventory.rs` | `brewing/inventory.rs` | 3 | 1 | 3 | 0.25 |
| `brewing/inventory.rs::Adjustment` | `brewing/inventory.rs:4` | 0 | 0 | 0 | N/A |
| `brewing/inventory.rs::<anonymous>` | `brewing/inventory.rs:5` | 0 | 0 | 0 | N/A |
| `brewing/inventory.rs::Inventory` | `brewing/inventory.rs:7` | 0 | 0 | 0 | N/A |
| `brewing/inventory.rs::Inventory.new` | `brewing/inventory.rs:12` | 0 | 0 | 0 | N/A |
| `brewing/inventory.rs::Inventory.new.<anonymous>` | `brewing/inventory.rs:15` | 0 | 0 | 0 | N/A |
| `brewing/inventory.rs::Inventory.remaining` | `brewing/inventory.rs:20` | 2 | 0 | 4 | 0.00 |
| `brewing/inventory.rs::Inventory.reserve` | `brewing/inventory.rs:24` | 1 | 2 | 2 | 0.67 |
| `brewing/inventory.rs::Inventory.restock` | `brewing/inventory.rs:33` | 1 | 0 | 1 | 0.00 |
| `brewing/inventory.rs::Inventory.restock.<anonymous>` | `brewing/inventory.rs:34` | 0 | 0 | 0 | N/A |
| `brewing/inventory.rs::Inventory.restock.<anonymous>.adjusted_units` | `brewing/inventory.rs:35` | 1 | 0 | 1 | 0.00 |
| `brewing/inventory.rs::Inventory.restock.<anonymous>.<anonymous>` | `brewing/inventory.rs:38` | 0 | 1 | 0 | 1.00 |
| `brewing/mod.rs` | `brewing/mod.rs` | 1 | 3 | 1 | 0.75 |
| `brewing/mod.rs::brewer` | `brewing/mod.rs:1` | 0 | 0 | 0 | N/A |
| `brewing/mod.rs::inventory` | `brewing/mod.rs:2` | 0 | 0 | 0 | N/A |
| `brewing/mod.rs::recipe` | `brewing/mod.rs:3` | 0 | 0 | 0 | N/A |
| `brewing/recipe.rs` | `brewing/recipe.rs` | 5 | 1 | 7 | 0.17 |
| `brewing/recipe.rs::Recipe` | `brewing/recipe.rs:4` | 0 | 0 | 0 | N/A |
| `brewing/recipe.rs::Recipe.new` | `brewing/recipe.rs:10` | 0 | 0 | 0 | N/A |
| `brewing/recipe.rs::Recipe.portions` | `brewing/recipe.rs:17` | 2 | 1 | 3 | 0.33 |
| `brewing/recipe.rs::Recipe.scale` | `brewing/recipe.rs:21` | 1 | 0 | 1 | 0.00 |
| `brewing/recipe.rs::Recipe.label` | `brewing/recipe.rs:25` | 1 | 0 | 1 | 0.00 |
| `brewing/recipe.rs::portions` | `brewing/recipe.rs:30` | 6 | 0 | 10 | 0.00 |
| `brewing/recipe.rs::preview` | `brewing/recipe.rs:38` | 1 | 1 | 1 | 0.50 |
| `main.rs` | `main.rs` | 0 | 5 | 0 | 1.00 |
| `main.rs::brewing` | `main.rs:1` | 0 | 0 | 0 | N/A |
| `main.rs::reporting` | `main.rs:2` | 0 | 0 | 0 | N/A |
| `main.rs::main` | `main.rs:10` | 0 | 14 | 0 | 1.00 |
| `main.rs::main.<anonymous>` | `main.rs:12` | 0 | 0 | 0 | N/A |
| `reporting` | `reporting` | 4 | 2 | 4 | 0.33 |
| `reporting.daily` | `reporting/daily` | 2 | 1 | 4 | 0.33 |
| `reporting/daily/totals.rs` | `reporting/daily/totals.rs` | 1 | 1 | 2 | 0.50 |
| `reporting/daily/totals.rs::portions` | `reporting/daily/totals.rs:3` | 1 | 1 | 2 | 0.50 |
| `reporting/mod.rs` | `reporting/mod.rs` | 1 | 2 | 1 | 0.67 |
| `reporting/mod.rs::report` | `reporting/mod.rs:1` | 0 | 0 | 0 | N/A |
| `reporting/mod.rs::daily` | `reporting/mod.rs:4` | 1 | 2 | 1 | 0.67 |
| `reporting/mod.rs::daily.totals` | `reporting/mod.rs:6` | 0 | 0 | 0 | N/A |
| `reporting/mod.rs::daily.close` | `reporting/mod.rs:8` | 1 | 3 | 1 | 0.75 |
| `reporting/report.rs` | `reporting/report.rs` | 4 | 1 | 7 | 0.20 |
| `reporting/report.rs::Report` | `reporting/report.rs:5` | 0 | 0 | 0 | N/A |
| `reporting/report.rs::Report.new` | `reporting/report.rs:10` | 0 | 0 | 0 | N/A |
| `reporting/report.rs::Report.new.<anonymous>` | `reporting/report.rs:12` | 0 | 0 | 0 | N/A |
| `reporting/report.rs::Report.render` | `reporting/report.rs:16` | 1 | 1 | 2 | 0.50 |
| `reporting/report.rs::Report.render.<anonymous>` | `reporting/report.rs:17` | 0 | 0 | 0 | N/A |
| `reporting/report.rs::Report.estimate` | `reporting/report.rs:21` | 1 | 1 | 2 | 0.50 |
| `reporting/report.rs::total` | `reporting/report.rs:27` | 2 | 0 | 8 | 0.00 |
| `reporting/report.rs::total.<anonymous>` | `reporting/report.rs:28` | 0 | 1 | 0 | 1.00 |
| `reporting/report.rs::render` | `reporting/report.rs:31` | 3 | 1 | 6 | 0.25 |
| `reporting/report.rs::render.<anonymous>` | `reporting/report.rs:34` | 0 | 1 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/recipe.rs`
- `reporting/report.rs`

Example cycle: `brewing/recipe.rs` → `reporting/report.rs` → `brewing/recipe.rs`
