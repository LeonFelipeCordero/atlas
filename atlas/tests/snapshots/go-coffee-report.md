# Metrics

- files: 7
- modules: 4
- types: 6
- callables: 30
- circularImportGroups: 0
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/brewer.go` | `brewing/brewer.go` | 97 | 11 | 11 | 30 |
| `brewing/inventory.go` | `brewing/inventory.go` | 36 | 6 | 6 | 9 |
| `brewing/order.go` | `brewing/order.go` | 26 | 3 | 3 | 3 |
| `go.mod` | `go.mod` | 3 | 0 | 0 | 0 |
| `main.go` | `main.go` | 7 | 1 | 1 | 1 |
| `recipe/recipe.go` | `recipe/recipe.go` | 39 | 5 | 5 | 8 |
| `reporting/report.go` | `reporting/report.go` | 38 | 4 | 4 | 6 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/brewer.go::NewBrewer` | `brewing/brewer.go:15` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.go::Brew` | `brewing/brewer.go:19` | 10 | 1 | 3 | 3 | 0 | 0 | 2 |
| `brewing/brewer.go::brew` | `brewing/brewer.go:30` | 13 | 1 | 4 | 4 | 0 | 0 | 2 |
| `brewing/brewer.go::brew.accept` | `brewing/brewer.go:35` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.go::retry` | `brewing/brewer.go:44` | 6 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/brewer.go::score` | `brewing/brewer.go:51` | 12 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/brewer.go::classify` | `brewing/brewer.go:65` | 12 | 1 | 4 | 4 | 0 | 0 | 1 |
| `brewing/brewer.go::ready` | `brewing/brewer.go:78` | 3 | 4 | 5 | 5 | 0 | 0 | 0 |
| `brewing/brewer.go::calibrate` | `brewing/brewer.go:83` | 3 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.go::Main` | `brewing/brewer.go:87` | 11 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/brewer.go::Main.<anonymous>` | `brewing/brewer.go:89` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.go::NewInventory` | `brewing/inventory.go:11` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.go::Remaining` | `brewing/inventory.go:15` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.go::Reserve` | `brewing/inventory.go:19` | 8 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/inventory.go::Restock` | `brewing/inventory.go:28` | 9 | 2 | 2 | 2 | 0 | 0 | 1 |
| `brewing/inventory.go::Restock.apply` | `brewing/inventory.go:29` | 4 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/inventory.go::Restock.apply.normalize` | `brewing/inventory.go:30` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/order.go::NewOrder` | `brewing/order.go:14` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `brewing/order.go::Serve` | `brewing/order.go:18` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/order.go::Estimate` | `brewing/order.go:22` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `main.go::main` | `main.go:5` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `recipe/recipe.go::Normalize` | `recipe/recipe.go:6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `recipe/recipe.go::New` | `recipe/recipe.go:13` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `recipe/recipe.go::Portions` | `recipe/recipe.go:17` | 10 | 1 | 3 | 3 | 0 | 0 | 1 |
| `recipe/recipe.go::Dose` | `recipe/recipe.go:28` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `recipe/recipe.go::Scale` | `recipe/recipe.go:33` | 7 | 3 | 2 | 2 | 0 | 0 | 1 |
| `reporting/report.go::Total` | `reporting/report.go:14` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `reporting/report.go::Render` | `reporting/report.go:22` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `reporting/report.go::Receipt` | `reporting/report.go:30` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `reporting/report.go::Preview` | `reporting/report.go:35` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `go` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 0 | 0 | 0 | N/A |
| `brewing/brewer.go` | `brewing/brewer.go` | 1 | 2 | 1 | 0.67 |
| `brewing/brewer.go::Brewer` | `brewing/brewer.go:11` | 0 | 0 | 0 | N/A |
| `brewing/brewer.go::NewBrewer` | `brewing/brewer.go:15` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.go::Brew` | `brewing/brewer.go:19` | 1 | 2 | 2 | 0.67 |
| `brewing/brewer.go::brew` | `brewing/brewer.go:30` | 2 | 1 | 3 | 0.33 |
| `brewing/brewer.go::brew.accept` | `brewing/brewer.go:35` | 1 | 0 | 4 | 0.00 |
| `brewing/brewer.go::retry` | `brewing/brewer.go:44` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.go::score` | `brewing/brewer.go:51` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.go::classify` | `brewing/brewer.go:65` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.go::ready` | `brewing/brewer.go:78` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.go::calibrate` | `brewing/brewer.go:83` | 1 | 0 | 1 | 0.00 |
| `brewing/brewer.go::Main` | `brewing/brewer.go:87` | 0 | 13 | 0 | 1.00 |
| `brewing/brewer.go::Main.<anonymous>` | `brewing/brewer.go:89` | 0 | 0 | 0 | N/A |
| `brewing/inventory.go` | `brewing/inventory.go` | 1 | 0 | 2 | 0.00 |
| `brewing/inventory.go::Adjustment` | `brewing/inventory.go:5` | 0 | 0 | 0 | N/A |
| `brewing/inventory.go::Inventory` | `brewing/inventory.go:7` | 0 | 0 | 0 | N/A |
| `brewing/inventory.go::NewInventory` | `brewing/inventory.go:11` | 1 | 0 | 1 | 0.00 |
| `brewing/inventory.go::Remaining` | `brewing/inventory.go:15` | 2 | 0 | 4 | 0.00 |
| `brewing/inventory.go::Reserve` | `brewing/inventory.go:19` | 1 | 1 | 3 | 0.50 |
| `brewing/inventory.go::Restock` | `brewing/inventory.go:28` | 1 | 1 | 1 | 0.50 |
| `brewing/inventory.go::Restock.apply` | `brewing/inventory.go:29` | 1 | 1 | 2 | 0.50 |
| `brewing/inventory.go::Restock.apply.normalize` | `brewing/inventory.go:30` | 1 | 0 | 3 | 0.00 |
| `brewing/order.go` | `brewing/order.go` | 1 | 1 | 1 | 0.50 |
| `brewing/order.go::Order` | `brewing/order.go:9` | 0 | 0 | 0 | N/A |
| `brewing/order.go::NewOrder` | `brewing/order.go:14` | 1 | 0 | 1 | 0.00 |
| `brewing/order.go::Serve` | `brewing/order.go:18` | 1 | 1 | 1 | 0.50 |
| `brewing/order.go::Estimate` | `brewing/order.go:22` | 1 | 0 | 1 | 0.00 |
| `go.mod` | `go.mod` | 0 | 0 | 0 | N/A |
| `main.go` | `main.go` | 0 | 0 | 0 | N/A |
| `main.go::main` | `main.go:5` | 0 | 0 | 0 | N/A |
| `recipe` | `recipe` | 0 | 0 | 0 | N/A |
| `recipe/recipe.go` | `recipe/recipe.go` | 0 | 0 | 0 | N/A |
| `recipe/recipe.go::Normalize` | `recipe/recipe.go:6` | 2 | 0 | 2 | 0.00 |
| `recipe/recipe.go::Recipe` | `recipe/recipe.go:8` | 0 | 0 | 0 | N/A |
| `recipe/recipe.go::New` | `recipe/recipe.go:13` | 0 | 1 | 0 | 1.00 |
| `recipe/recipe.go::Portions` | `recipe/recipe.go:17` | 1 | 0 | 1 | 0.00 |
| `recipe/recipe.go::Dose` | `recipe/recipe.go:28` | 0 | 1 | 0 | 1.00 |
| `recipe/recipe.go::Scale` | `recipe/recipe.go:33` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 0 | 0 | 0 | N/A |
| `reporting/report.go` | `reporting/report.go` | 0 | 0 | 0 | N/A |
| `reporting/report.go::Report` | `reporting/report.go:10` | 0 | 0 | 0 | N/A |
| `reporting/report.go::Total` | `reporting/report.go:14` | 1 | 0 | 3 | 0.00 |
| `reporting/report.go::Render` | `reporting/report.go:22` | 1 | 1 | 2 | 0.50 |
| `reporting/report.go::Receipt` | `reporting/report.go:30` | 1 | 1 | 1 | 0.50 |
| `reporting/report.go::Preview` | `reporting/report.go:35` | 0 | 1 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.
