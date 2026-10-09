"""Language modules own policies; shared helpers remain language-neutral."""

import ast
from importlib import import_module
from pathlib import Path

import pytest

from atlas.adapters import ADAPTERS, get_adapter
from atlas.adapters import rust

ROOT = Path(__file__).parents[1] / "src/atlas/adapters"
OWNERS = {
    "python": "python",
    "java": "java",
    "kotlin": "kotlin",
    "go": "go",
    "rust": "rust",
    "elixir": "elixir",
    "javascript": "javascript",
    "jsx": "javascript",
    "typescript": "typescript",
    "tsx": "typescript",
}


@pytest.mark.parametrize("language, owner", OWNERS.items())
def test_language_module_owns_adapter_and_parameter_policy(language, owner):
    module = import_module(f"atlas.adapters.{owner}")
    adapter = ADAPTERS[language]
    assert adapter is module.ADAPTER
    assert adapter.parameter_count is module.parameter_count
    assert adapter.parameter_count.__module__ == module.__name__


@pytest.mark.parametrize("language", ["python", "kotlin", "rust", "elixir"])
def test_language_module_owns_metric_policy(language):
    module = import_module(f"atlas.adapters.{language}")
    assert get_adapter(language).metrics is module.METRICS
    assert all(
        callback.__module__ == module.__name__
        for callback in module.METRICS.decision_overrides.values()
    )


@pytest.mark.parametrize("name", [
    "base", "parameters", "module_index", "resolution", "resolution_paths", "resolution_policy",
])
def test_shared_adapter_helpers_do_not_import_language_modules(name):
    tree = ast.parse((ROOT / f"{name}.py").read_text())
    assert not any(_language_import(node) for node in ast.walk(tree))


def _language_import(node):
    if isinstance(node, ast.ImportFrom):
        return (
            node.module.rsplit(".", 1)[-1] in OWNERS
            if node.module else any(alias.name in OWNERS for alias in node.names)
        )
    if isinstance(node, ast.Import):
        return any(alias.name.rsplit(".", 1)[-1] in OWNERS for alias in node.names)
    return False


def test_rust_module_owns_macro_evaluation():
    assert rust.macro_payloads.__module__ == rust.__name__
    assert rust.payload_unshadowed.__module__ == rust.__name__
    assert not (ROOT / "macro_evaluation.py").exists()
