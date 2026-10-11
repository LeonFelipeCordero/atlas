# Metrics

- files: 7
- modules: 12
- types: 16
- callables: 60
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.kt` | `brewing/Brewer.kt` | 61 | 9 | 9 | 28 |
| `brewing/Recipe.kt` | `brewing/Recipe.kt` | 11 | 2 | 2 | 4 |
| `inventory/Inventory.kt` | `inventory/Inventory.kt` | 54 | 11 | 11 | 14 |
| `orders/Order.kt` | `orders/Order.kt` | 37 | 9 | 9 | 12 |
| `orders/OrderService.kt` | `orders/OrderService.kt` | 58 | 12 | 12 | 16 |
| `reporting/Report.kt` | `reporting/Report.kt` | 9 | 3 | 3 | 3 |
| `reporting/SalesReport.kt` | `reporting/SalesReport.kt` | 45 | 14 | 14 | 15 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.kt::CoffeeMaker.brew` | `brewing/Brewer.kt:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.kt::Brewer.brew` | `brewing/Brewer.kt:11` | 5 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.kt::Brewer.brew.<anonymous>` | `brewing/Brewer.kt:13` | 1 | N/A | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.kt::Brewer.retry` | `brewing/Brewer.kt:17` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.kt::Brewer.score` | `brewing/Brewer.kt:22` | 10 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/Brewer.kt::Brewer.classify` | `brewing/Brewer.kt:34` | 12 | 1 | 9 | 9 | 0 | 0 | 1 |
| `brewing/Brewer.kt::Brewer.ready` | `brewing/Brewer.kt:47` | 3 | 4 | 4 | 4 | 0 | 0 | 0 |
| `brewing/Brewer.kt::Brewer.calibrate` | `brewing/Brewer.kt:51` | 5 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.kt::main` | `brewing/Brewer.kt:58` | 4 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.kt::portions` | `brewing/Recipe.kt:5` | 5 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/Recipe.kt::preview` | `brewing/Recipe.kt:11` | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::StockLedger.record` | `inventory/Inventory.kt:9` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::StockLedger.snapshot` | `inventory/Inventory.kt:13` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::Reservable.reserve` | `inventory/Inventory.kt:17` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::Inventory.record` | `inventory/Inventory.kt:24` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::Inventory.receive` | `inventory/Inventory.kt:29` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::Inventory.receive.<anonymous>` | `inventory/Inventory.kt:30` | 1 | N/A | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::Inventory.reserve` | `inventory/Inventory.kt:33` | 11 | 1 | 4 | 4 | 0 | 0 | 2 |
| `inventory/Inventory.kt::Inventory.reserve.<anonymous>` | `inventory/Inventory.kt:40` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::Inventory.reserve.<anonymous>` | `inventory/Inventory.kt:41` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::Inventory.units` | `inventory/Inventory.kt:45` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.kt::Inventory.Companion.stocked` | `inventory/Inventory.kt:48` | 5 | 2 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.kt::OrderLine.subtotal` | `orders/Order.kt:8` | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.kt::OrderLine.Factory.espresso` | `orders/Order.kt:11` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.kt::Order.total.<anonymous>` | `orders/Order.kt:21` | 1 | N/A | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.kt::Order.total` | `orders/Order.kt:21` | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.kt::Order.names.<anonymous>.<anonymous>` | `orders/Order.kt:23` | 1 | N/A | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.kt::Order.names.<anonymous>` | `orders/Order.kt:23` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.kt::Order.names` | `orders/Order.kt:23` | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| `orders/Order.kt::Order.transition` | `orders/Order.kt:25` | 10 | 1 | 4 | 4 | 0 | 0 | 1 |
| `orders/Order.kt::receipt` | `orders/Order.kt:37` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.kt::CoffeeOrders.fulfill` | `orders/OrderService.kt:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.kt::OrderService.<anonymous>` | `orders/OrderService.kt:13` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.kt::OrderService.place` | `orders/OrderService.kt:17` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.kt::OrderService.place` | `orders/OrderService.kt:21` | 7 | 4 | 2 | 2 | 0 | 0 | 1 |
| `orders/OrderService.kt::OrderService.fulfill` | `orders/OrderService.kt:29` | 6 | 1 | 2 | 2 | 0 | 0 | 1 |
| `orders/OrderService.kt::OrderService.preview` | `orders/OrderService.kt:36` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.kt::OrderService.receipts.<anonymous>` | `orders/OrderService.kt:38` | 1 | N/A | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.kt::OrderService.receipts` | `orders/OrderService.kt:38` | 6 | 1 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.kt::OrderService.receipts.formatReady` | `orders/OrderService.kt:39` | 3 | 1 | 2 | 2 | 0 | 0 | 1 |
| `orders/OrderService.kt::OrderService.notify` | `orders/OrderService.kt:45` | 3 | 1 | 2 | 2 | 0 | 0 | 1 |
| `orders/OrderService.kt::OrderService.place` | `orders/OrderService.kt:49` | 2 | 2 | 1 | 1 | 0 | 0 | 0 |
| `orders/OrderService.kt::OrderService.Companion.stocked` | `orders/OrderService.kt:53` | 4 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.kt::render` | `reporting/Report.kt:5` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.kt::render.<anonymous>` | `reporting/Report.kt:6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.kt::render.<anonymous>` | `reporting/Report.kt:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.<anonymous>` | `reporting/SalesReport.kt:12` | 1 | N/A | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.totals` | `reporting/SalesReport.kt:14` | 11 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.totals.<anonymous>` | `reporting/SalesReport.kt:16` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `reporting/SalesReport.kt::SalesReport.totals.<anonymous>.add` | `reporting/SalesReport.kt:18` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.totals.<anonymous>` | `reporting/SalesReport.kt:23` | 1 | N/A | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.discounts` | `reporting/SalesReport.kt:26` | 5 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.discounts.<anonymous>` | `reporting/SalesReport.kt:27` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.discounts.<anonymous>.<anonymous>` | `reporting/SalesReport.kt:28` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.projected` | `reporting/SalesReport.kt:32` | 6 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.projected.<anonymous>` | `reporting/SalesReport.kt:33` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.projected.<anonymous>` | `reporting/SalesReport.kt:36` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.résumé` | `reporting/SalesReport.kt:39` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.résumé.<anonymous>` | `reporting/SalesReport.kt:40` | 1 | N/A | 1 | 1 | 0 | 0 | 0 |
| `reporting/SalesReport.kt::SalesReport.résumé` | `reporting/SalesReport.kt:44` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `kotlin` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 3 | 1 | 3 | 0.25 |
| `brewing/Brewer.kt` | `brewing/Brewer.kt` | 1 | 2 | 1 | 0.67 |
| `brewing/Brewer.kt::coffee.brewing` | `brewing/Brewer.kt:1` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::CoffeeMaker` | `brewing/Brewer.kt:6` | 1 | 0 | 3 | 0.00 |
| `brewing/Brewer.kt::CoffeeMaker.brew` | `brewing/Brewer.kt:7` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::Brewer` | `brewing/Brewer.kt:10` | 1 | 1 | 2 | 0.50 |
| `brewing/Brewer.kt::Brewer.brew` | `brewing/Brewer.kt:11` | 3 | 1 | 4 | 0.25 |
| `brewing/Brewer.kt::Brewer.brew.<anonymous>` | `brewing/Brewer.kt:13` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.kt::Brewer.retry` | `brewing/Brewer.kt:17` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::Brewer.score` | `brewing/Brewer.kt:22` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.kt::Brewer.classify` | `brewing/Brewer.kt:34` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::Brewer.ready` | `brewing/Brewer.kt:47` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::Brewer.calibrate` | `brewing/Brewer.kt:51` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.kt::main` | `brewing/Brewer.kt:58` | 0 | 1 | 0 | 1.00 |
| `brewing/Recipe.kt` | `brewing/Recipe.kt` | 3 | 1 | 6 | 0.25 |
| `brewing/Recipe.kt::coffee.brewing` | `brewing/Recipe.kt:1` | 0 | 0 | 0 | N/A |
| `brewing/Recipe.kt::portions` | `brewing/Recipe.kt:5` | 5 | 0 | 5 | 0.00 |
| `brewing/Recipe.kt::preview` | `brewing/Recipe.kt:11` | 0 | 1 | 0 | 1.00 |
| `inventory` | `inventory` | 2 | 2 | 3 | 0.50 |
| `inventory/Inventory.kt` | `inventory/Inventory.kt` | 2 | 2 | 2 | 0.50 |
| `inventory/Inventory.kt::coffee.inventory` | `inventory/Inventory.kt:1` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.kt::StockLedger` | `inventory/Inventory.kt:6` | 1 | 0 | 3 | 0.00 |
| `inventory/Inventory.kt::StockLedger.record` | `inventory/Inventory.kt:9` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.kt::StockLedger.snapshot` | `inventory/Inventory.kt:13` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.kt::Reservable` | `inventory/Inventory.kt:16` | 1 | 0 | 3 | 0.00 |
| `inventory/Inventory.kt::Reservable.reserve` | `inventory/Inventory.kt:17` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.kt::Inventory` | `inventory/Inventory.kt:20` | 2 | 3 | 2 | 0.60 |
| `inventory/Inventory.kt::Inventory.Change` | `inventory/Inventory.kt:22` | 2 | 0 | 3 | 0.00 |
| `inventory/Inventory.kt::Inventory.record` | `inventory/Inventory.kt:24` | 2 | 1 | 2 | 0.33 |
| `inventory/Inventory.kt::Inventory.receive` | `inventory/Inventory.kt:29` | 1 | 0 | 1 | 0.00 |
| `inventory/Inventory.kt::Inventory.receive.<anonymous>` | `inventory/Inventory.kt:30` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.kt::Inventory.reserve` | `inventory/Inventory.kt:33` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.kt::Inventory.reserve.<anonymous>` | `inventory/Inventory.kt:40` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.kt::Inventory.reserve.<anonymous>` | `inventory/Inventory.kt:41` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.kt::Inventory.units` | `inventory/Inventory.kt:45` | 3 | 0 | 5 | 0.00 |
| `inventory/Inventory.kt::Inventory.Companion` | `inventory/Inventory.kt:47` | 0 | 2 | 0 | 1.00 |
| `inventory/Inventory.kt::Inventory.Companion.stocked` | `inventory/Inventory.kt:48` | 0 | 1 | 0 | 1.00 |
| `orders` | `orders` | 2 | 3 | 3 | 0.60 |
| `orders/Order.kt` | `orders/Order.kt` | 3 | 1 | 3 | 0.25 |
| `orders/Order.kt::coffee.orders` | `orders/Order.kt:1` | 0 | 0 | 0 | N/A |
| `orders/Order.kt::OrderStatus` | `orders/Order.kt:5` | 0 | 0 | 0 | N/A |
| `orders/Order.kt::OrderLine` | `orders/Order.kt:7` | 3 | 0 | 4 | 0.00 |
| `orders/Order.kt::OrderLine.subtotal` | `orders/Order.kt:8` | 2 | 0 | 3 | 0.00 |
| `orders/Order.kt::OrderLine.Factory` | `orders/Order.kt:10` | 0 | 1 | 0 | 1.00 |
| `orders/Order.kt::OrderLine.Factory.espresso` | `orders/Order.kt:11` | 0 | 0 | 0 | N/A |
| `orders/Order.kt::Order` | `orders/Order.kt:15` | 1 | 0 | 2 | 0.00 |
| `orders/Order.kt::Order.total.<anonymous>` | `orders/Order.kt:21` | 0 | 0 | 0 | N/A |
| `orders/Order.kt::Order.total` | `orders/Order.kt:21` | 0 | 0 | 0 | N/A |
| `orders/Order.kt::Order.names.<anonymous>.<anonymous>` | `orders/Order.kt:23` | 0 | 0 | 0 | N/A |
| `orders/Order.kt::Order.names.<anonymous>` | `orders/Order.kt:23` | 0 | 0 | 0 | N/A |
| `orders/Order.kt::Order.names` | `orders/Order.kt:23` | 3 | 0 | 4 | 0.00 |
| `orders/Order.kt::Order.transition` | `orders/Order.kt:25` | 1 | 0 | 2 | 0.00 |
| `orders/Order.kt::receipt` | `orders/Order.kt:37` | 0 | 2 | 0 | 1.00 |
| `orders/OrderService.kt` | `orders/OrderService.kt` | 0 | 3 | 0 | 1.00 |
| `orders/OrderService.kt::coffee.orders` | `orders/OrderService.kt:1` | 0 | 0 | 0 | N/A |
| `orders/OrderService.kt::CoffeeOrders` | `orders/OrderService.kt:6` | 1 | 0 | 2 | 0.00 |
| `orders/OrderService.kt::CoffeeOrders.fulfill` | `orders/OrderService.kt:7` | 0 | 0 | 0 | N/A |
| `orders/OrderService.kt::OrderService` | `orders/OrderService.kt:10` | 1 | 4 | 1 | 0.80 |
| `orders/OrderService.kt::OrderService.<anonymous>` | `orders/OrderService.kt:13` | 0 | 0 | 0 | N/A |
| `orders/OrderService.kt::OrderService.place` | `orders/OrderService.kt:17` | 0 | 0 | 0 | N/A |
| `orders/OrderService.kt::OrderService.place` | `orders/OrderService.kt:21` | 0 | 1 | 0 | 1.00 |
| `orders/OrderService.kt::OrderService.fulfill` | `orders/OrderService.kt:29` | 1 | 3 | 1 | 0.75 |
| `orders/OrderService.kt::OrderService.preview` | `orders/OrderService.kt:36` | 0 | 2 | 0 | 1.00 |
| `orders/OrderService.kt::OrderService.receipts.<anonymous>` | `orders/OrderService.kt:38` | 0 | 0 | 0 | N/A |
| `orders/OrderService.kt::OrderService.receipts` | `orders/OrderService.kt:38` | 1 | 1 | 1 | 0.50 |
| `orders/OrderService.kt::OrderService.receipts.formatReady` | `orders/OrderService.kt:39` | 1 | 0 | 2 | 0.00 |
| `orders/OrderService.kt::OrderService.notify` | `orders/OrderService.kt:45` | 0 | 1 | 0 | 1.00 |
| `orders/OrderService.kt::OrderService.place` | `orders/OrderService.kt:49` | 0 | 0 | 0 | N/A |
| `orders/OrderService.kt::OrderService.Companion` | `orders/OrderService.kt:52` | 0 | 1 | 0 | 1.00 |
| `orders/OrderService.kt::OrderService.Companion.stocked` | `orders/OrderService.kt:53` | 0 | 0 | 0 | N/A |
| `reporting` | `reporting` | 2 | 3 | 3 | 0.60 |
| `reporting/Report.kt` | `reporting/Report.kt` | 4 | 1 | 6 | 0.20 |
| `reporting/Report.kt::coffee.reporting` | `reporting/Report.kt:1` | 0 | 0 | 0 | N/A |
| `reporting/Report.kt::render` | `reporting/Report.kt:5` | 4 | 0 | 8 | 0.00 |
| `reporting/Report.kt::render.<anonymous>` | `reporting/Report.kt:6` | 0 | 1 | 0 | 1.00 |
| `reporting/Report.kt::render.<anonymous>` | `reporting/Report.kt:7` | 0 | 1 | 0 | 1.00 |
| `reporting/SalesReport.kt` | `reporting/SalesReport.kt` | 0 | 3 | 0 | 1.00 |
| `reporting/SalesReport.kt::coffee.reporting` | `reporting/SalesReport.kt:1` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::OrderFilter` | `reporting/SalesReport.kt:9` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport` | `reporting/SalesReport.kt:11` | 0 | 2 | 0 | 1.00 |
| `reporting/SalesReport.kt::SalesReport.<anonymous>` | `reporting/SalesReport.kt:12` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport.totals` | `reporting/SalesReport.kt:14` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport.totals.<anonymous>` | `reporting/SalesReport.kt:16` | 0 | 1 | 0 | 1.00 |
| `reporting/SalesReport.kt::SalesReport.totals.<anonymous>.add` | `reporting/SalesReport.kt:18` | 1 | 1 | 1 | 0.50 |
| `reporting/SalesReport.kt::SalesReport.totals.<anonymous>` | `reporting/SalesReport.kt:23` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport.discounts` | `reporting/SalesReport.kt:26` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport.discounts.<anonymous>` | `reporting/SalesReport.kt:27` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport.discounts.<anonymous>.<anonymous>` | `reporting/SalesReport.kt:28` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport.projected` | `reporting/SalesReport.kt:32` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport.projected.<anonymous>` | `reporting/SalesReport.kt:33` | 0 | 1 | 0 | 1.00 |
| `reporting/SalesReport.kt::SalesReport.projected.<anonymous>` | `reporting/SalesReport.kt:36` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport.résumé` | `reporting/SalesReport.kt:39` | 0 | 2 | 0 | 1.00 |
| `reporting/SalesReport.kt::SalesReport.résumé.<anonymous>` | `reporting/SalesReport.kt:40` | 0 | 0 | 0 | N/A |
| `reporting/SalesReport.kt::SalesReport.résumé` | `reporting/SalesReport.kt:44` | 0 | 0 | 0 | N/A |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/Recipe.kt`
- `reporting/Report.kt`

Example cycle: `brewing/Recipe.kt` → `reporting/Report.kt` → `brewing/Recipe.kt`
