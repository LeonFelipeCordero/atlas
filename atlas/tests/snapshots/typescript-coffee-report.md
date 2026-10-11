# Metrics

- files: 9
- modules: 5
- types: 16
- callables: 81
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.ts` | `brewing/Brewer.ts` | 51 | 10 | 10 | 21 |
| `brewing/Recipe.ts` | `brewing/Recipe.ts` | 29 | 5 | 5 | 7 |
| `inventory/Inventory.ts` | `inventory/Inventory.ts` | 53 | 12 | 12 | 19 |
| `ordering/Order.ts` | `ordering/Order.ts` | 37 | 6 | 6 | 6 |
| `ordering/OrderLedger.ts` | `ordering/OrderLedger.ts` | 37 | 11 | 11 | 12 |
| `ordering/OrderService.ts` | `ordering/OrderService.ts` | 41 | 7 | 7 | 8 |
| `ordering/Orders.ts` | `ordering/Orders.ts` | 49 | 15 | 15 | 21 |
| `reporting/Receipt.ts` | `reporting/Receipt.ts` | 39 | 11 | 11 | 13 |
| `reporting/Report.ts` | `reporting/Report.ts` | 12 | 4 | 4 | 4 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.ts::Brewing.brew` | `brewing/Brewer.ts:6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.ts::Brewer.brew` | `brewing/Brewer.ts:10` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.ts::Brewer.brew.<anonymous>` | `brewing/Brewer.ts:12` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.ts::Brewer.retry` | `brewing/Brewer.ts:15` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.ts::Brewer.score` | `brewing/Brewer.ts:20` | 10 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/Brewer.ts::Brewer.classify` | `brewing/Brewer.ts:31` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.ts::Brewer.classify.<anonymous>` | `brewing/Brewer.ts:33` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.ts::Brewer.ready` | `brewing/Brewer.ts:36` | 3 | 4 | 4 | 4 | 0 | 0 | 0 |
| `brewing/Brewer.ts::Brewer.calibrate` | `brewing/Brewer.ts:41` | 4 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.ts::main` | `brewing/Brewer.ts:47` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.ts::Recipe.portions` | `brewing/Recipe.ts:4` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/Recipe.ts::Recipe.price` | `brewing/Recipe.ts:12` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.ts::Recipe.dose` | `brewing/Recipe.ts:17` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.ts::Recipe.describe` | `brewing/Recipe.ts:22` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.ts::Recipe.preview` | `brewing/Recipe.ts:26` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.ts::Inventory.constructor` | `inventory/Inventory.ts:10` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.ts::Inventory.canFill` | `inventory/Inventory.ts:12` | 5 | 1 | 2 | 2 | 0 | 0 | 0 |
| `inventory/Inventory.ts::Inventory.canFill.<anonymous>` | `inventory/Inventory.ts:13` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.ts::Inventory.canFill.<anonymous>` | `inventory/Inventory.ts:14` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.ts::Inventory.reserve` | `inventory/Inventory.ts:18` | 8 | 1 | 3 | 3 | 0 | 0 | 1 |
| `inventory/Inventory.ts::Inventory.restock` | `inventory/Inventory.ts:27` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.ts::remaining` | `inventory/Inventory.ts:34` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.ts::needsDelivery` | `inventory/Inventory.ts:35` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.ts::deliveries` | `inventory/Inventory.ts:38` | 6 | 2 | 2 | 2 | 0 | 0 | 1 |
| `inventory/Inventory.ts::deliveries.shortage` | `inventory/Inventory.ts:39` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.ts::alerts` | `inventory/Inventory.ts:44` | 4 | 1 | 3 | 3 | 0 | 0 | 1 |
| `inventory/Inventory.ts::replenish` | `inventory/Inventory.ts:50` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `ordering/Order.ts::OrderBook.select` | `ordering/Order.ts:21` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Order.ts::OrderBook.onChange` | `ordering/Order.ts:22` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Order.ts::OrderBook."daily-total"` | `ordering/Order.ts:23` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Order.ts::OrderBook.[Symbol.iterator]` | `ordering/Order.ts:24` | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Order.ts::OrderBook.find` | `ordering/Order.ts:25` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Order.ts::OrderBook.find` | `ordering/Order.ts:26` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger.constructor` | `ordering/OrderLedger.ts:7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger.count` | `ordering/OrderLedger.ts:9` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger.select` | `ordering/OrderLedger.ts:13` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger."daily-total"` | `ordering/OrderLedger.ts:17` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger."daily-total".<anonymous>` | `ordering/OrderLedger.ts:18` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger.[Symbol.iterator]` | `ordering/OrderLedger.ts:21` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger.find` | `ordering/OrderLedger.ts:25` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger.find` | `ordering/OrderLedger.ts:26` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger.find` | `ordering/OrderLedger.ts:27` | 3 | 1 | 2 | 2 | 0 | 0 | 1 |
| `ordering/OrderLedger.ts::OrderLedger.find.<anonymous>` | `ordering/OrderLedger.ts:28` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderLedger.ts::OrderLedger.add` | `ordering/OrderLedger.ts:31` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.ts::OrderService.constructor` | `ordering/OrderService.ts:11` | 5 | 3 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.ts::OrderService.fulfill` | `ordering/OrderService.ts:17` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `ordering/OrderService.ts::OrderService.fulfill.<anonymous>` | `ordering/OrderService.ts:19` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.ts::OrderService.describe` | `ordering/OrderService.ts:25` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.ts::OrderService.describe.<anonymous>` | `ordering/OrderService.ts:26` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.ts::morningOrder` | `ordering/OrderService.ts:30` | 6 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.ts::checkStock` | `ordering/OrderService.ts:37` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::priceOrder` | `ordering/Orders.ts:4` | 7 | 3 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::priceOrder.lineTotal` | `ordering/Orders.ts:5` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::priceOrder.<anonymous>` | `ordering/Orders.ts:8` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::priceOrder.<anonymous>` | `ordering/Orders.ts:9` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::createOrder` | `ordering/Orders.ts:12` | 3 | 4 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::drinkTickets` | `ordering/Orders.ts:16` | 8 | 1 | 3 | 4 | 0 | 1 | 2 |
| `ordering/Orders.ts::drinkTickets.ticket` | `ordering/Orders.ts:17` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::pickupQueue` | `ordering/Orders.ts:25` | 5 | 2 | 3 | 3 | 0 | 0 | 2 |
| `ordering/Orders.ts::quote` | `ordering/Orders.ts:31` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::quote` | `ordering/Orders.ts:32` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::quote` | `ordering/Orders.ts:33` | 5 | 2 | 2 | 2 | 0 | 0 | 1 |
| `ordering/Orders.ts::quoteWithFees` | `ordering/Orders.ts:39` | 3 | 3 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::groupTickets` | `ordering/Orders.ts:43` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::groupTickets.<anonymous>.<anonymous>` | `ordering/Orders.ts:44` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.ts::groupTickets.<anonymous>` | `ordering/Orders.ts:44` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.ts::ReceiptFormatters.header` | `reporting/Receipt.ts:6` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.ts::ReceiptFormatters.money` | `reporting/Receipt.ts:7` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.ts::ReceiptFormatters.items` | `reporting/Receipt.ts:8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.ts::ReceiptFormatters.totals` | `reporting/Receipt.ts:9` | 1 | 3 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.ts::header` | `reporting/Receipt.ts:14` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.ts::money` | `reporting/Receipt.ts:15` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.ts::items` | `reporting/Receipt.ts:18` | 6 | 1 | 2 | 2 | 0 | 0 | 1 |
| `reporting/Receipt.ts::items.describe` | `reporting/Receipt.ts:19` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.ts::totals` | `reporting/Receipt.ts:24` | 4 | 3 | 2 | 2 | 0 | 0 | 1 |
| `reporting/Receipt.ts::Receipt.constructor` | `reporting/Receipt.ts:30` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.ts::Receipt.render` | `reporting/Receipt.ts:32` | 7 | 3 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.ts::Report.total` | `reporting/Report.ts:4` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.ts::Report.total.<anonymous>` | `reporting/Report.ts:5` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.ts::Report.render` | `reporting/Report.ts:8` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.ts::Report.render.<anonymous>` | `reporting/Report.ts:9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `typescript` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 3 | 1 | 3 | 0.25 |
| `brewing/Brewer.ts` | `brewing/Brewer.ts` | 1 | 2 | 1 | 0.67 |
| `brewing/Brewer.ts::Brewing` | `brewing/Brewer.ts:5` | 1 | 0 | 2 | 0.00 |
| `brewing/Brewer.ts::Brewing.brew` | `brewing/Brewer.ts:6` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::Brewer` | `brewing/Brewer.ts:9` | 1 | 3 | 1 | 0.75 |
| `brewing/Brewer.ts::Brewer.brew` | `brewing/Brewer.ts:10` | 2 | 1 | 3 | 0.33 |
| `brewing/Brewer.ts::Brewer.brew.<anonymous>` | `brewing/Brewer.ts:12` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.ts::Brewer.retry` | `brewing/Brewer.ts:15` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::Brewer.score` | `brewing/Brewer.ts:20` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.ts::Brewer.classify` | `brewing/Brewer.ts:31` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::Brewer.classify.<anonymous>` | `brewing/Brewer.ts:33` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::Brewer.ready` | `brewing/Brewer.ts:36` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::Brewer.calibrate` | `brewing/Brewer.ts:41` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.ts::main` | `brewing/Brewer.ts:47` | 0 | 1 | 0 | 1.00 |
| `brewing/Recipe.ts` | `brewing/Recipe.ts` | 6 | 1 | 7 | 0.14 |
| `brewing/Recipe.ts::Recipe` | `brewing/Recipe.ts:3` | 4 | 1 | 4 | 0.20 |
| `brewing/Recipe.ts::Recipe.portions` | `brewing/Recipe.ts:4` | 4 | 0 | 4 | 0.00 |
| `brewing/Recipe.ts::Recipe.price` | `brewing/Recipe.ts:12` | 3 | 0 | 5 | 0.00 |
| `brewing/Recipe.ts::Recipe.dose` | `brewing/Recipe.ts:17` | 4 | 0 | 9 | 0.00 |
| `brewing/Recipe.ts::Recipe.describe` | `brewing/Recipe.ts:22` | 1 | 1 | 1 | 0.50 |
| `brewing/Recipe.ts::Recipe.preview` | `brewing/Recipe.ts:26` | 0 | 1 | 0 | 1.00 |
| `inventory` | `inventory` | 1 | 2 | 3 | 0.67 |
| `inventory/Inventory.ts` | `inventory/Inventory.ts` | 1 | 2 | 1 | 0.67 |
| `inventory/Inventory.ts::Delivery` | `inventory/Inventory.ts:4` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.ts::Inventory` | `inventory/Inventory.ts:9` | 1 | 1 | 1 | 0.50 |
| `inventory/Inventory.ts::Inventory.constructor` | `inventory/Inventory.ts:10` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.ts::Inventory.canFill` | `inventory/Inventory.ts:12` | 2 | 0 | 4 | 0.00 |
| `inventory/Inventory.ts::Inventory.canFill.<anonymous>` | `inventory/Inventory.ts:13` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.ts::Inventory.canFill.<anonymous>` | `inventory/Inventory.ts:14` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.ts::Inventory.reserve` | `inventory/Inventory.ts:18` | 1 | 2 | 2 | 0.67 |
| `inventory/Inventory.ts::Inventory.restock` | `inventory/Inventory.ts:27` | 2 | 0 | 2 | 0.00 |
| `inventory/Inventory.ts::remaining` | `inventory/Inventory.ts:34` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.ts::needsDelivery` | `inventory/Inventory.ts:35` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.ts::deliveries` | `inventory/Inventory.ts:38` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.ts::deliveries.shortage` | `inventory/Inventory.ts:39` | 1 | 0 | 1 | 0.00 |
| `inventory/Inventory.ts::alerts` | `inventory/Inventory.ts:44` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.ts::replenish` | `inventory/Inventory.ts:50` | 0 | 1 | 0 | 1.00 |
| `ordering` | `ordering` | 2 | 3 | 3 | 0.60 |
| `ordering/Order.ts` | `ordering/Order.ts` | 5 | 0 | 5 | 0.00 |
| `ordering/Order.ts::OrderItem` | `ordering/Order.ts:1` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::Order` | `ordering/Order.ts:6` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::Ticket` | `ordering/Order.ts:14` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::OrderBook` | `ordering/Order.ts:20` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::OrderBook.select` | `ordering/Order.ts:21` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::OrderBook.onChange` | `ordering/Order.ts:22` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::OrderBook."daily-total"` | `ordering/Order.ts:23` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::OrderBook.[Symbol.iterator]` | `ordering/Order.ts:24` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::OrderBook.find` | `ordering/Order.ts:25` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::OrderBook.find` | `ordering/Order.ts:26` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::PricingContext` | `ordering/Order.ts:30` | 0 | 0 | 0 | N/A |
| `ordering/Order.ts::OrderBookProvider` | `ordering/Order.ts:34` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts` | `ordering/OrderLedger.ts` | 0 | 2 | 0 | 1.00 |
| `ordering/OrderLedger.ts::OrderLedger` | `ordering/OrderLedger.ts:4` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger.constructor` | `ordering/OrderLedger.ts:7` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger.count` | `ordering/OrderLedger.ts:9` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger.select` | `ordering/OrderLedger.ts:13` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger."daily-total"` | `ordering/OrderLedger.ts:17` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger."daily-total".<anonymous>` | `ordering/OrderLedger.ts:18` | 0 | 1 | 0 | 1.00 |
| `ordering/OrderLedger.ts::OrderLedger.[Symbol.iterator]` | `ordering/OrderLedger.ts:21` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger.find` | `ordering/OrderLedger.ts:25` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger.find` | `ordering/OrderLedger.ts:26` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger.find` | `ordering/OrderLedger.ts:27` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger.find.<anonymous>` | `ordering/OrderLedger.ts:28` | 0 | 0 | 0 | N/A |
| `ordering/OrderLedger.ts::OrderLedger.add` | `ordering/OrderLedger.ts:31` | 0 | 0 | 0 | N/A |
| `ordering/OrderService.ts` | `ordering/OrderService.ts` | 0 | 6 | 0 | 1.00 |
| `ordering/OrderService.ts::OrderService` | `ordering/OrderService.ts:8` | 0 | 4 | 0 | 1.00 |
| `ordering/OrderService.ts::OrderService.constructor` | `ordering/OrderService.ts:11` | 0 | 0 | 0 | N/A |
| `ordering/OrderService.ts::OrderService.fulfill` | `ordering/OrderService.ts:17` | 1 | 4 | 1 | 0.80 |
| `ordering/OrderService.ts::OrderService.fulfill.<anonymous>` | `ordering/OrderService.ts:19` | 0 | 0 | 0 | N/A |
| `ordering/OrderService.ts::OrderService.describe` | `ordering/OrderService.ts:25` | 0 | 0 | 0 | N/A |
| `ordering/OrderService.ts::OrderService.describe.<anonymous>` | `ordering/OrderService.ts:26` | 0 | 1 | 0 | 1.00 |
| `ordering/OrderService.ts::morningOrder` | `ordering/OrderService.ts:30` | 0 | 3 | 0 | 1.00 |
| `ordering/OrderService.ts::checkStock` | `ordering/OrderService.ts:37` | 0 | 1 | 0 | 1.00 |
| `ordering/Orders.ts` | `ordering/Orders.ts` | 3 | 2 | 3 | 0.40 |
| `ordering/Orders.ts::priceOrder` | `ordering/Orders.ts:4` | 4 | 0 | 4 | 0.00 |
| `ordering/Orders.ts::priceOrder.lineTotal` | `ordering/Orders.ts:5` | 1 | 1 | 1 | 0.50 |
| `ordering/Orders.ts::priceOrder.<anonymous>` | `ordering/Orders.ts:8` | 0 | 1 | 0 | 1.00 |
| `ordering/Orders.ts::priceOrder.<anonymous>` | `ordering/Orders.ts:9` | 0 | 0 | 0 | N/A |
| `ordering/Orders.ts::createOrder` | `ordering/Orders.ts:12` | 1 | 0 | 1 | 0.00 |
| `ordering/Orders.ts::drinkTickets` | `ordering/Orders.ts:16` | 2 | 1 | 3 | 0.33 |
| `ordering/Orders.ts::drinkTickets.ticket` | `ordering/Orders.ts:17` | 1 | 1 | 4 | 0.50 |
| `ordering/Orders.ts::pickupQueue` | `ordering/Orders.ts:25` | 0 | 0 | 0 | N/A |
| `ordering/Orders.ts::quote` | `ordering/Orders.ts:31` | 0 | 0 | 0 | N/A |
| `ordering/Orders.ts::quote` | `ordering/Orders.ts:32` | 0 | 0 | 0 | N/A |
| `ordering/Orders.ts::quote` | `ordering/Orders.ts:33` | 0 | 2 | 0 | 1.00 |
| `ordering/Orders.ts::quoteWithFees` | `ordering/Orders.ts:39` | 0 | 1 | 0 | 1.00 |
| `ordering/Orders.ts::groupTickets` | `ordering/Orders.ts:43` | 0 | 0 | 0 | N/A |
| `ordering/Orders.ts::groupTickets.<anonymous>.<anonymous>` | `ordering/Orders.ts:44` | 0 | 0 | 0 | N/A |
| `ordering/Orders.ts::groupTickets.<anonymous>` | `ordering/Orders.ts:44` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 2 | 2 | 3 | 0.50 |
| `reporting/Receipt.ts` | `reporting/Receipt.ts` | 1 | 3 | 1 | 0.75 |
| `reporting/Receipt.ts::ReceiptFormatters` | `reporting/Receipt.ts:5` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.ts::ReceiptFormatters.header` | `reporting/Receipt.ts:6` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.ts::ReceiptFormatters.money` | `reporting/Receipt.ts:7` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.ts::ReceiptFormatters.items` | `reporting/Receipt.ts:8` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.ts::ReceiptFormatters.totals` | `reporting/Receipt.ts:9` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.ts::header` | `reporting/Receipt.ts:14` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.ts::money` | `reporting/Receipt.ts:15` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.ts::items` | `reporting/Receipt.ts:18` | 0 | 1 | 0 | 1.00 |
| `reporting/Receipt.ts::items.describe` | `reporting/Receipt.ts:19` | 1 | 1 | 1 | 0.50 |
| `reporting/Receipt.ts::totals` | `reporting/Receipt.ts:24` | 0 | 1 | 0 | 1.00 |
| `reporting/Receipt.ts::Receipt` | `reporting/Receipt.ts:29` | 1 | 0 | 1 | 0.00 |
| `reporting/Receipt.ts::Receipt.constructor` | `reporting/Receipt.ts:30` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.ts::Receipt.render` | `reporting/Receipt.ts:32` | 1 | 0 | 2 | 0.00 |
| `reporting/Report.ts` | `reporting/Report.ts` | 2 | 1 | 7 | 0.33 |
| `reporting/Report.ts::Report` | `reporting/Report.ts:3` | 2 | 1 | 4 | 0.33 |
| `reporting/Report.ts::Report.total` | `reporting/Report.ts:4` | 1 | 0 | 6 | 0.00 |
| `reporting/Report.ts::Report.total.<anonymous>` | `reporting/Report.ts:5` | 0 | 1 | 0 | 1.00 |
| `reporting/Report.ts::Report.render` | `reporting/Report.ts:8` | 2 | 1 | 5 | 0.33 |
| `reporting/Report.ts::Report.render.<anonymous>` | `reporting/Report.ts:9` | 0 | 1 | 0 | 1.00 |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.

## Circular imports

### Group 1

Files: 2. Internal dependencies: 2.
- `brewing/Recipe.ts`
- `reporting/Report.ts`

Example cycle: `brewing/Recipe.ts` → `reporting/Report.ts` → `brewing/Recipe.ts`
