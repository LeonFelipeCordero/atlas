"""Source-reviewed inventories and scenario expectations, independent of JSON."""

from collections import Counter
from typing import Any

# Exact path-keyed inventories, including manifests with no declarations.
DECLARATIONS = {
    "java": {
        "brewing/Brewer.java": "coffee.brewing Brewing Brewing.brew Brewer Brewer.brew Brewer.brew.<anonymous> Brewer.retry Brewer.score Brewer.classify Brewer.ready Brewer.calibrate Brewer.main",
        "brewing/Recipe.java": "coffee.brewing Recipe Recipe.Recipe Recipe.portions Recipe.preview",
        "inventory/Inventory.java": "coffee.inventory Reservable Reservable.reserve Inventory Inventory.Change Inventory.Change.Change Inventory.record Inventory.receive Inventory.reserve Inventory.reserve.<anonymous> Inventory.reserve.<anonymous> Inventory.units",
        "inventory/StockLedger.java": "coffee.inventory StockLedger StockLedger.record StockLedger.snapshot",
        "orders/CoffeeOrders.java": "coffee.orders CoffeeOrders CoffeeOrders.fulfill CoffeeOrders.ready",
        "orders/Order.java": "coffee.orders Order Order.Line Order.Line.Line Order.Line.subtotal Order.Order Order.status Order.total Order.names Order.names.<anonymous> Order.transition",
        "orders/OrderService.java": "coffee.orders OrderService OrderService.audit OrderService.OrderService OrderService.OrderService OrderService.place OrderService.place OrderService.fulfill OrderService.preview OrderService.orders OrderService.place OrderService.stocked OrderService.Factory OrderService.Factory.Factory OrderService.Factory.create",
        "reporting/Report.java": "coffee.reporting Report Report.Report Report.total Report.render Report.render.<anonymous>",
        "reporting/SalesReport.java": "coffee.reporting SalesReport SalesReport.include SalesReport.SalesReport SalesReport.totals SalesReport.totals.<anonymous> SalesReport.totals.<anonymous>.<anonymous> SalesReport.totals.<anonymous> SalesReport.discounts SalesReport.discounts.<anonymous> SalesReport.discounts.<anonymous>.<anonymous> SalesReport.summary SalesReport.summary.<anonymous>",
    },
    "kotlin": {
        "brewing/Brewer.kt": "coffee.brewing CoffeeMaker CoffeeMaker.brew Brewer Brewer.brew Brewer.brew.<anonymous> Brewer.retry Brewer.score Brewer.classify Brewer.ready Brewer.calibrate main",
        "brewing/Recipe.kt": "coffee.brewing portions preview",
        "inventory/Inventory.kt": "coffee.inventory StockLedger StockLedger.record StockLedger.snapshot Reservable Reservable.reserve Inventory Inventory.Change Inventory.record Inventory.receive Inventory.receive.<anonymous> Inventory.reserve Inventory.reserve.<anonymous> Inventory.reserve.<anonymous> Inventory.units Inventory.Companion Inventory.Companion.stocked",
        "orders/Order.kt": "coffee.orders OrderStatus OrderLine OrderLine.subtotal OrderLine.Factory OrderLine.Factory.espresso Order Order.total Order.total.<anonymous> Order.names Order.names.<anonymous> Order.names.<anonymous>.<anonymous> Order.transition receipt",
        "orders/OrderService.kt": "coffee.orders CoffeeOrders CoffeeOrders.fulfill OrderService OrderService.<anonymous> OrderService.place OrderService.place OrderService.fulfill OrderService.preview OrderService.receipts OrderService.receipts.<anonymous> OrderService.receipts.formatReady OrderService.notify OrderService.place OrderService.Companion OrderService.Companion.stocked",
        "reporting/Report.kt": "coffee.reporting render render.<anonymous> render.<anonymous>",
        "reporting/SalesReport.kt": "coffee.reporting OrderFilter SalesReport SalesReport.<anonymous> SalesReport.totals SalesReport.totals.<anonymous> SalesReport.totals.<anonymous>.add SalesReport.totals.<anonymous> SalesReport.discounts SalesReport.discounts.<anonymous> SalesReport.discounts.<anonymous>.<anonymous> SalesReport.projected SalesReport.projected.<anonymous> SalesReport.projected.<anonymous> SalesReport.résumé SalesReport.résumé.<anonymous> SalesReport.résumé",
    },
    "go": {
        "brewing/brewer.go": "Brewer NewBrewer Brew brew brew.accept retry score classify ready calibrate Main Main.<anonymous>",
        "brewing/inventory.go": "Adjustment Inventory NewInventory Remaining Reserve Restock Restock.apply Restock.apply.normalize",
        "brewing/order.go": "Order NewOrder Serve Estimate",
        "go.mod": "",
        "main.go": "main",
        "recipe/recipe.go": "Normalize Recipe New Portions Dose Scale",
        "reporting/report.go": "Report Total Render Receipt Preview",
    },
    "rust": {
        "Cargo.toml": "",
        "brewing/brewer.rs": "Brewer new brew remaining brew brew.<anonymous> retry score classify ready calibrate",
        "brewing/inventory.rs": "Adjustment <anonymous> Inventory new new.<anonymous> remaining reserve restock restock.<anonymous> restock.<anonymous>.adjusted_units restock.<anonymous>.<anonymous>",
        "brewing/mod.rs": "brewer inventory recipe",
        "brewing/recipe.rs": "Recipe new portions scale label portions preview",
        "main.rs": "brewing reporting main main.<anonymous>",
        "reporting/daily/totals.rs": "portions",
        "reporting/mod.rs": "report daily daily.totals daily.close",
        "reporting/report.rs": "Report new new.<anonymous> render render.<anonymous> estimate total total.<anonymous> render render.<anonymous>",
    },
    "javascript": {
        "brewing/Brewer.js": "Brewing Brewing.brew Brewer Brewer.brew Brewer.brew.<anonymous> Brewer.retry Brewer.score Brewer.classify Brewer.classify.<anonymous> Brewer.ready Brewer.calibrate main",
        "brewing/Recipe.js": "Recipe Recipe.portions Recipe.price Recipe.dose Recipe.describe Recipe.preview",
        "inventory/Inventory.js": "Inventory Inventory.canFill Inventory.canFill.<anonymous> Inventory.canFill.<anonymous> Inventory.reserve Inventory.restock remaining needsDelivery deliveries deliveries.shortage alerts replenish",
        "ordering/OrderService.js": "OrderService OrderService.fulfill OrderService.fulfill.<anonymous> OrderService.describe OrderService.describe.<anonymous> morningOrder",
        "ordering/Orders.js": "priceOrder priceOrder.lineTotal priceOrder.<anonymous> priceOrder.<anonymous> createOrder drinkTickets drinkTickets.ticket pickupQueue groupTickets groupTickets.<anonymous> groupTickets.<anonymous>.<anonymous>",
        "reporting/Receipt.js": "header money items items.describe totals Receipt Receipt.render",
        "reporting/Report.js": "Report Report.total Report.total.<anonymous> Report.render Report.render.<anonymous>",
    },
    "typescript": {
        "brewing/Brewer.ts": "Brewing Brewing.brew Brewer Brewer.brew Brewer.brew.<anonymous> Brewer.retry Brewer.score Brewer.classify Brewer.classify.<anonymous> Brewer.ready Brewer.calibrate main",
        "brewing/Recipe.ts": "Recipe Recipe.portions Recipe.price Recipe.dose Recipe.describe Recipe.preview",
        "inventory/Inventory.ts": "Delivery Inventory Inventory.constructor Inventory.canFill Inventory.canFill.<anonymous> Inventory.canFill.<anonymous> Inventory.reserve Inventory.restock remaining needsDelivery deliveries deliveries.shortage alerts replenish",
        "ordering/Order.ts": 'OrderItem Order Ticket OrderBook OrderBook.select OrderBook.onChange OrderBook."daily-total" OrderBook.[Symbol.iterator] OrderBook.find OrderBook.find PricingContext OrderBookProvider',
        "ordering/OrderLedger.ts": 'OrderLedger OrderLedger.constructor OrderLedger.count OrderLedger.select OrderLedger."daily-total" OrderLedger."daily-total".<anonymous> OrderLedger.[Symbol.iterator] OrderLedger.find OrderLedger.find OrderLedger.find OrderLedger.find.<anonymous> OrderLedger.add',
        "ordering/OrderService.ts": "OrderService OrderService.constructor OrderService.fulfill OrderService.fulfill.<anonymous> OrderService.describe OrderService.describe.<anonymous> morningOrder checkStock",
        "ordering/Orders.ts": "priceOrder priceOrder.lineTotal priceOrder.<anonymous> priceOrder.<anonymous> createOrder drinkTickets drinkTickets.ticket pickupQueue quote quote quote quoteWithFees groupTickets groupTickets.<anonymous> groupTickets.<anonymous>.<anonymous>",
        "reporting/Receipt.ts": "ReceiptFormatters ReceiptFormatters.header ReceiptFormatters.money ReceiptFormatters.items ReceiptFormatters.totals header money items items.describe totals Receipt Receipt.constructor Receipt.render",
        "reporting/Report.ts": "Report Report.total Report.total.<anonymous> Report.render Report.render.<anonymous>",
    },
    "elixir": {
        "brewing/brewer.ex": "Coffee.Brewing.Brewer Coffee.Brewing.Brewer.brew Coffee.Brewing.Brewer.brew Coffee.Brewing.Brewer.brew.<anonymous> Coffee.Brewing.Brewer.serve Coffee.Brewing.Brewer.serve.<anonymous> Coffee.Brewing.Brewer.retry Coffee.Brewing.Brewer.retry Coffee.Brewing.Brewer.score Coffee.Brewing.Brewer.score.<anonymous> Coffee.Brewing.Brewer.score.<anonymous>.<anonymous> Coffee.Brewing.Brewer.classify Coffee.Brewing.Brewer.ready Coffee.Brewing.Brewer.calibrate Coffee.Brewing.Brewer.main",
        "brewing/inventory.ex": "Coffee.Brewing.Inventory Coffee.Brewing.Inventory.new Coffee.Brewing.Inventory.remaining Coffee.Brewing.Inventory.reserve Coffee.Brewing.Inventory.restock Coffee.Brewing.Inventory.restock.<anonymous> Coffee.Brewing.Inventory.restock.<anonymous>.<anonymous> Coffee.Brewing.Inventory.restock.<anonymous>.<anonymous> Coffee.Brewing.Inventory.available Coffee.Brewing.Inventory.available.<anonymous>",
        "brewing/order.ex": "Coffee.Brewing.Order Coffee.Brewing.Order.new Coffee.Brewing.Order.estimate Coffee.Brewing.Order.preview",
        "brewing/recipe.ex": "Coffee.Brewing.Recipe Coffee.Brewing.Recipe.new Coffee.Brewing.Recipe.portions Coffee.Brewing.Recipe.scale Coffee.Brewing.Recipe.dose Coffee.Brewing.Recipe.preview",
        "reporting/report.ex": "Coffee.Reporting.Report Coffee.Reporting.Report.total Coffee.Reporting.Report.total.<anonymous> Coffee.Reporting.Report.render Coffee.Reporting.Report.render.<anonymous> Coffee.Reporting.Report.daily Coffee.Reporting.Report.largest Coffee.Reporting.Report.largest",
    },
    "python": {
        "src/coffee/brewing/brewer.py": "Brewing Brewing.brew Brewer Brewer.brew Brewer.retry Brewer.score Brewer.classify Brewer.ready Brewer.calibrate import_styles main",
        "src/coffee/brewing/recipe.py": "Recipe Recipe.portions Recipe.preview portions",
        "src/coffee/inventory/stock.py": "Ledger Ledger.record StockChange Inventory Inventory.Snapshot Inventory.Snapshot.units Inventory.__init__ Inventory.record Inventory.receive Inventory.reserve Inventory.snapshot",
        "src/coffee/orders/models.py": "OrderStatus OrderLine OrderLine.subtotal OrderLine.espresso Order Order.total Order.names Order.transition",
        "src/coffee/orders/service.py": "audited audited.decorate audited.decorate.wrapped CoffeeOrders CoffeeOrders.fulfill AuditTrail AuditTrail.audit OrderService OrderService.__init__ OrderService.place OrderService.fulfill OrderService.preview OrderService.receipts OrderService.receipts.format_ready OrderService.notify OrderService.notify.<anonymous> OrderService.estimate OrderService.stocked",
        "src/coffee/reporting/report.py": "Report Report.total Report.render render",
        "src/coffee/reporting/sales.py": "SalesReport SalesReport.__init__ SalesReport.__init__.<anonymous> SalesReport.totals SalesReport.totals.collect SalesReport.discounts SalesReport.discounts.<anonymous> SalesReport.discounts.<anonymous>.<anonymous> SalesReport.render",
    },
    "tsx": {
        "App.tsx": "App Preview Menu Menu.<anonymous> Menu.addDrink Menu.<anonymous> Menu.<anonymous> CoffeeCounter CoffeeCounter.<anonymous>",
        "Basket.tsx": "BasketItem Basket Basket.constructor Basket.add Basket.add.<anonymous> Basket.total Basket.total.<anonymous> Basket.total.<anonymous> Basket.snapshot Basket.snapshot.<anonymous> startOrder orderTotal",
        "CoffeeCard.tsx": "CoffeeProps CoffeeProps.onOrder label CoffeeCard CoffeeCard.<anonymous>",
    },
}
# Native-only supported declarations: enum, impl ownership, JS constructors,
# and Elixir defstruct expressions. Assert both variants exactly, not a union.
NATIVE_OVERRIDES = {
    "java": {
        "orders/Order.java": "coffee.orders Order Order.Status Order.Line Order.Line.Line Order.Line.subtotal Order.Order Order.status Order.total Order.names Order.names.<anonymous> Order.transition",
    },
    "rust": {
        "brewing/brewer.rs": "Brewer Brewer Brewer.new Brewer.brew Brewer.remaining brew brew.<anonymous> retry score classify ready calibrate",
        "brewing/inventory.rs": "Adjustment <anonymous> Inventory Inventory Inventory.new Inventory.new.<anonymous> Inventory.remaining Inventory.reserve Inventory.restock Inventory.restock.<anonymous> Inventory.restock.<anonymous>.adjusted_units Inventory.restock.<anonymous>.<anonymous>",
        "brewing/recipe.rs": "Recipe Recipe Recipe.new Recipe.portions Recipe.scale Recipe.label portions preview",
        "reporting/report.rs": "Report Report Report.new Report.new.<anonymous> Report.render Report.render.<anonymous> Report.estimate total total.<anonymous> render render.<anonymous>",
    },
    "javascript": {
        "inventory/Inventory.js": "Inventory Inventory.constructor Inventory.canFill Inventory.canFill.<anonymous> Inventory.canFill.<anonymous> Inventory.reserve Inventory.restock remaining needsDelivery deliveries deliveries.shortage alerts replenish",
        "ordering/OrderService.js": "OrderService OrderService.constructor OrderService.fulfill OrderService.fulfill.<anonymous> OrderService.describe OrderService.describe.<anonymous> morningOrder",
        "reporting/Receipt.js": "header money items items.describe totals Receipt Receipt.constructor Receipt.render",
    },
    "elixir": {
        "brewing/inventory.ex": "Coffee.Brewing.Inventory Coffee.Brewing.Inventory.<anonymous> Coffee.Brewing.Inventory.new Coffee.Brewing.Inventory.remaining Coffee.Brewing.Inventory.reserve Coffee.Brewing.Inventory.restock Coffee.Brewing.Inventory.restock.<anonymous> Coffee.Brewing.Inventory.restock.<anonymous>.<anonymous> Coffee.Brewing.Inventory.restock.<anonymous>.<anonymous> Coffee.Brewing.Inventory.available Coffee.Brewing.Inventory.available.<anonymous>",
        "brewing/order.ex": "Coffee.Brewing.Order Coffee.Brewing.Order.<anonymous> Coffee.Brewing.Order.new Coffee.Brewing.Order.estimate Coffee.Brewing.Order.preview",
        "brewing/recipe.ex": "Coffee.Brewing.Recipe Coffee.Brewing.Recipe.<anonymous> Coffee.Brewing.Recipe.new Coffee.Brewing.Recipe.portions Coffee.Brewing.Recipe.scale Coffee.Brewing.Recipe.dose Coffee.Brewing.Recipe.preview",
    },
}
NATIVE_DECLARATIONS = {
    language: {**paths, **NATIVE_OVERRIDES.get(language, {})}
    for language, paths in DECLARATIONS.items()
}
CORE_LANGUAGES = tuple(language for language in DECLARATIONS if language != "tsx")

