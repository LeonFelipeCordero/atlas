"""Independent registries for metric policies and resolution policies."""

from dataclasses import replace
from functools import lru_cache

from ...parsing.discovery import (
    SUPPORTED_LANGUAGES as SUPPORTED_LANGUAGES,
    require_supported_language,
)

from . import elixir, go, java, javascript, kotlin, python, rust, typescript
from .base import MetricAdapter, MetricPolicy as MetricPolicy
from .resolution import ResolutionAdapter
from .generic import GenericResolution, receiver_coverage as _receiver_coverage

DEFAULT_METRICS = replace(
    kotlin.METRICS,
    decision_overrides={
        **python.METRICS.decision_overrides,
        **rust.METRICS.decision_overrides,
        **elixir.METRICS.decision_overrides,
    },
    extra_scope=elixir.METRICS.extra_scope,
)
DEFAULT_ADAPTER = MetricAdapter(metrics=DEFAULT_METRICS)
ADAPTERS = {
    "javascript": javascript.ADAPTER,
    "jsx": javascript.ADAPTER,
    "typescript": typescript.ADAPTER,
    "tsx": typescript.ADAPTER,
    "java": java.ADAPTER,
    "kotlin": kotlin.ADAPTER,
    "go": go.ADAPTER,
    "rust": rust.ADAPTER,
    "elixir": elixir.ADAPTER,
    "python": python.ADAPTER,
}


def get_metric_adapter(language: str) -> MetricAdapter:
    """Select metric hooks using the importer language catalog, not extraction."""
    require_supported_language(language)
    return ADAPTERS.get(language, DEFAULT_ADAPTER)


_RESOLUTIONS = {
    "python": python.PythonResolution,
    "javascript": javascript.JavaScriptResolution,
    "jsx": javascript.JavaScriptResolution,
    "typescript": typescript.TypeScriptResolution,
    "tsx": typescript.TypeScriptResolution,
    "java": java.JavaResolution,
    "kotlin": kotlin.KotlinResolution,
    "go": go.GoResolution,
    "rust": rust.RustResolution,
    "elixir": elixir.ElixirResolution,
}


def receiver_coverage() -> dict[str, dict[str, object]]:
    """Inventory dedicated receiver policies and generic fallbacks across the catalog."""
    return _receiver_coverage(SUPPORTED_LANGUAGES, _RESOLUTIONS)


@lru_cache(maxsize=None)
def get_resolution_adapter(language: str) -> ResolutionAdapter:
    """Return the resolution policy, or the conservative generic fallback."""
    dedicated = _RESOLUTIONS.get(language)
    return dedicated() if dedicated else GenericResolution(language)
