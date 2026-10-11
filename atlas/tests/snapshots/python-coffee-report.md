# Metrics

- files: 7
- modules: 7
- types: 15
- callables: 50
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `src/coffee/brewing/brewer.py` | `src/coffee/brewing/brewer.py` | 99 | 9 | 9 | 30 |
| `src/coffee/brewing/recipe.py` | `src/coffee/brewing/recipe.py` | 21 | 3 | 3 | 5 |
| `src/coffee/inventory/stock.py` | `src/coffee/inventory/stock.py` | 60 | 7 | 7 | 15 |
| `src/coffee/orders/models.py` | `src/coffee/orders/models.py` | 48 | 5 | 5 | 10 |
| `src/coffee/orders/service.py` | `src/coffee/orders/service.py` | 79 | 15 | 15 | 21 |
| `src/coffee/reporting/report.py` | `src/coffee/reporting/report.py` | 16 | 3 | 3 | 5 |
| `src/coffee/reporting/sales.py` | `src/coffee/reporting/sales.py` | 38 | 8 | 8 | 16 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `src/coffee/brewing/brewer.py::Brewing.brew` | `src/coffee/brewing/brewer.py:23` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/brewer.py::Brewer.brew` | `src/coffee/brewing/brewer.py:28` | 5 | 1 | 4 | 4 | 0 | 0 | 1 |
| `src/coffee/brewing/brewer.py::Brewer.retry` | `src/coffee/brewing/brewer.py:34` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/brewing/brewer.py::Brewer.score` | `src/coffee/brewing/brewer.py:39` | 8 | 1 | 5 | 7 | 1 | 1 | 3 |
| `src/coffee/brewing/brewer.py::Brewer.classify` | `src/coffee/brewing/brewer.py:49` | 19 | 1 | 9 | 9 | 0 | 0 | 1 |
| `src/coffee/brewing/brewer.py::Brewer.ready` | `src/coffee/brewing/brewer.py:69` | 2 | 4 | 4 | 4 | 0 | 0 | 0 |
| `src/coffee/brewing/brewer.py::Brewer.calibrate` | `src/coffee/brewing/brewer.py:72` | 6 | 8 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/brewer.py::import_styles` | `src/coffee/brewing/brewer.py:80` | 11 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/brewer.py::main` | `src/coffee/brewing/brewer.py:93` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/recipe.py::Recipe.portions` | `src/coffee/brewing/recipe.py:3` | 8 | 1 | 3 | 3 | 0 | 0 | 1 |
| `src/coffee/brewing/recipe.py::Recipe.preview` | `src/coffee/brewing/recipe.py:13` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/brewing/recipe.py::portions` | `src/coffee/brewing/recipe.py:20` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/inventory/stock.py::Ledger.record` | `src/coffee/inventory/stock.py:13` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/inventory/stock.py::Inventory.Snapshot.units` | `src/coffee/inventory/stock.py:29` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/inventory/stock.py::Inventory.__init__` | `src/coffee/inventory/stock.py:32` | 3 | 1 | 2 | 2 | 0 | 0 | 0 |
| `src/coffee/inventory/stock.py::Inventory.record` | `src/coffee/inventory/stock.py:36` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/inventory/stock.py::Inventory.receive` | `src/coffee/inventory/stock.py:40` | 5 | 2 | 3 | 3 | 0 | 0 | 1 |
| `src/coffee/inventory/stock.py::Inventory.reserve` | `src/coffee/inventory/stock.py:46` | 12 | 1 | 6 | 6 | 0 | 0 | 2 |
| `src/coffee/inventory/stock.py::Inventory.snapshot` | `src/coffee/inventory/stock.py:59` | 2 | 0 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/models.py::OrderLine.subtotal` | `src/coffee/orders/models.py:17` | 2 | 0 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/models.py::OrderLine.espresso` | `src/coffee/orders/models.py:21` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/models.py::Order.total` | `src/coffee/orders/models.py:33` | 2 | 0 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/orders/models.py::Order.names` | `src/coffee/orders/models.py:36` | 2 | 0 | 3 | 3 | 0 | 0 | 1 |
| `src/coffee/orders/models.py::Order.transition` | `src/coffee/orders/models.py:39` | 10 | 1 | 3 | 3 | 0 | 0 | 1 |
| `src/coffee/orders/service.py::audited` | `src/coffee/orders/service.py:10` | 9 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::audited.decorate` | `src/coffee/orders/service.py:12` | 6 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::audited.decorate.wrapped` | `src/coffee/orders/service.py:14` | 3 | 3 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::CoffeeOrders.fulfill` | `src/coffee/orders/service.py:23` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::AuditTrail.audit` | `src/coffee/orders/service.py:28` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::OrderService.__init__` | `src/coffee/orders/service.py:33` | 5 | 2 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::OrderService.place` | `src/coffee/orders/service.py:40` | 10 | 7 | 4 | 4 | 0 | 0 | 1 |
| `src/coffee/orders/service.py::OrderService.fulfill` | `src/coffee/orders/service.py:51` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/orders/service.py::OrderService.preview` | `src/coffee/orders/service.py:59` | 2 | 2 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::OrderService.receipts` | `src/coffee/orders/service.py:62` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::OrderService.receipts.format_ready` | `src/coffee/orders/service.py:63` | 2 | 1 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/orders/service.py::OrderService.notify` | `src/coffee/orders/service.py:67` | 3 | 1 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/orders/service.py::OrderService.notify.<anonymous>` | `src/coffee/orders/service.py:68` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::OrderService.estimate` | `src/coffee/orders/service.py:72` | 2 | 3 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/orders/service.py::OrderService.stocked` | `src/coffee/orders/service.py:76` | 4 | 2 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/reporting/report.py::Report.total` | `src/coffee/reporting/report.py:6` | 2 | 1 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/reporting/report.py::Report.render` | `src/coffee/reporting/report.py:10` | 3 | 1 | 2 | 2 | 0 | 0 | 1 |
| `src/coffee/reporting/report.py::render` | `src/coffee/reporting/report.py:15` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/reporting/sales.py::SalesReport.__init__` | `src/coffee/reporting/sales.py:10` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/reporting/sales.py::SalesReport.__init__.<anonymous>` | `src/coffee/reporting/sales.py:12` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/reporting/sales.py::SalesReport.totals` | `src/coffee/reporting/sales.py:14` | 12 | 2 | 4 | 4 | 0 | 0 | 1 |
| `src/coffee/reporting/sales.py::SalesReport.totals.collect` | `src/coffee/reporting/sales.py:17` | 5 | 1 | 3 | 3 | 0 | 0 | 1 |
| `src/coffee/reporting/sales.py::SalesReport.discounts` | `src/coffee/reporting/sales.py:27` | 7 | 2 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/reporting/sales.py::SalesReport.discounts.<anonymous>` | `src/coffee/reporting/sales.py:30` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/reporting/sales.py::SalesReport.discounts.<anonymous>.<anonymous>` | `src/coffee/reporting/sales.py:31` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `src/coffee/reporting/sales.py::SalesReport.render` | `src/coffee/reporting/sales.py:35` | 4 | 1 | 4 | 4 | 0 | 0 | 1 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `python` | `.` | 0 | 0 | 0 | N/A |
| `src` | `src` | 0 | 0 | 0 | N/A |
| `src.coffee` | `src/coffee` | 0 | 0 | 0 | N/A |
| `src.coffee.brewing` | `src/coffee/brewing` | 3 | 1 | 3 | 0.25 |
| `src/coffee/brewing/brewer.py` | `src/coffee/brewing/brewer.py` | 1 | 2 | 1 | 0.67 |
| `src/coffee/brewing/brewer.py::Brewing` | `src/coffee/brewing/brewer.py:21` | 1 | 0 | 2 | 0.00 |
| `src/coffee/brewing/brewer.py::Brewing.brew` | `src/coffee/brewing/brewer.py:23` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::Brewer` | `src/coffee/brewing/brewer.py:27` | 1 | 3 | 1 | 0.75 |
| `src/coffee/brewing/brewer.py::Brewer.brew` | `src/coffee/brewing/brewer.py:28` | 3 | 2 | 4 | 0.40 |
| `src/coffee/brewing/brewer.py::Brewer.retry` | `src/coffee/brewing/brewer.py:34` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::Brewer.score` | `src/coffee/brewing/brewer.py:39` | 0 | 1 | 0 | 1.00 |
| `src/coffee/brewing/brewer.py::Brewer.classify` | `src/coffee/brewing/brewer.py:49` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::Brewer.ready` | `src/coffee/brewing/brewer.py:69` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::Brewer.calibrate` | `src/coffee/brewing/brewer.py:72` | 0 | 0 | 0 | N/A |
| `src/coffee/brewing/brewer.py::import_styles` | `src/coffee/brewing/brewer.py:80` | 1 | 2 | 1 | 0.67 |
| `src/coffee/brewing/brewer.py::main` | `src/coffee/brewing/brewer.py:93` | 0 | 2 | 0 | 1.00 |
| `src/coffee/brewing/recipe.py` | `src/coffee/brewing/recipe.py` | 3 | 1 | 5 | 0.25 |
| `src/coffee/brewing/recipe.py::Recipe` | `src/coffee/brewing/recipe.py:1` | 3 | 1 | 5 | 0.25 |
| `src/coffee/brewing/recipe.py::Recipe.portions` | `src/coffee/brewing/recipe.py:3` | 6 | 0 | 14 | 0.00 |
| `src/coffee/brewing/recipe.py::Recipe.preview` | `src/coffee/brewing/recipe.py:13` | 0 | 1 | 0 | 1.00 |
| `src/coffee/brewing/recipe.py::portions` | `src/coffee/brewing/recipe.py:20` | 1 | 1 | 2 | 0.50 |
| `src.coffee.inventory` | `src/coffee/inventory` | 2 | 2 | 3 | 0.50 |
| `src/coffee/inventory/stock.py` | `src/coffee/inventory/stock.py` | 2 | 2 | 2 | 0.50 |
| `src/coffee/inventory/stock.py::Ledger` | `src/coffee/inventory/stock.py:11` | 1 | 0 | 3 | 0.00 |
| `src/coffee/inventory/stock.py::Ledger.record` | `src/coffee/inventory/stock.py:13` | 0 | 0 | 0 | N/A |
| `src/coffee/inventory/stock.py::StockChange` | `src/coffee/inventory/stock.py:18` | 1 | 0 | 3 | 0.00 |
| `src/coffee/inventory/stock.py::Inventory` | `src/coffee/inventory/stock.py:24` | 2 | 4 | 2 | 0.67 |
| `src/coffee/inventory/stock.py::Inventory.Snapshot` | `src/coffee/inventory/stock.py:26` | 1 | 0 | 3 | 0.00 |
| `src/coffee/inventory/stock.py::Inventory.Snapshot.units` | `src/coffee/inventory/stock.py:29` | 0 | 0 | 0 | N/A |
| `src/coffee/inventory/stock.py::Inventory.__init__` | `src/coffee/inventory/stock.py:32` | 0 | 0 | 0 | N/A |
| `src/coffee/inventory/stock.py::Inventory.record` | `src/coffee/inventory/stock.py:36` | 2 | 0 | 5 | 0.00 |
| `src/coffee/inventory/stock.py::Inventory.receive` | `src/coffee/inventory/stock.py:40` | 1 | 1 | 1 | 0.50 |
| `src/coffee/inventory/stock.py::Inventory.reserve` | `src/coffee/inventory/stock.py:46` | 1 | 2 | 2 | 0.67 |
| `src/coffee/inventory/stock.py::Inventory.snapshot` | `src/coffee/inventory/stock.py:59` | 1 | 0 | 1 | 0.00 |
| `src.coffee.orders` | `src/coffee/orders` | 2 | 2 | 3 | 0.50 |
| `src/coffee/orders/models.py` | `src/coffee/orders/models.py` | 3 | 0 | 3 | 0.00 |
| `src/coffee/orders/models.py::OrderStatus` | `src/coffee/orders/models.py:5` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/models.py::OrderLine` | `src/coffee/orders/models.py:12` | 1 | 0 | 1 | 0.00 |
| `src/coffee/orders/models.py::OrderLine.subtotal` | `src/coffee/orders/models.py:17` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/models.py::OrderLine.espresso` | `src/coffee/orders/models.py:21` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/models.py::Order` | `src/coffee/orders/models.py:26` | 1 | 0 | 1 | 0.00 |
| `src/coffee/orders/models.py::Order.total` | `src/coffee/orders/models.py:33` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/models.py::Order.names` | `src/coffee/orders/models.py:36` | 2 | 0 | 3 | 0.00 |
| `src/coffee/orders/models.py::Order.transition` | `src/coffee/orders/models.py:39` | 1 | 0 | 2 | 0.00 |
| `src/coffee/orders/service.py` | `src/coffee/orders/service.py` | 0 | 3 | 0 | 1.00 |
| `src/coffee/orders/service.py::audited` | `src/coffee/orders/service.py:10` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/service.py::audited.decorate` | `src/coffee/orders/service.py:12` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/service.py::audited.decorate.wrapped` | `src/coffee/orders/service.py:14` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/service.py::CoffeeOrders` | `src/coffee/orders/service.py:21` | 1 | 0 | 1 | 0.00 |
| `src/coffee/orders/service.py::CoffeeOrders.fulfill` | `src/coffee/orders/service.py:23` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/service.py::AuditTrail` | `src/coffee/orders/service.py:27` | 1 | 0 | 1 | 0.00 |
| `src/coffee/orders/service.py::AuditTrail.audit` | `src/coffee/orders/service.py:28` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/service.py::OrderService` | `src/coffee/orders/service.py:32` | 0 | 6 | 0 | 1.00 |
| `src/coffee/orders/service.py::OrderService.__init__` | `src/coffee/orders/service.py:33` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/service.py::OrderService.place` | `src/coffee/orders/service.py:40` | 0 | 1 | 0 | 1.00 |
| `src/coffee/orders/service.py::OrderService.fulfill` | `src/coffee/orders/service.py:51` | 1 | 4 | 1 | 0.80 |
| `src/coffee/orders/service.py::OrderService.preview` | `src/coffee/orders/service.py:59` | 0 | 2 | 0 | 1.00 |
| `src/coffee/orders/service.py::OrderService.receipts` | `src/coffee/orders/service.py:62` | 1 | 0 | 1 | 0.00 |
| `src/coffee/orders/service.py::OrderService.receipts.format_ready` | `src/coffee/orders/service.py:63` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/service.py::OrderService.notify` | `src/coffee/orders/service.py:67` | 0 | 1 | 0 | 1.00 |
| `src/coffee/orders/service.py::OrderService.notify.<anonymous>` | `src/coffee/orders/service.py:68` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/service.py::OrderService.estimate` | `src/coffee/orders/service.py:72` | 0 | 0 | 0 | N/A |
| `src/coffee/orders/service.py::OrderService.stocked` | `src/coffee/orders/service.py:76` | 0 | 1 | 0 | 1.00 |
| `src.coffee.reporting` | `src/coffee/reporting` | 1 | 3 | 3 | 0.75 |
| `src/coffee/reporting/report.py` | `src/coffee/reporting/report.py` | 3 | 1 | 5 | 0.25 |
| `src/coffee/reporting/report.py::Report` | `src/coffee/reporting/report.py:4` | 3 | 1 | 5 | 0.25 |
| `src/coffee/reporting/report.py::Report.total` | `src/coffee/reporting/report.py:6` | 1 | 1 | 10 | 0.50 |
| `src/coffee/reporting/report.py::Report.render` | `src/coffee/reporting/report.py:10` | 4 | 2 | 9 | 0.33 |
| `src/coffee/reporting/report.py::render` | `src/coffee/reporting/report.py:15` | 1 | 1 | 2 | 0.50 |
| `src/coffee/reporting/sales.py` | `src/coffee/reporting/sales.py` | 0 | 3 | 0 | 1.00 |
| `src/coffee/reporting/sales.py::SalesReport` | `src/coffee/reporting/sales.py:9` | 0 | 2 | 0 | 1.00 |
| `src/coffee/reporting/sales.py::SalesReport.__init__` | `src/coffee/reporting/sales.py:10` | 0 | 0 | 0 | N/A |
| `src/coffee/reporting/sales.py::SalesReport.__init__.<anonymous>` | `src/coffee/reporting/sales.py:12` | 0 | 0 | 0 | N/A |
| `src/coffee/reporting/sales.py::SalesReport.totals` | `src/coffee/reporting/sales.py:14` | 0 | 1 | 0 | 1.00 |
| `src/coffee/reporting/sales.py::SalesReport.totals.collect` | `src/coffee/reporting/sales.py:17` | 1 | 0 | 1 | 0.00 |
| `src/coffee/reporting/sales.py::SalesReport.discounts` | `src/coffee/reporting/sales.py:27` | 0 | 0 | 0 | N/A |
| `src/coffee/reporting/sales.py::SalesReport.discounts.<anonymous>` | `src/coffee/reporting/sales.py:30` | 0 | 0 | 0 | N/A |
| `src/coffee/reporting/sales.py::SalesReport.discounts.<anonymous>.<anonymous>` | `src/coffee/reporting/sales.py:31` | 0 | 0 | 0 | N/A |
| `src/coffee/reporting/sales.py::SalesReport.render` | `src/coffee/reporting/sales.py:35` | 0 | 2 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `src/coffee/brewing/recipe.py`
- `src/coffee/reporting/report.py`

Example cycle: `src/coffee/brewing/recipe.py` → `src/coffee/reporting/report.py` → `src/coffee/brewing/recipe.py`