# Columns: symbols, anonymous nodes, self-calls, inheritance, internal imports,
# Recipe→Report / Report→Recipe file-view counts, import-cycle groups.
OBSERVED = {
    "java": (83, 11, 1, 4, 11, (2, 3), 1),
    "kotlin": (83, 19, 1, 4, 13, (2, 3), 1),
    "go": (36, 1, 1, 0, 0, (0, 0), 0),
    "rust": (55, 10, 1, 0, 18, (2, 4), 1),
    "javascript": (62, 12, 1, 1, 13, (2, 3), 1),
    "typescript": (97, 14, 1, 2, 19, (2, 3), 1),
    "elixir": (46, 13, 2, 0, 8, (2, 0), 0),
    "python": (65, 4, 1, 9, 20, (2, 3), 1),
}
COMPLEXITY_FIELDS = (
    "baseCyclomaticComplexity", "nestedCyclomaticComplexity", "loopNestedComplexity",
    "cyclomaticComplexity", "maxDecisionDepth",
)
SCORE = {language: (5, 1, 1, 7, 3) for language in CORE_LANGUAGES}
SCORE["elixir"] = (1, 0, 0, 1, 0)
CALL_SITES = {
    "java": 114, "kotlin": 95, "go": 66, "rust": 98, "javascript": 68,
    "typescript": 77, "elixir": 88, "python": 98, "tsx": 23,
}
# Same source calls may dispatch to overloads/clauses, never synthetic sites.
CALL_DUPLICATES = {"javascript": 1, "typescript": 1, "elixir": 8}
EMPTY_BREW_CALL = {
    "java": "Report.render(List.of())", "kotlin": "render(emptyList())",
    "go": "reporting.Render(nil)", "rust": "report::render(&[])",
    "javascript": "Report.render([])", "typescript": "Report.render([])",
    "elixir": "Report.render([])", "python": "Report.render([])",
}
FILTER_CALL = {
    "java": "names.stream()\n            .filter(name -> Recipe.portions(name) > 0)",
    "kotlin": "names.filter { portions(it) > 0 }", "go": "accept(name)",
    "rust": "names\n        .iter()\n        .copied()\n        .filter(|name| recipe::portions(name) > 0)",
    "javascript": "names.filter(name => Recipe.portions(name) > 0)",
    "typescript": "names.filter(name => Recipe.portions(name) > 0)",
    "elixir": "Enum.filter(fn name -> Recipe.portions(name) > 0 end)",
    "python": "Recipe.portions(name)",
}
CORE_CALLS = {
    ("main", "brew"), ("brew", "render"), ("brew", "portions"),
    ("retry", "retry"), ("score", "portions"), ("preview", "render"),
    ("total", "portions"), ("render", "portions"), ("render", "total"),
}


