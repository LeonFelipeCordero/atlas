"""Independent expectations for the brewing/reporting workflow, not an inventory."""

from tests.coffee_fixture import BREWING_LANGUAGES

CORE_LANGUAGES = BREWING_LANGUAGES
COMPLEXITY_FIELDS = (
    "baseCyclomaticComplexity", "nestedCyclomaticComplexity", "loopNestedComplexity",
    "cyclomaticComplexity", "maxDecisionDepth",
)
SCORE = {language: (5, 1, 1, 7, 3) for language in CORE_LANGUAGES}
SCORE["elixir"] = (1, 0, 0, 1, 0)
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


def core_calls(graph):
    """Project callback edges to their named workflow owners."""
    nodes = {node["stableKey"]: node for node in graph["nodes"]}

    def role(key):
        node = nodes[key]
        while node["name"] in {"<anonymous>", "accept"} and node["parentStableKey"]:
            node = nodes[node["parentStableKey"]]
        return node["name"].lower()

    return {
        (role(edge["sourceStableKey"]), role(edge["targetStableKey"]))
        for edge in graph["edges"] if edge["type"] == "CALLS"
        and nodes[edge["targetStableKey"]]["level"] != "external"
    }
