"""app/merged_parser.py
Single flat filters dict, combining:
- local_parser: broad extraction + natural language operators (bigger than -> > etc.)
- ai_parser: better normalization for some core fields, but ONLY when it improves the value.
"""

from typing import Any, Dict

from app.local_parser import local_text_to_filters
from app.ai_parser import text_to_filters as ai_text_to_filters


AI_BETTER_KEYS = {
    "product_family",
    "ip_rating",
    "ik_rating",
    "cct_k",
    "power_min_w",
    "power_max_w",
    "lumen_output",
    "efficacy_lm_w",
}


def _is_more_expressive(v: Any) -> bool:
    """True if value includes operators or ranges (more useful for filtering)."""
    s = str(v or "").strip()
    if not s:
        return False
    # operators or ranges
    return any(op in s for op in [">=", "<=", ">", "<"]) or ("-" in s)


def _should_override(key: str, base_v: Any, ai_v: Any) -> bool:
    """Override only when AI adds real value (keeps local 'bigger than' behavior)."""
    if base_v is None or str(base_v).strip() == "":
        return True  # local missing -> take AI

    if key not in AI_BETTER_KEYS:
        return False

    # If local already has operators/range and AI doesn't, KEEP local.
    if _is_more_expressive(base_v) and not _is_more_expressive(ai_v):
        return False

    # If AI has operators/range and local doesn't, prefer AI.
    if _is_more_expressive(ai_v) and not _is_more_expressive(base_v):
        return True

    # For IP/IK, AI can normalize IPX->IP0 etc.; override if AI looks like IP/IK format
    if key in ("ip_rating", "ik_rating"):
        a = str(ai_v or "").upper().replace(" ", "")
        if ("IP" in a) or ("IK" in a):
            return True

    # Otherwise keep local (sa già gestire "bigger than", "at least", ecc.)
    return False


def merged_text_to_filters(text: str) -> Dict[str, Any]:
    base = local_text_to_filters(text) or {}

    ai = ai_text_to_filters(text) or {}
    hard = ai.get("hard_filters", {}) or {}
    soft = ai.get("soft_filters", {}) or {}
    ai_flat: Dict[str, Any] = {**hard, **soft}

    for k, v in ai_flat.items():
        if v is None:
            continue
        if k not in base:
            base[k] = v
        else:
            if _should_override(k, base.get(k), v):
                base[k] = v

    return base

