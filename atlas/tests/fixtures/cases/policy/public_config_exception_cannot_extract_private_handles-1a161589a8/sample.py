from .config import CheckConfig

RULES = (
    ("maxFileLines", "lineCount", {"file"}),
    ("maxFunctionLines", "lineCount", {"function", "method"}),
    ("maxParameters", "parameterCount", {"function", "method"}),
    ("maxWeightedComplexity", "weightedComplexity", {"function", "method"}),
    ("maxDecisionDepth", "maxDecisionDepth", {"function", "method"}),
    ("maxNestedLoops", "nestedLoops", {"function", "method"}),
)
DEPENDENCY_RULES = (
    ("maxChangeImpact", "transitiveChangeImpact"),
    ("maxInstability", "instability"),
)
def _enabled_limits(node, config: NavigationReader):
    rules = [(rule, metric) for rule, metric, kinds in RULES if node["kind"] in kinds]
    if node["level"] in {"module", "file"}:
        rules.extend(DEPENDENCY_RULES)
    for rule, metric in rules:
        maximum = getattr(config, rule)
        if maximum is not None:
            yield _MetricLimit(rule, metric, maximum)
