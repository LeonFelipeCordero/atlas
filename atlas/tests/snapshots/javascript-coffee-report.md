# Metrics

- files: 7
- modules: 5
- types: 7
- callables: 55
- circularImportGroups: 1
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.js` | `brewing/Brewer.js` | 53 | 10 | 10 | 21 |
| `brewing/Recipe.js` | `brewing/Recipe.js` | 27 | 5 | 5 | 7 |
| `inventory/Inventory.js` | `inventory/Inventory.js` | 50 | 12 | 12 | 19 |
| `ordering/OrderService.js` | `ordering/OrderService.js` | 35 | 6 | 6 | 7 |
| `ordering/Orders.js` | `ordering/Orders.js` | 36 | 11 | 11 | 16 |
| `reporting/Receipt.js` | `reporting/Receipt.js` | 33 | 7 | 7 | 9 |
| `reporting/Report.js` | `reporting/Report.js` | 12 | 4 | 4 | 4 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `brewing/Brewer.js::Brewing.brew` | `brewing/Brewer.js:6` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.js::Brewer.brew` | `brewing/Brewer.js:12` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.js::Brewer.brew.<anonymous>` | `brewing/Brewer.js:14` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.js::Brewer.retry` | `brewing/Brewer.js:17` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `brewing/Brewer.js::Brewer.score` | `brewing/Brewer.js:22` | 10 | 1 | 5 | 7 | 1 | 1 | 3 |
| `brewing/Brewer.js::Brewer.classify` | `brewing/Brewer.js:33` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.js::Brewer.classify.<anonymous>` | `brewing/Brewer.js:35` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.js::Brewer.ready` | `brewing/Brewer.js:38` | 3 | 4 | 4 | 4 | 0 | 0 | 0 |
| `brewing/Brewer.js::Brewer.calibrate` | `brewing/Brewer.js:43` | 4 | 8 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Brewer.js::main` | `brewing/Brewer.js:49` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.js::Recipe.portions` | `brewing/Recipe.js:4` | 7 | 1 | 3 | 3 | 0 | 0 | 1 |
| `brewing/Recipe.js::Recipe.price` | `brewing/Recipe.js:12` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.js::Recipe.dose` | `brewing/Recipe.js:16` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.js::Recipe.describe` | `brewing/Recipe.js:20` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `brewing/Recipe.js::Recipe.preview` | `brewing/Recipe.js:24` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.js::Inventory.constructor` | `inventory/Inventory.js:4` | 4 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.js::Inventory.canFill` | `inventory/Inventory.js:9` | 5 | 1 | 2 | 2 | 0 | 0 | 0 |
| `inventory/Inventory.js::Inventory.canFill.<anonymous>` | `inventory/Inventory.js:10` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.js::Inventory.canFill.<anonymous>` | `inventory/Inventory.js:11` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.js::Inventory.reserve` | `inventory/Inventory.js:15` | 8 | 1 | 3 | 3 | 0 | 0 | 1 |
| `inventory/Inventory.js::Inventory.restock` | `inventory/Inventory.js:24` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.js::remaining` | `inventory/Inventory.js:31` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.js::needsDelivery` | `inventory/Inventory.js:32` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.js::deliveries` | `inventory/Inventory.js:35` | 6 | 2 | 2 | 2 | 0 | 0 | 1 |
| `inventory/Inventory.js::deliveries.shortage` | `inventory/Inventory.js:36` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `inventory/Inventory.js::alerts` | `inventory/Inventory.js:41` | 4 | 1 | 3 | 3 | 0 | 0 | 1 |
| `inventory/Inventory.js::replenish` | `inventory/Inventory.js:47` | 4 | 1 | 2 | 2 | 0 | 0 | 1 |
| `ordering/OrderService.js::OrderService.constructor` | `ordering/OrderService.js:8` | 6 | 3 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.js::OrderService.fulfill` | `ordering/OrderService.js:15` | 7 | 1 | 2 | 2 | 0 | 0 | 1 |
| `ordering/OrderService.js::OrderService.fulfill.<anonymous>` | `ordering/OrderService.js:17` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.js::OrderService.describe` | `ordering/OrderService.js:23` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.js::OrderService.describe.<anonymous>` | `ordering/OrderService.js:24` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/OrderService.js::morningOrder` | `ordering/OrderService.js:28` | 6 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.js::priceOrder` | `ordering/Orders.js:3` | 7 | 3 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.js::priceOrder.lineTotal` | `ordering/Orders.js:4` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.js::priceOrder.<anonymous>` | `ordering/Orders.js:7` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.js::priceOrder.<anonymous>` | `ordering/Orders.js:8` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.js::createOrder` | `ordering/Orders.js:11` | 3 | 3 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.js::drinkTickets` | `ordering/Orders.js:15` | 8 | 1 | 3 | 4 | 0 | 1 | 2 |
| `ordering/Orders.js::drinkTickets.ticket` | `ordering/Orders.js:16` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.js::pickupQueue` | `ordering/Orders.js:24` | 5 | 2 | 3 | 3 | 0 | 0 | 2 |
| `ordering/Orders.js::groupTickets` | `ordering/Orders.js:30` | 5 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.js::groupTickets.<anonymous>.<anonymous>` | `ordering/Orders.js:31` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `ordering/Orders.js::groupTickets.<anonymous>` | `ordering/Orders.js:31` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.js::header` | `reporting/Receipt.js:6` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.js::money` | `reporting/Receipt.js:7` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.js::items` | `reporting/Receipt.js:10` | 6 | 1 | 2 | 2 | 0 | 0 | 1 |
| `reporting/Receipt.js::items.describe` | `reporting/Receipt.js:11` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.js::totals` | `reporting/Receipt.js:16` | 4 | 3 | 2 | 2 | 0 | 0 | 1 |
| `reporting/Receipt.js::Receipt.constructor` | `reporting/Receipt.js:22` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Receipt.js::Receipt.render` | `reporting/Receipt.js:26` | 7 | 3 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.js::Report.total` | `reporting/Report.js:4` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.js::Report.total.<anonymous>` | `reporting/Report.js:5` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.js::Report.render` | `reporting/Report.js:8` | 4 | 1 | 1 | 1 | 0 | 0 | 0 |
| `reporting/Report.js::Report.render.<anonymous>` | `reporting/Report.js:9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `javascript` | `.` | 0 | 0 | 0 | N/A |
| `brewing` | `brewing` | 3 | 1 | 3 | 0.25 |
| `brewing/Brewer.js` | `brewing/Brewer.js` | 1 | 2 | 1 | 0.67 |
| `brewing/Brewer.js::Brewing` | `brewing/Brewer.js:5` | 1 | 0 | 2 | 0.00 |
| `brewing/Brewer.js::Brewing.brew` | `brewing/Brewer.js:6` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::Brewer` | `brewing/Brewer.js:11` | 1 | 3 | 1 | 0.75 |
| `brewing/Brewer.js::Brewer.brew` | `brewing/Brewer.js:12` | 1 | 1 | 1 | 0.50 |
| `brewing/Brewer.js::Brewer.brew.<anonymous>` | `brewing/Brewer.js:14` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.js::Brewer.retry` | `brewing/Brewer.js:17` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::Brewer.score` | `brewing/Brewer.js:22` | 0 | 1 | 0 | 1.00 |
| `brewing/Brewer.js::Brewer.classify` | `brewing/Brewer.js:33` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::Brewer.classify.<anonymous>` | `brewing/Brewer.js:35` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::Brewer.ready` | `brewing/Brewer.js:38` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::Brewer.calibrate` | `brewing/Brewer.js:43` | 0 | 0 | 0 | N/A |
| `brewing/Brewer.js::main` | `brewing/Brewer.js:49` | 0 | 1 | 0 | 1.00 |
| `brewing/Recipe.js` | `brewing/Recipe.js` | 6 | 1 | 6 | 0.14 |
| `brewing/Recipe.js::Recipe` | `brewing/Recipe.js:3` | 4 | 1 | 4 | 0.20 |
| `brewing/Recipe.js::Recipe.portions` | `brewing/Recipe.js:4` | 4 | 0 | 4 | 0.00 |
| `brewing/Recipe.js::Recipe.price` | `brewing/Recipe.js:12` | 2 | 0 | 4 | 0.00 |
| `brewing/Recipe.js::Recipe.dose` | `brewing/Recipe.js:16` | 4 | 0 | 9 | 0.00 |
| `brewing/Recipe.js::Recipe.describe` | `brewing/Recipe.js:20` | 1 | 1 | 1 | 0.50 |
| `brewing/Recipe.js::Recipe.preview` | `brewing/Recipe.js:24` | 0 | 1 | 0 | 1.00 |
| `inventory` | `inventory` | 1 | 1 | 3 | 0.50 |
| `inventory/Inventory.js` | `inventory/Inventory.js` | 1 | 1 | 1 | 0.50 |
| `inventory/Inventory.js::Inventory` | `inventory/Inventory.js:3` | 1 | 1 | 1 | 0.50 |
| `inventory/Inventory.js::Inventory.constructor` | `inventory/Inventory.js:4` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.js::Inventory.canFill` | `inventory/Inventory.js:9` | 1 | 0 | 1 | 0.00 |
| `inventory/Inventory.js::Inventory.canFill.<anonymous>` | `inventory/Inventory.js:10` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.js::Inventory.canFill.<anonymous>` | `inventory/Inventory.js:11` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.js::Inventory.reserve` | `inventory/Inventory.js:15` | 0 | 2 | 0 | 1.00 |
| `inventory/Inventory.js::Inventory.restock` | `inventory/Inventory.js:24` | 1 | 0 | 1 | 0.00 |
| `inventory/Inventory.js::remaining` | `inventory/Inventory.js:31` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.js::needsDelivery` | `inventory/Inventory.js:32` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.js::deliveries` | `inventory/Inventory.js:35` | 0 | 1 | 0 | 1.00 |
| `inventory/Inventory.js::deliveries.shortage` | `inventory/Inventory.js:36` | 1 | 0 | 1 | 0.00 |
| `inventory/Inventory.js::alerts` | `inventory/Inventory.js:41` | 0 | 0 | 0 | N/A |
| `inventory/Inventory.js::replenish` | `inventory/Inventory.js:47` | 0 | 0 | 0 | N/A |
| `ordering` | `ordering` | 1 | 3 | 3 | 0.75 |
| `ordering/OrderService.js` | `ordering/OrderService.js` | 0 | 5 | 0 | 1.00 |
| `ordering/OrderService.js::OrderService` | `ordering/OrderService.js:7` | 0 | 4 | 0 | 1.00 |
| `ordering/OrderService.js::OrderService.constructor` | `ordering/OrderService.js:8` | 0 | 0 | 0 | N/A |
| `ordering/OrderService.js::OrderService.fulfill` | `ordering/OrderService.js:15` | 1 | 1 | 1 | 0.50 |
| `ordering/OrderService.js::OrderService.fulfill.<anonymous>` | `ordering/OrderService.js:17` | 0 | 0 | 0 | N/A |
| `ordering/OrderService.js::OrderService.describe` | `ordering/OrderService.js:23` | 0 | 0 | 0 | N/A |
| `ordering/OrderService.js::OrderService.describe.<anonymous>` | `ordering/OrderService.js:24` | 0 | 1 | 0 | 1.00 |
| `ordering/OrderService.js::morningOrder` | `ordering/OrderService.js:28` | 0 | 3 | 0 | 1.00 |
| `ordering/Orders.js` | `ordering/Orders.js` | 2 | 1 | 2 | 0.33 |
| `ordering/Orders.js::priceOrder` | `ordering/Orders.js:3` | 1 | 0 | 1 | 0.00 |
| `ordering/Orders.js::priceOrder.lineTotal` | `ordering/Orders.js:4` | 1 | 1 | 1 | 0.50 |
| `ordering/Orders.js::priceOrder.<anonymous>` | `ordering/Orders.js:7` | 0 | 1 | 0 | 1.00 |
| `ordering/Orders.js::priceOrder.<anonymous>` | `ordering/Orders.js:8` | 0 | 0 | 0 | N/A |
| `ordering/Orders.js::createOrder` | `ordering/Orders.js:11` | 1 | 0 | 1 | 0.00 |
| `ordering/Orders.js::drinkTickets` | `ordering/Orders.js:15` | 2 | 1 | 3 | 0.33 |
| `ordering/Orders.js::drinkTickets.ticket` | `ordering/Orders.js:16` | 1 | 1 | 4 | 0.50 |
| `ordering/Orders.js::pickupQueue` | `ordering/Orders.js:24` | 0 | 0 | 0 | N/A |
| `ordering/Orders.js::groupTickets` | `ordering/Orders.js:30` | 0 | 0 | 0 | N/A |
| `ordering/Orders.js::groupTickets.<anonymous>.<anonymous>` | `ordering/Orders.js:31` | 0 | 0 | 0 | N/A |
| `ordering/Orders.js::groupTickets.<anonymous>` | `ordering/Orders.js:31` | 0 | 1 | 0 | 1.00 |
| `reporting` | `reporting` | 2 | 2 | 3 | 0.50 |
| `reporting/Receipt.js` | `reporting/Receipt.js` | 1 | 2 | 1 | 0.67 |
| `reporting/Receipt.js::header` | `reporting/Receipt.js:6` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.js::money` | `reporting/Receipt.js:7` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.js::items` | `reporting/Receipt.js:10` | 0 | 1 | 0 | 1.00 |
| `reporting/Receipt.js::items.describe` | `reporting/Receipt.js:11` | 1 | 1 | 1 | 0.50 |
| `reporting/Receipt.js::totals` | `reporting/Receipt.js:16` | 0 | 1 | 0 | 1.00 |
| `reporting/Receipt.js::Receipt` | `reporting/Receipt.js:21` | 1 | 0 | 1 | 0.00 |
| `reporting/Receipt.js::Receipt.constructor` | `reporting/Receipt.js:22` | 0 | 0 | 0 | N/A |
| `reporting/Receipt.js::Receipt.render` | `reporting/Receipt.js:26` | 0 | 0 | 0 | N/A |
| `reporting/Report.js` | `reporting/Report.js` | 2 | 1 | 6 | 0.33 |
| `reporting/Report.js::Report` | `reporting/Report.js:3` | 2 | 1 | 4 | 0.33 |
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
