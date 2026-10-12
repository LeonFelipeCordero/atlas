"""Lossless record checks shared by metric enrichment tests."""


def assert_symbol_identity(actual, expected):
    assert all(a is b for a, b in zip(actual, expected, strict=True))


def restore_symbol_metrics(enriched, original):
    for metric in ("complexity", "line_count", "parameter_count"):
        enriched[metric] = original[metric]


def restore_file_metrics(enriched, original):
    for new, old in zip(enriched["symbols"], original["symbols"], strict=True):
        restore_symbol_metrics(new, old)


def restore_repository_metrics(enriched, original):
    for new, old in zip(enriched["files"], original["files"], strict=True):
        restore_file_metrics(new, old)