def declaration_gaps(graph: dict[str, Any]) -> tuple[list[Counter[str]], list[Counter[str]]]:
    language = graph["repository"]["languages"][0]
    paths = sorted(node["path"] for node in graph["nodes"] if node["level"] == "file")
    assert set(paths) == set(DECLARATIONS[language]), (language, paths)
    missing, extra = [], []
    for path in paths:
        actual = declarations_for_path(graph, path)
        expected = Counter(NATIVE_DECLARATIONS[language][path].split())
        missing.append(expected - actual)
        extra.append(actual - expected)
    return missing, extra


def declarations_for_path(graph, path):
    return Counter(
        node["qualifiedName"].split("::", 1)[1]
        for node in graph["nodes"] if node["path"] == path and "startLine" in node
    )


def core_calls(graph: dict[str, Any]) -> set[tuple[str, str]]:
    """Project callbacks to named owners solely for workflow coverage assertions."""
    nodes = {node["stableKey"]: node for node in graph["nodes"]}

    def role(key: str) -> str:
        node = nodes[key]
        while node["name"] in {"<anonymous>", "accept"} and node["parentStableKey"]:
            node = nodes[node["parentStableKey"]]
        return node["name"].lower()

    return {
        (role(edge["sourceStableKey"]), role(edge["targetStableKey"]))
        for edge in graph["edges"] if edge["type"] == "CALLS"
        and nodes[edge["targetStableKey"]]["level"] != "external"
    }


