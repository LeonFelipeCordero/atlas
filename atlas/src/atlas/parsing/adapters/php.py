"""PHP invocation syntax missing from the generic call-node vocabulary."""

from .base import LanguageAdapter
from ..syntax import FALLBACK_CALL_TYPES, call_sites as generic_call_sites


def call_sites(root):
    return generic_call_sites(root, FALLBACK_CALL_TYPES | {
        "function_call_expression", "member_call_expression",
        "nullsafe_member_call_expression", "scoped_call_expression",
    })


ADAPTER = LanguageAdapter(call_sites=call_sites)
