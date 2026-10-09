"""Normalized extraction contract; per-language modules own grammar policies.

Other language-pack grammars retain the historical generic fallback. Registry is
not an allowlist, and TSX shares TypeScript/JSX extraction behavior.
"""

from dataclasses import replace
from functools import lru_cache

from . import elixir, go, java, kotlin, python, rust, typescript
from . import javascript as script
from .base import LanguageAdapter
from ..discovery import require_supported_language
from .resolution import ResolutionAdapter

DEFAULT_METRICS = replace(
    kotlin.METRICS,
    decision_overrides={
        **python.METRICS.decision_overrides,
        **rust.METRICS.decision_overrides,
        **elixir.METRICS.decision_overrides,
    },
    extra_scope=elixir.METRICS.extra_scope,
)

DEFAULT_ADAPTER = LanguageAdapter(metrics=DEFAULT_METRICS)
ADAPTERS = {
    "javascript": script.ADAPTER,
    "jsx": script.ADAPTER,
    "typescript": typescript.ADAPTER,
    "tsx": typescript.ADAPTER,
    "java": java.ADAPTER,
    "kotlin": kotlin.ADAPTER,
    "go": go.ADAPTER,
    "rust": rust.ADAPTER,
    "elixir": elixir.ADAPTER,
    "python": python.ADAPTER,
}


def get_adapter(language: str) -> LanguageAdapter:
    """Select grammar-specific hooks, rejecting unsupported importer languages."""
    require_supported_language(language)
    return ADAPTERS.get(language, DEFAULT_ADAPTER)


_RESOLUTIONS = {
    "python": python.PythonResolution,
    "javascript": script.JavaScriptResolution,
    "jsx": script.JavaScriptResolution,
    "typescript": script.JavaScriptResolution,
    "tsx": script.JavaScriptResolution,
    "java": java.JavaResolution,
    "kotlin": kotlin.KotlinResolution,
    "go": go.GoResolution,
    "rust": rust.RustResolution,
    "elixir": elixir.ElixirResolution,
}


@lru_cache(maxsize=None)
def get_resolution_adapter(language: str) -> ResolutionAdapter:
    """Return the language policy, or the conservative generic fallback."""
    return _RESOLUTIONS.get(language, ResolutionAdapter)()
