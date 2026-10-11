# Metrics

- files: 3
- modules: 1
- types: 3
- callables: 23
- circularImportGroups: 0
- parseErrors: 0

## Files

| Item | Location | Lines | Functions/methods | Measured functions/methods | Weighted complexity sum |
| --- | --- | --- | --- | --- | --- |
| `App.tsx` | `App.tsx` | 47 | 9 | 9 | 9 |
| `Basket.tsx` | `Basket.tsx` | 35 | 10 | 10 | 11 |
| `CoffeeCard.tsx` | `CoffeeCard.tsx` | 23 | 4 | 4 | 5 |

## Callables

| Item | Location | Lines | Parameters | Cyclomatic complexity | Weighted complexity | Nested decision penalty | Nested loops | Decision depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `App.tsx::App` | `App.tsx:9` | 8 | 0 | 1 | 1 | 0 | 0 | 0 |
| `App.tsx::Preview` | `App.tsx:19` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `App.tsx::Menu` | `App.tsx:23` | 20 | 1 | 1 | 1 | 0 | 0 | 0 |
| `App.tsx::Menu.<anonymous>` | `App.tsx:24` | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| `App.tsx::Menu.addDrink` | `App.tsx:25` | 4 | 2 | 1 | 1 | 0 | 0 | 0 |
| `App.tsx::Menu.<anonymous>` | `App.tsx:33` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `App.tsx::Menu.<anonymous>` | `App.tsx:37` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `App.tsx::CoffeeCounter` | `App.tsx:44` | 4 | 0 | 1 | 1 | 0 | 0 | 0 |
| `App.tsx::CoffeeCounter.<anonymous>` | `App.tsx:45` | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| `Basket.tsx::Basket.constructor` | `Basket.tsx:9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `Basket.tsx::Basket.add` | `Basket.tsx:11` | 5 | 2 | 2 | 2 | 0 | 0 | 1 |
| `Basket.tsx::Basket.add.<anonymous>` | `Basket.tsx:12` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `Basket.tsx::Basket.total` | `Basket.tsx:17` | 4 | 2 | 1 | 1 | 0 | 0 | 0 |
| `Basket.tsx::Basket.total.<anonymous>` | `Basket.tsx:18` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `Basket.tsx::Basket.total.<anonymous>` | `Basket.tsx:19` | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `Basket.tsx::Basket.snapshot` | `Basket.tsx:22` | 3 | 0 | 1 | 1 | 0 | 0 | 0 |
| `Basket.tsx::Basket.snapshot.<anonymous>` | `Basket.tsx:23` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `Basket.tsx::startOrder` | `Basket.tsx:27` | 5 | 2 | 1 | 1 | 0 | 0 | 0 |
| `Basket.tsx::orderTotal` | `Basket.tsx:33` | 3 | 2 | 1 | 1 | 0 | 0 | 0 |
| `CoffeeCard.tsx::CoffeeProps.onOrder` | `CoffeeCard.tsx:5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `CoffeeCard.tsx::label` | `CoffeeCard.tsx:9` | 3 | 1 | 1 | 1 | 0 | 0 | 0 |
| `CoffeeCard.tsx::CoffeeCard` | `CoffeeCard.tsx:13` | 9 | 1 | 2 | 2 | 0 | 0 | 0 |
| `CoffeeCard.tsx::CoffeeCard.<anonymous>` | `CoffeeCard.tsx:18` | 1 | 0 | 1 | 1 | 0 | 0 | 0 |

## Dependencies

| Item | Location | Fan-in | Fan-out | Change impact | Internal instability |
| --- | --- | --- | --- | --- | --- |
| `tsx` | `.` | 0 | 0 | 0 | N/A |
| `App.tsx` | `App.tsx` | 0 | 2 | 0 | 1.00 |
| `App.tsx::App` | `App.tsx:9` | 0 | 2 | 0 | 1.00 |
| `App.tsx::Preview` | `App.tsx:19` | 0 | 0 | 0 | N/A |
| `App.tsx::Menu` | `App.tsx:23` | 1 | 2 | 1 | 0.67 |
| `App.tsx::Menu.<anonymous>` | `App.tsx:24` | 0 | 0 | 0 | N/A |
| `App.tsx::Menu.addDrink` | `App.tsx:25` | 1 | 0 | 1 | 0.00 |
| `App.tsx::Menu.<anonymous>` | `App.tsx:33` | 0 | 1 | 0 | 1.00 |
| `App.tsx::Menu.<anonymous>` | `App.tsx:37` | 0 | 0 | 0 | N/A |
| `App.tsx::CoffeeCounter` | `App.tsx:44` | 0 | 1 | 0 | 1.00 |
| `App.tsx::CoffeeCounter.<anonymous>` | `App.tsx:45` | 0 | 0 | 0 | N/A |
| `Basket.tsx` | `Basket.tsx` | 1 | 0 | 1 | 0.00 |
| `Basket.tsx::BasketItem` | `Basket.tsx:1` | 0 | 0 | 0 | N/A |
| `Basket.tsx::Basket` | `Basket.tsx:6` | 0 | 0 | 0 | N/A |
| `Basket.tsx::Basket.constructor` | `Basket.tsx:9` | 0 | 0 | 0 | N/A |
| `Basket.tsx::Basket.add` | `Basket.tsx:11` | 1 | 0 | 1 | 0.00 |
| `Basket.tsx::Basket.add.<anonymous>` | `Basket.tsx:12` | 0 | 0 | 0 | N/A |
| `Basket.tsx::Basket.total` | `Basket.tsx:17` | 1 | 0 | 3 | 0.00 |
| `Basket.tsx::Basket.total.<anonymous>` | `Basket.tsx:18` | 0 | 0 | 0 | N/A |
| `Basket.tsx::Basket.total.<anonymous>` | `Basket.tsx:19` | 0 | 0 | 0 | N/A |
| `Basket.tsx::Basket.snapshot` | `Basket.tsx:22` | 0 | 0 | 0 | N/A |
| `Basket.tsx::Basket.snapshot.<anonymous>` | `Basket.tsx:23` | 0 | 0 | 0 | N/A |
| `Basket.tsx::startOrder` | `Basket.tsx:27` | 0 | 1 | 0 | 1.00 |
| `Basket.tsx::orderTotal` | `Basket.tsx:33` | 1 | 1 | 2 | 0.50 |
| `CoffeeCard.tsx` | `CoffeeCard.tsx` | 1 | 0 | 1 | 0.00 |
| `CoffeeCard.tsx::CoffeeProps` | `CoffeeCard.tsx:1` | 0 | 0 | 0 | N/A |
| `CoffeeCard.tsx::CoffeeProps.onOrder` | `CoffeeCard.tsx:5` | 0 | 0 | 0 | N/A |
| `CoffeeCard.tsx::label` | `CoffeeCard.tsx:9` | 2 | 0 | 4 | 0.00 |
| `CoffeeCard.tsx::CoffeeCard` | `CoffeeCard.tsx:13` | 2 | 1 | 3 | 0.33 |
| `CoffeeCard.tsx::CoffeeCard.<anonymous>` | `CoffeeCard.tsx:18` | 0 | 0 | 0 | N/A |

Dependency metrics count distinct internal peers at each item's level, including tests and type-only dependencies. Impact excludes the item itself. Instability = fan-out / (fan-in + fan-out); isolated items are N/A.
