# Metrics

- files: 5
- modules: 8
- types: 3
- callables: 38
- circularImportGroups: 0
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/brewer.ex` | `brewing/brewer.ex` | 74 | 14 | 14 | 27 |
| `brewing/inventory.ex` | `brewing/inventory.ex` | 35 | 9 | 9 | 13 |
| `brewing/order.ex` | `brewing/order.ex` | 23 | 3 | 3 | 4 |
| `brewing/recipe.ex` | `brewing/recipe.ex` | 25 | 5 | 5 | 10 |
| `reporting/report.ex` | `reporting/report.ex` | 19 | 7 | 7 | 8 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew` | `brewing/brewer.ex:8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew` | `brewing/brewer.ex:10` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew.<anonymous>` | `brewing/brewer.ex:11` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.serve` | `brewing/brewer.ex:14` | 11 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.serve.<anonymous>` | `brewing/brewer.ex:15` | 8 | 2 | 4 | 4 | 0 | 0 | 2 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.retry` | `brewing/brewer.ex:26` | 1 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.retry` | `brewing/brewer.ex:27` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score` | `brewing/brewer.ex:29` | 12 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score.<anonymous>` | `brewing/brewer.ex:30` | 10 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score.<anonymous>.<anonymous>` | `brewing/brewer.ex:31` | 8 | 2 | 3 | 3 | 0 | 0 | 1 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.classify` | `brewing/brewer.ex:42` | 8 | 1 | 4 | 4 | 0 | 0 | 1 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.ready` | `brewing/brewer.ex:51` | 3 | 4 | 5 | 5 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.calibrate` | `brewing/brewer.ex:56` | 3 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.main` | `brewing/brewer.ex:60` | 14 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.new` | `brewing/inventory.ex:6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.remaining` | `brewing/inventory.ex:8` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.reserve` | `brewing/inventory.ex:10` | 8 | 2 | 3 | 3 | 0 | 0 | 1 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.restock` | `brewing/inventory.ex:19` | 9 | 3 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.restock.<anonymous>` | `brewing/inventory.ex:20` | 7 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.restock.<anonymous>.<anonymous>` | `brewing/inventory.ex:21` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.restock.<anonymous>.<anonymous>` | `brewing/inventory.ex:22` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.available` | `brewing/inventory.ex:29` | 6 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.available.<anonymous>` | `brewing/inventory.ex:30` | 4 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/order.ex::Coffee.Brewing.Order.new` | `brewing/order.ex:7` | 4 | 2 | 2 | 2 | 0 | 0 | 1 |
| `brewing/order.ex::Coffee.Brewing.Order.estimate` | `brewing/order.ex:12` | 7 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/order.ex::Coffee.Brewing.Order.preview` | `brewing/order.ex:20` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.new` | `brewing/recipe.ex:6` | 3 | 2 | 3 | 3 | 0 | 0 | 1 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.portions` | `brewing/recipe.ex:10` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.scale` | `brewing/recipe.ex:18` | 3 | 2 | 2 | 2 | 0 | 0 | 1 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.dose` | `brewing/recipe.ex:22` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.preview` | `brewing/recipe.ex:24` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.total.<anonymous>` | `reporting/report.ex:4` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.total` | `reporting/report.ex:4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.render` | `reporting/report.ex:6` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.render.<anonymous>` | `reporting/report.ex:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.daily` | `reporting/report.ex:11` | 5 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.largest` | `reporting/report.ex:17` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.ex::Coffee.Reporting.Report.largest` | `reporting/report.ex:18` | 1 | 1 | 2 | 2 | 0 | 0 | 1 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `elixir` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 0 | 4 | 0 | 1.00 |
| `brewing/brewer.ex` | `brewing/brewer.ex` | 0 | 4 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer` | `brewing/brewer.ex:1` | 0 | 4 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew` | `brewing/brewer.ex:8` | 2 | 1 | 2 | 0.33 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew` | `brewing/brewer.ex:10` | 2 | 1 | 2 | 0.33 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.brew.<anonymous>` | `brewing/brewer.ex:11` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.serve` | `brewing/brewer.ex:14` | 1 | 2 | 1 | 0.67 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.serve.<anonymous>` | `brewing/brewer.ex:15` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.retry` | `brewing/brewer.ex:26` | 2 | 0 | 2 | 0.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.retry` | `brewing/brewer.ex:27` | 1 | 1 | 1 | 0.50 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score` | `brewing/brewer.ex:29` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score.<anonymous>` | `brewing/brewer.ex:30` | 0 | 0 | 0 | N/A |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.score.<anonymous>.<anonymous>` | `brewing/brewer.ex:31` | 0 | 1 | 0 | 1.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.classify` | `brewing/brewer.ex:42` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.ready` | `brewing/brewer.ex:51` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.calibrate` | `brewing/brewer.ex:56` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.ex::Coffee.Brewing.Brewer.main` | `brewing/brewer.ex:60` | 0 | 16 | 0 | 1.00 |
| `brewing/inventory.ex` | `brewing/inventory.ex` | 1 | 1 | 1 | 0.50 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory` | `brewing/inventory.ex:1` | 2 | 1 | 2 | 0.33 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.<anonymous>` | `brewing/inventory.ex:4` | 0 | 0 | 0 | N/A |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.new` | `brewing/inventory.ex:6` | 1 | 0 | 1 | 0.00 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.remaining` | `brewing/inventory.ex:8` | 2 | 0 | 3 | 0.00 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.reserve` | `brewing/inventory.ex:10` | 1 | 2 | 1 | 0.67 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.restock` | `brewing/inventory.ex:19` | 1 | 0 | 1 | 0.00 |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.restock.<anonymous>` | `brewing/inventory.ex:20` | 0 | 0 | 0 | N/A |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.restock.<anonymous>.<anonymous>` | `brewing/inventory.ex:21` | 0 | 0 | 0 | N/A |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.restock.<anonymous>.<anonymous>` | `brewing/inventory.ex:22` | 0 | 0 | 0 | N/A |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.available` | `brewing/inventory.ex:29` | 0 | 0 | 0 | N/A |
| `brewing/inventory.ex::Coffee.Brewing.Inventory.available.<anonymous>` | `brewing/inventory.ex:30` | 0 | 2 | 0 | 1.00 |
| `brewing/order.ex` | `brewing/order.ex` | 1 | 2 | 1 | 0.67 |
| `brewing/order.ex::Coffee.Brewing.Order` | `brewing/order.ex:1` | 2 | 2 | 2 | 0.50 |
| `brewing/order.ex::Coffee.Brewing.Order.<anonymous>` | `brewing/order.ex:5` | 0 | 0 | 0 | N/A |
| `brewing/order.ex::Coffee.Brewing.Order.new` | `brewing/order.ex:7` | 1 | 0 | 1 | 0.00 |
| `brewing/order.ex::Coffee.Brewing.Order.estimate` | `brewing/order.ex:12` | 1 | 3 | 1 | 0.75 |
| `brewing/order.ex::Coffee.Brewing.Order.preview` | `brewing/order.ex:20` | 1 | 1 | 1 | 0.50 |
| `brewing/recipe.ex` | `brewing/recipe.ex` | 3 | 1 | 3 | 0.25 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe` | `brewing/recipe.ex:1` | 4 | 1 | 4 | 0.20 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.<anonymous>` | `brewing/recipe.ex:4` | 0 | 0 | 0 | N/A |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.new` | `brewing/recipe.ex:6` | 1 | 0 | 2 | 0.00 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.portions` | `brewing/recipe.ex:10` | 5 | 0 | 8 | 0.00 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.scale` | `brewing/recipe.ex:18` | 1 | 0 | 2 | 0.00 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.dose` | `brewing/recipe.ex:22` | 1 | 1 | 2 | 0.50 |
| `brewing/recipe.ex::Coffee.Brewing.Recipe.preview` | `brewing/recipe.ex:24` | 1 | 1 | 1 | 0.50 |
| `reporting` | `reporting` | 0 | 0 | 0 | N/A |
| `reporting/report.ex` | `reporting/report.ex` | 3 | 0 | 4 | 0.00 |
| `reporting/report.ex::Coffee.Reporting.Report` | `reporting/report.ex:1` | 4 | 0 | 5 | 0.00 |
| `reporting/report.ex::Coffee.Reporting.Report.total.<anonymous>` | `reporting/report.ex:4` | 0 | 0 | 0 | N/A |
| `reporting/report.ex::Coffee.Reporting.Report.total` | `reporting/report.ex:4` | 1 | 0 | 8 | 0.00 |
| `reporting/report.ex::Coffee.Reporting.Report.render` | `reporting/report.ex:6` | 5 | 1 | 7 | 0.17 |
| `reporting/report.ex::Coffee.Reporting.Report.render.<anonymous>` | `reporting/report.ex:7` | 0 | 0 | 0 | N/A |
| `reporting/report.ex::Coffee.Reporting.Report.daily` | `reporting/report.ex:11` | 1 | 3 | 1 | 0.75 |
| `reporting/report.ex::Coffee.Reporting.Report.largest` | `reporting/report.ex:17` | 2 | 0 | 3 | 0.00 |
| `reporting/report.ex::Coffee.Reporting.Report.largest` | `reporting/report.ex:18` | 1 | 1 | 2 | 0.50 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.