def named_file_key(nodes, name):
    return next(
        node["stableKey"] for node in nodes.values()
        if node["level"] == "file" and f"/{name}." in node["path"].lower()
    )


def self_call_count(graph):
    return sum(
        edge["type"] == "CALLS" and edge["sourceStableKey"] == edge["targetStableKey"]
        for edge in graph["edges"]
    )


def internal_import_count(graph, nodes):
    return sum(
        edge["type"] == "IMPORTS" and nodes[edge["targetStableKey"]]["level"] != "external"
        for edge in graph["edges"]
    )


def scenario_summary(graph: dict[str, Any]) -> tuple[Any, ...]:
    nodes = {node["stableKey"]: node for node in graph["nodes"]}
    recipe = named_file_key(nodes, "recipe")
    report = named_file_key(nodes, "report")
    file_counts = {
        (edge["sourceStableKey"], edge["targetStableKey"]): edge["count"]
        for edge in graph["views"]["file"]["edges"]
    }
    return (
        graph["stats"]["symbols"],
        sum(node["name"] == "<anonymous>" for node in nodes.values()),
        self_call_count(graph),
        sum(edge["type"] == "INHERITS" for edge in graph["edges"]),
        internal_import_count(graph, nodes),
        (file_counts.get((recipe, report), 0), file_counts.get((report, recipe), 0)),
        len(graph["circularDependencies"]["groups"]),
    )
