"""Source-reviewed inventories and scenario expectations, independent of JSON."""

from collections import Counter
from typing import Any

# File order: brewing/Brewer, brewing/Recipe, reporting/Report.
DECLARATIONS = {
    "java": (
        "coffee.brewing Brewing Brewing.brew Brewer Brewer.brew Brewer.brew.<anonymous> Brewer.retry Brewer.score Brewer.main",
        "coffee.brewing Recipe Recipe.Recipe Recipe.portions Recipe.preview",
        "coffee.reporting Report Report.Report Report.total Report.render Report.render.<anonymous>",
    ),
    "kotlin": (
        "coffee.brewing CoffeeMaker CoffeeMaker.brew Brewer Brewer.brew Brewer.brew.<anonymous> Brewer.retry Brewer.score main",
        "coffee.brewing portions preview",
        "coffee.reporting render render.<anonymous> render.<anonymous>",
    ),
    "go": ("brew brew.accept retry score Main", "portions preview", "total render"),
    "rust": (
        "recipe report brew brew.<anonymous> retry score main",
        "portions preview",
        "total total.<anonymous> render render.<anonymous>",
    ),
    "javascript": (
        "Brewing Brewing.brew Brewer Brewer.brew Brewer.brew.<anonymous> Brewer.retry Brewer.score main",
        "Recipe Recipe.portions Recipe.preview",
        "Report Report.total Report.total.<anonymous> Report.render Report.render.<anonymous>",
    ),
    "typescript": (
        "Brewing Brewing.brew Brewer Brewer.brew Brewer.brew.<anonymous> Brewer.retry Brewer.score main",
        "Recipe Recipe.portions Recipe.preview",
        "Report Report.total Report.total.<anonymous> Report.render Report.render.<anonymous>",
    ),
    "elixir": (
        "Coffee.Brewing.Brewer Coffee.Brewing.Brewer.brew Coffee.Brewing.Brewer.brew Coffee.Brewing.Brewer.brew.<anonymous> Coffee.Brewing.Brewer.retry Coffee.Brewing.Brewer.retry Coffee.Brewing.Brewer.score Coffee.Brewing.Brewer.score.<anonymous> Coffee.Brewing.Brewer.score.<anonymous>.<anonymous> Coffee.Brewing.Brewer.main",
        "Coffee.Brewing.Recipe Coffee.Brewing.Recipe.portions Coffee.Brewing.Recipe.preview",
        "Coffee.Reporting.Report Coffee.Reporting.Report.total Coffee.Reporting.Report.total.<anonymous> Coffee.Reporting.Report.render Coffee.Reporting.Report.render.<anonymous>",
    ),
    "python": (
        "Brewing Brewing.brew Brewer Brewer.brew Brewer.retry Brewer.score import_styles main",
        "Recipe Recipe.portions Recipe.preview portions",
        "Report Report.total Report.render render",
    ),
}

# Columns: symbols, anonymous nodes, self-call edges, inheritance edges,
# internal imports, Recipe→Report / Report→Recipe file-view relationship counts,
# import-cycle groups. Separate Elixir clauses are real source declarations.
OBSERVED = {
    "java": (20, 2, 1, 1, 3, (2, 3), 1),
    "kotlin": (16, 3, 1, 1, 3, (2, 3), 1),
    "go": (9, 0, 1, 0, 0, (1, 2), 0),
    "rust": (13, 3, 1, 0, 4, (2, 3), 1),
    "javascript": (16, 3, 1, 1, 4, (2, 3), 1),
    "typescript": (16, 3, 1, 1, 4, (2, 3), 1),
    "elixir": (18, 5, 1, 0, 4, (2, 3), 1),
    "python": (16, 0, 1, 2, 12, (2, 3), 1),
}
COMPLEXITY_FIELDS = (
    "baseCyclomaticComplexity",
    "nestedCyclomaticComplexity",
    "loopNestedComplexity",
    "cyclomaticComplexity",
    "maxDecisionDepth",
)
SCORE = {language: (5, 1, 1, 7, 3) for language in DECLARATIONS}
SCORE["elixir"] = (1, 0, 0, 1, 0)
# Source-reviewed expectations for the 24 indexed fixture files, independent of snapshots.
# Elixir's two clauses yield two edges for each of two call sites.
CALL_SITES = {
    "java": 25,
    "kotlin": 21,
    "go": 22,
    "rust": 25,
    "javascript": 18,
    "typescript": 17,
    "elixir": 16,
    "python": 26,
}
EMPTY_BREW_CALL = {
    "java": "Report.render(List.of())",
    "kotlin": "render(emptyList())",
    "go": "render(nil)",
    "rust": "report::render(&[])",
    "javascript": "Report.render([])",
    "typescript": "Report.render([])",
    "elixir": "Report.render([])",
    "python": "Report.render([])",
}
FILTER_CALL = {
    "java": "names.stream()\n            .filter(name -> Recipe.portions(name) > 0)",
    "kotlin": "names.filter { portions(it) > 0 }",
    "go": "accept(name)",
    "rust": "names.iter().copied()\n        .filter(|name| recipe::portions(name) > 0)",
    "javascript": "names.filter(name => Recipe.portions(name) > 0)",
    "typescript": "names.filter(name => Recipe.portions(name) > 0)",
    "elixir": "Enum.filter(fn name -> Recipe.portions(name) > 0 end)",
    "python": "Recipe.portions(name)",
}
CORE_CALLS = {
    ("main", "brew"),
    ("brew", "render"),
    ("brew", "portions"),
    ("retry", "retry"),
    ("score", "portions"),
    ("preview", "render"),
    ("total", "portions"),
    ("render", "portions"),
    ("render", "total"),
}


def declaration_gaps(
    graph: dict[str, Any],
) -> tuple[list[Counter[str]], list[Counter[str]]]:
    language = graph["repository"]["languages"][0]
    paths = sorted(node["path"] for node in graph["nodes"] if node["level"] == "file")
    missing, extra = [], []
    for path, inventory in zip(paths, DECLARATIONS[language]):
        actual = declarations_for_path(graph, path)
        expected = Counter(inventory.split())
        missing.append(expected - actual)
        extra.append(actual - expected)
    return missing, extra


def declarations_for_path(graph, path):
    return Counter(
        node["qualifiedName"].split("::", 1)[1]
        for node in graph["nodes"]
        if node["path"] == path and "startLine" in node
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
        for edge in graph["edges"]
        if edge["type"] == "CALLS"
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
