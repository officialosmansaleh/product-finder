from __future__ import annotations

from typing import Any, Callable

EXACT_MIN_SCORE = 1.0


def select_exact_and_similar(
    *,
    exact_pool: list[dict[str, Any]],
    similar_pool: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    text_query: str,
    hard_filters: dict[str, Any],
    soft_filters: dict[str, Any],
    limit: int,
    include_similar: bool,
    text_relevance_fn: Callable[[dict[str, Any], str], float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact_pool.sort(
        key=lambda x: (x["score"], x.get("text_relevance", 0.0), str(x["row"].get("product_code", ""))),
        reverse=True,
    )
    similar_pool.sort(
        key=lambda x: (x["score"], x.get("text_relevance", 0.0), str(x["row"].get("product_code", ""))),
        reverse=True,
    )

    exact_scored: list[dict[str, Any]] = []
    q = (text_query or "").strip()
    text_only_query = bool(q) and not hard_filters and not soft_filters
    for s in exact_pool:
        if float(s.get("score", 0.0)) < EXACT_MIN_SCORE:
            continue
        if text_only_query and float(s.get("text_relevance", 0.0)) <= 0.0:
            continue
        exact_scored.append(s)

    exact_codes = {str(s["row"].get("product_code", "")).strip() for s in exact_scored}
    similar_scored: list[dict[str, Any]] = [
        s for s in similar_pool if str(s["row"].get("product_code", "")).strip() not in exact_codes
    ]
    overflow_exact: list[dict[str, Any]] = []
    for s in exact_pool:
        code = str(s["row"].get("product_code", "")).strip()
        if code in exact_codes:
            continue
        overflow_exact.append(dict(s))
    if text_only_query:
        promoted_similar: list[dict[str, Any]] = []
        for s in overflow_exact:
            deviations = list(s.get("deviations", []) or [])
            if float(s.get("text_relevance", 0.0)) <= 0.0 and "fallback: text mismatch" not in deviations:
                deviations.append("fallback: text mismatch")
            promoted = dict(s)
            promoted["deviations"] = deviations
            promoted_similar.append(promoted)
        if promoted_similar:
            promoted_similar.sort(
                key=lambda x: (x["score"], x.get("text_relevance", 0.0), str(x["row"].get("product_code", ""))),
                reverse=True,
            )
            similar_scored = promoted_similar + similar_scored
    elif overflow_exact:
        similar_scored = overflow_exact + similar_scored

    q_l = (text_query or "").strip().lower()
    has_spec_tokens = any(tok in q_l for tok in ("ip", "ik", "cri", "ugr", "dali", "lm/w", "lm"))
    has_cmp_tokens = any(tok in q_l for tok in (">=", "<=", ">", "<", "="))
    has_digits = any(ch.isdigit() for ch in q_l)
    allow_relaxed_fallback = (not q_l) or (
        bool(hard_filters or soft_filters) and (len(q_l) >= 20 or has_spec_tokens or has_cmp_tokens or has_digits)
    )

    if not similar_scored and rows and allow_relaxed_fallback:
        for r in rows:
            rel = text_relevance_fn(r, text_query or "")
            base = max(0.6, min(1.0, rel * 0.5))
            similar_scored.append(
                {
                    "row": r,
                    "score": base,
                    "text_relevance": float(rel),
                    "matched": {},
                    "deviations": ["fallback: strict constraints relaxed"],
                    "missing": [],
                }
            )
        similar_scored.sort(
            key=lambda x: (x["score"], x.get("text_relevance", 0.0), str(x["row"].get("product_code", ""))),
            reverse=True,
        )

    for item in exact_scored:
        item.setdefault("match_tier", "exact")
    for item in similar_scored:
        deviations = [str(x or "").lower() for x in (item.get("deviations") or [])]
        if any("fallback: strict constraints relaxed" in x for x in deviations):
            item["match_tier"] = "broader"
        elif any("fallback: text mismatch" in x for x in deviations):
            item["match_tier"] = "broader"
        else:
            item["match_tier"] = "close"

    exact_scored = exact_scored[:limit]
    if include_similar:
        similar_scored = similar_scored[:limit]
    else:
        similar_scored = []

    return exact_scored, similar_scored
