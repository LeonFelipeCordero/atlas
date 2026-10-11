# Metrics

- files: 9
- modules: 14
- types: 15
- callables: 59
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.java` | `brewing/Brewer.java` | 64 | 9 | 9 | 28 |
| `brewing/Recipe.java` | `brewing/Recipe.java` | 20 | 2 | 2 | 4 |
| `inventory/Inventory.java` | `inventory/Inventory.java` | 54 | 7 | 7 | 11 |
| `inventory/StockLedger.java` | `inventory/StockLedger.java` | 19 | 2 | 2 | 3 |
| `orders/CoffeeOrders.java` | `orders/CoffeeOrders.java` | 9 | 2 | 2 | 2 |
| `orders/Order.java` | `orders/Order.java` | 59 | 6 | 6 | 9 |
| `orders/OrderService.java` | `orders/OrderService.java` | 78 | 9 | 9 | 11 |
| `reporting/Report.java` | `reporting/Report.java` | 20 | 3 | 3 | 3 |
| `reporting/SalesReport.java` | `reporting/SalesReport.java` | 40 | 10 | 10 | 10 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.java::Brewing.brew` | `brewing/Brewer.java:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.java::Brewer.brew` | `brewing/Brewer.java:11` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.java::Brewer.brew.<anonymous>` | `brewing/Brewer.java:15` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.java::Brewer.retry` | `brewing/Brewer.java:19` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.java::Brewer.score` | `brewing/Brewer.java:24` | 12 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/Brewer.java::Brewer.classify` | `brewing/Brewer.java:38` | 12 | 1 | 9 | 9 | 0 | 0 | 1 |
| `brewing/Brewer.java::Brewer.ready` | `brewing/Brewer.java:51` | 3 | 4 | 4 | 4 | 0 | 0 | 0 |
| `brewing/Brewer.java::Brewer.calibrate` | `brewing/Brewer.java:55` | 5 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.java::Brewer.main` | `brewing/Brewer.java:61` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.java::Recipe.portions` | `brewing/Recipe.java:9` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/Recipe.java::Recipe.preview` | `brewing/Recipe.java:17` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.java::Reservable.reserve` | `inventory/Inventory.java:9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.java::Inventory.record` | `inventory/Inventory.java:27` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.java::Inventory.receive` | `inventory/Inventory.java:33` | 3 | 1 | 2 | 2 | 0 | 0 | 1 |
| `inventory/Inventory.java::Inventory.reserve` | `inventory/Inventory.java:37` | 13 | 1 | 4 | 4 | 0 | 0 | 2 |
| `inventory/Inventory.java::Inventory.reserve.<anonymous>` | `inventory/Inventory.java:45` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.java::Inventory.reserve.<anonymous>` | `inventory/Inventory.java:47` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.java::Inventory.units` | `inventory/Inventory.java:51` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/StockLedger.java::StockLedger.record` | `inventory/StockLedger.java:10` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/StockLedger.java::StockLedger.snapshot` | `inventory/StockLedger.java:14` | 5 | 1 | 2 | 2 | 0 | 0 | 1 |
| `orders/CoffeeOrders.java::CoffeeOrders.fulfill` | `orders/CoffeeOrders.java:4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/CoffeeOrders.java::CoffeeOrders.ready` | `orders/CoffeeOrders.java:6` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.java::Order.Line.subtotal` | `orders/Order.java:20` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.java::Order.status` | `orders/Order.java:36` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.java::Order.total` | `orders/Order.java:40` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.java::Order.names` | `orders/Order.java:44` | 4 | 0 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.java::Order.names.<anonymous>` | `orders/Order.java:45` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.java::Order.transition` | `orders/Order.java:49` | 10 | 1 | 4 | 4 | 0 | 0 | 1 |
| `orders/OrderService.java::OrderService.audit` | `orders/OrderService.java:16` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.java::OrderService.place` | `orders/OrderService.java:27` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.java::OrderService.place` | `orders/OrderService.java:31` | 7 | 4 | 2 | 2 | 0 | 0 | 1 |
| `orders/OrderService.java::OrderService.fulfill` | `orders/OrderService.java:39` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `orders/OrderService.java::OrderService.preview` | `orders/OrderService.java:47` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.java::OrderService.orders` | `orders/OrderService.java:51` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.java::OrderService.place` | `orders/OrderService.java:55` | 4 | 2 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.java::OrderService.stocked` | `orders/OrderService.java:60` | 6 | 2 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.java::OrderService.Factory.create` | `orders/OrderService.java:74` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.java::Report.total` | `reporting/Report.java:10` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.java::Report.render` | `reporting/Report.java:14` | 6 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.java::Report.render.<anonymous>` | `reporting/Report.java:16` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.include` | `reporting/SalesReport.java:13` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.totals` | `reporting/SalesReport.java:19` | 10 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.totals.<anonymous>` | `reporting/SalesReport.java:21` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.totals.<anonymous>.<anonymous>` | `reporting/SalesReport.java:22` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.totals.<anonymous>` | `reporting/SalesReport.java:26` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.discounts` | `reporting/SalesReport.java:30` | 4 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.discounts.<anonymous>` | `reporting/SalesReport.java:31` | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.discounts.<anonymous>.<anonymous>` | `reporting/SalesReport.java:32` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.summary` | `reporting/SalesReport.java:35` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.java::SalesReport.summary.<anonymous>` | `reporting/SalesReport.java:37` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `java` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 3 | 1 | 3 | 0.25 |
| `brewing/Brewer.java` | `brewing/Brewer.java` | 1 | 2 | 1 | 0.67 |
| `brewing/Brewer.java::coffee.brewing` | `brewing/Brewer.java:1` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewing` | `brewing/Brewer.java:6` | 1 | 0 | 2 | 0.00 |
| `brewing/Brewer.java::Brewing.brew` | `brewing/Brewer.java:7` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer` | `brewing/Brewer.java:10` | 1 | 3 | 1 | 0.75 |
| `brewing/Brewer.java::Brewer.brew` | `brewing/Brewer.java:11` | 3 | 1 | 4 | 0.25 |
| `brewing/Brewer.java::Brewer.brew.<anonymous>` | `brewing/Brewer.java:15` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.java::Brewer.retry` | `brewing/Brewer.java:19` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer.score` | `brewing/Brewer.java:24` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.java::Brewer.classify` | `brewing/Brewer.java:38` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer.ready` | `brewing/Brewer.java:51` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer.calibrate` | `brewing/Brewer.java:55` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.java::Brewer.main` | `brewing/Brewer.java:61` | 0 | 1 | 0 | 1.00 |
| `brewing/Recipe.java` | `brewing/Recipe.java` | 3 | 1 | 5 | 0.25 |
| `brewing/Recipe.java::coffee.brewing` | `brewing/Recipe.java:1` | 0 | 0 | 0 | N/A |
| `brewing/Recipe.java::Recipe` | `brewing/Recipe.java:6` | 3 | 1 | 5 | 0.25 |
| `brewing/Recipe.java::Recipe.Recipe` | `brewing/Recipe.java:7` | 0 | 0 | 0 | N/A |
| `brewing/Recipe.java::Recipe.portions` | `brewing/Recipe.java:9` | 5 | 0 | 13 | 0.00 |
| `brewing/Recipe.java::Recipe.preview` | `brewing/Recipe.java:17` | 0 | 1 | 0 | 1.00 |
| `inventory` | `inventory` | 2 | 2 | 3 | 0.50 |
| `inventory/Inventory.java` | `inventory/Inventory.java` | 2 | 3 | 2 | 0.60 |
| `inventory/Inventory.java::coffee.inventory` | `inventory/Inventory.java:1` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.java::Reservable` | `inventory/Inventory.java:8` | 1 | 0 | 3 | 0.00 |
| `inventory/Inventory.java::Reservable.reserve` | `inventory/Inventory.java:9` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.java::Inventory` | `inventory/Inventory.java:12` | 2 | 4 | 2 | 0.67 |
| `inventory/Inventory.java::Inventory.Change` | `inventory/Inventory.java:13` | 2 | 0 | 3 | 0.00 |
| `inventory/Inventory.java::Inventory.Change.Change` | `inventory/Inventory.java:18` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.java::Inventory.record` | `inventory/Inventory.java:27` | 2 | 0 | 3 | 0.00 |
| `inventory/Inventory.java::Inventory.receive` | `inventory/Inventory.java:33` | 1 | 1 | 1 | 0.50 |
| `inventory/Inventory.java::Inventory.reserve` | `inventory/Inventory.java:37` | 1 | 1 | 2 | 0.50 |
| `inventory/Inventory.java::Inventory.reserve.<anonymous>` | `inventory/Inventory.java:45` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.java::Inventory.reserve.<anonymous>` | `inventory/Inventory.java:47` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.java::Inventory.units` | `inventory/Inventory.java:51` | 2 | 0 | 2 | 0.00 |
| `inventory/StockLedger.java` | `inventory/StockLedger.java` | 1 | 0 | 3 | 0.00 |
| `inventory/StockLedger.java::coffee.inventory` | `inventory/StockLedger.java:1` | 0 | 0 | 0 | N/A |
| `inventory/StockLedger.java::StockLedger` | `inventory/StockLedger.java:7` | 1 | 0 | 3 | 0.00 |
| `inventory/StockLedger.java::StockLedger.record` | `inventory/StockLedger.java:10` | 0 | 0 | 0 | N/A |
| `inventory/StockLedger.java::StockLedger.snapshot` | `inventory/StockLedger.java:14` | 0 | 0 | 0 | N/A |
| `orders` | `orders` | 2 | 2 | 3 | 0.50 |
| `orders/CoffeeOrders.java` | `orders/CoffeeOrders.java` | 1 | 0 | 1 | 0.00 |
| `orders/CoffeeOrders.java::coffee.orders` | `orders/CoffeeOrders.java:1` | 0 | 0 | 0 | N/A |
| `orders/CoffeeOrders.java::CoffeeOrders` | `orders/CoffeeOrders.java:3` | 1 | 0 | 1 | 0.00 |
| `orders/CoffeeOrders.java::CoffeeOrders.fulfill` | `orders/CoffeeOrders.java:4` | 0 | 0 | 0 | N/A |
| `orders/CoffeeOrders.java::CoffeeOrders.ready` | `orders/CoffeeOrders.java:6` | 0 | 0 | 0 | N/A |
| `orders/Order.java` | `orders/Order.java` | 3 | 0 | 3 | 0.00 |
| `orders/Order.java::coffee.orders` | `orders/Order.java:1` | 0 | 0 | 0 | N/A |
| `orders/Order.java::Order` | `orders/Order.java:6` | 1 | 0 | 1 | 0.00 |
| `orders/Order.java::Order.Status` | `orders/Order.java:7` | 0 | 0 | 0 | N/A |
| `orders/Order.java::Order.Line` | `orders/Order.java:9` | 1 | 0 | 1 | 0.00 |
| `orders/Order.java::Order.Line.Line` | `orders/Order.java:14` | 0 | 0 | 0 | N/A |
| `orders/Order.java::Order.Line.subtotal` | `orders/Order.java:20` | 0 | 0 | 0 | N/A |
| `orders/Order.java::Order.Order` | `orders/Order.java:30` | 0 | 0 | 0 | N/A |
| `orders/Order.java::Order.status` | `orders/Order.java:36` | 0 | 0 | 0 | N/A |
| `orders/Order.java::Order.total` | `orders/Order.java:40` | 0 | 0 | 0 | N/A |
| `orders/Order.java::Order.names` | `orders/Order.java:44` | 2 | 0 | 3 | 0.00 |
| `orders/Order.java::Order.names.<anonymous>` | `orders/Order.java:45` | 0 | 0 | 0 | N/A |
| `orders/Order.java::Order.transition` | `orders/Order.java:49` | 1 | 0 | 2 | 0.00 |
| `orders/OrderService.java` | `orders/OrderService.java` | 0 | 4 | 0 | 1.00 |
| `orders/OrderService.java::coffee.orders` | `orders/OrderService.java:1` | 0 | 0 | 0 | N/A |
| `orders/OrderService.java::OrderService` | `orders/OrderService.java:11` | 0 | 6 | 0 | 1.00 |
| `orders/OrderService.java::OrderService.audit` | `orders/OrderService.java:16` | 0 | 0 | 0 | N/A |
| `orders/OrderService.java::OrderService.OrderService` | `orders/OrderService.java:18` | 0 | 0 | 0 | N/A |
| `orders/OrderService.java::OrderService.OrderService` | `orders/OrderService.java:23` | 0 | 0 | 0 | N/A |
| `orders/OrderService.java::OrderService.place` | `orders/OrderService.java:27` | 0 | 0 | 0 | N/A |
| `orders/OrderService.java::OrderService.place` | `orders/OrderService.java:31` | 0 | 1 | 0 | 1.00 |
| `orders/OrderService.java::OrderService.fulfill` | `orders/OrderService.java:39` | 1 | 4 | 1 | 0.80 |
| `orders/OrderService.java::OrderService.preview` | `orders/OrderService.java:47` | 0 | 2 | 0 | 1.00 |
| `orders/OrderService.java::OrderService.orders` | `orders/OrderService.java:51` | 0 | 0 | 0 | N/A |
| `orders/OrderService.java::OrderService.place` | `orders/OrderService.java:55` | 0 | 0 | 0 | N/A |
| `orders/OrderService.java::OrderService.stocked` | `orders/OrderService.java:60` | 0 | 1 | 0 | 1.00 |
| `orders/OrderService.java::OrderService.Factory` | `orders/OrderService.java:67` | 0 | 0 | 0 | N/A |
| `orders/OrderService.java::OrderService.Factory.Factory` | `orders/OrderService.java:70` | 0 | 0 | 0 | N/A |
| `orders/OrderService.java::OrderService.Factory.create` | `orders/OrderService.java:74` | 0 | 0 | 0 | N/A |
| `reporting` | `reporting` | 1 | 3 | 3 | 0.75 |
| `reporting/Report.java` | `reporting/Report.java` | 3 | 1 | 5 | 0.25 |
| `reporting/Report.java::coffee.reporting` | `reporting/Report.java:1` | 0 | 0 | 0 | N/A |
| `reporting/Report.java::Report` | `reporting/Report.java:7` | 3 | 1 | 5 | 0.25 |
| `reporting/Report.java::Report.Report` | `reporting/Report.java:8` | 0 | 0 | 0 | N/A |
| `reporting/Report.java::Report.total` | `reporting/Report.java:10` | 1 | 1 | 8 | 0.50 |
| `reporting/Report.java::Report.render` | `reporting/Report.java:14` | 3 | 1 | 7 | 0.25 |
| `reporting/Report.java::Report.render.<anonymous>` | `reporting/Report.java:16` | 0 | 1 | 0 | 1.00 |
| `reporting/SalesReport.java` | `reporting/SalesReport.java` | 0 | 3 | 0 | 1.00 |
| `reporting/SalesReport.java::coffee.reporting` | `reporting/SalesReport.java:1` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport` | `reporting/SalesReport.java:11` | 0 | 2 | 0 | 1.00 |
| `reporting/SalesReport.java::SalesReport.include` | `reporting/SalesReport.java:13` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport.SalesReport` | `reporting/SalesReport.java:15` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport.totals` | `reporting/SalesReport.java:19` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport.totals.<anonymous>` | `reporting/SalesReport.java:21` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport.totals.<anonymous>.<anonymous>` | `reporting/SalesReport.java:22` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport.totals.<anonymous>` | `reporting/SalesReport.java:26` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport.discounts` | `reporting/SalesReport.java:30` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport.discounts.<anonymous>` | `reporting/SalesReport.java:31` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport.discounts.<anonymous>.<anonymous>` | `reporting/SalesReport.java:32` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.java::SalesReport.summary` | `reporting/SalesReport.java:35` | 0 | 2 | 0 | 1.00 |
| `reporting/SalesReport.java::SalesReport.summary.<anonymous>` | `reporting/SalesReport.java:37` | 0 | 0 | 0 | N/A |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/Recipe.java`
- `reporting/Report.java`

Example cycle: `brewing/Recipe.java` → `reporting/Report.java` → `brewing/Recipe.java`
