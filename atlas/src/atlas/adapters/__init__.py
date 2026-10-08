"""Normalized extraction contract; per-language modules own grammar policies.

Other language-pack grammars retain the historical generic fallback. Registry is
not an allowlist, and TSX shares TypeScript/JSX extraction behavior.
"""

from dataclasses import replace
from functools import lru_cache

from . import elixir, go, java, kotlin, python, rust, typescript
from . import javascript as script
from .base import LanguageAdapter, COMMON_METRICS
from ..discovery import require_supported_language
from .resolution import ResolutionAdapter

PYTHON_METRICS = replace(
    COMMON_METRICS, decision_overrides={"case_clause": python.case_decision}
)
KOTLIN_METRICS = replace(
    COMMON_METRICS, extra_alternative=kotlin.alternative, body_node="function_body"
)
RUST_METRICS = replace(
    COMMON_METRICS, decision_overrides={"match_arm": rust.match_decision}
)
ELIXIR_METRICS = replace(
    COMMON_METRICS,
    decision_overrides={
        "call": elixir.call_decision,
        "stab_clause": elixir.clause_decision,
        "binary_operator": elixir.guard_decision,
    },
    extra_scope=elixir.scope,
)
DEFAULT_METRICS = replace(
    KOTLIN_METRICS,
    decision_overrides={
        **PYTHON_METRICS.decision_overrides,
        **RUST_METRICS.decision_overrides,
        **ELIXIR_METRICS.decision_overrides,
    },
    extra_scope=elixir.scope,
)

DEFAULT_ADAPTER = LanguageAdapter(metrics=DEFAULT_METRICS)
SCRIPT_ADAPTER = LanguageAdapter(
    declaration_query=script.SCRIPT_QUERY,
    callback_types=script.SCRIPT_CALLBACKS,
    normalize_declaration=script.script_declaration,
    call_sites=script.call_sites,
    inheritance_policy=script.INHERITANCE,
    normalize_call=script.normalize_call,
    metadata=script.metadata,
    call_relationship=script.call_relationship,
    metrics=COMMON_METRICS,
)
TYPESCRIPT_ADAPTER = LanguageAdapter(
    declaration_query=typescript.QUERY,
    callback_types=script.SCRIPT_CALLBACKS,
    normalize_declaration=typescript.declaration,
    call_sites=script.call_sites,
    inheritance_policy=script.INHERITANCE,
    normalize_call=script.normalize_call,
    metadata=script.metadata,
    call_relationship=script.call_relationship,
    metrics=COMMON_METRICS,
)
ADAPTERS = {
    "javascript": SCRIPT_ADAPTER,
    "jsx": SCRIPT_ADAPTER,
    "typescript": TYPESCRIPT_ADAPTER,
    "tsx": TYPESCRIPT_ADAPTER,
    "java": LanguageAdapter(
        declaration_query=java.QUERY,
        callback_types=java.CALLBACK_TYPES,
        normalize_declaration=java.declaration,
        call_sites=java.call_sites,
        inheritance_policy=java.INHERITANCE,
        metadata=java.metadata,
        metrics=COMMON_METRICS,
    ),
    "kotlin": LanguageAdapter(
        declaration_query=kotlin.QUERY,
        callback_types=kotlin.CALLBACK_TYPES,
        normalize_declaration=kotlin.declaration,
        call_sites=kotlin.call_sites,
        import_node=kotlin.IMPORT_NODE,
        inheritance_policy=kotlin.INHERITANCE,
        normalize_call=kotlin.normalize_call,
        metadata=kotlin.metadata,
        metrics=KOTLIN_METRICS,
    ),
    "go": LanguageAdapter(
        declaration_query=go.QUERY,
        callback_types=go.CALLBACK_TYPES,
        normalize_declaration=go.declaration,
        call_sites=go.call_sites,
        inheritance_policy=go.INHERITANCE,
        metrics=COMMON_METRICS,
    ),
    "rust": LanguageAdapter(
        declaration_query=rust.QUERY,
        callback_types=rust.CALLBACK_TYPES,
        normalize_declaration=rust.declaration,
        call_sites=rust.rust_call_sites,
        import_node=rust.IMPORT_NODE,
        inheritance_policy=rust.INHERITANCE,
        normalize_call=rust.rust_call_target,
        accept_import=rust.rust_module_import,
        metadata=rust.metadata,
        metrics=RUST_METRICS,
    ),
    "elixir": LanguageAdapter(
        declaration_query=elixir.QUERY,
        callback_types=elixir.CALLBACK_TYPES,
        normalize_declaration=elixir.declaration,
        call_sites=elixir.elixir_call_sites,
        inheritance_policy=elixir.INHERITANCE,
        normalize_call=elixir.elixir_call_target,
        metrics=ELIXIR_METRICS,
    ),
    "python": LanguageAdapter(
        declaration_query=python.QUERY,
        callback_types=python.CALLBACK_TYPES,
        normalize_declaration=python.declaration,
        call_sites=python.call_sites,
        inheritance_policy=python.INHERITANCE,
        metrics=PYTHON_METRICS,
    ),
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
