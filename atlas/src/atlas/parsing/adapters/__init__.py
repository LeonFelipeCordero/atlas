"""Extraction registry with generic fallback for supported language-pack grammars."""

from . import elixir, go, java, javascript, kotlin, php, python, rust, typescript
from .base import LanguageAdapter
from ..discovery import require_supported_language

DEFAULT_ADAPTER = LanguageAdapter()
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
    "php": php.ADAPTER,
}


def get_adapter(language: str) -> LanguageAdapter:
    """Select extraction hooks, rejecting unsupported importer languages."""
    require_supported_language(language)
    return ADAPTERS.get(language, DEFAULT_ADAPTER)
