from __future__ import annotations

import re
from typing import Any, Callable

EXACT_MIN_SCORE = 1.0


def _product_line_key(item: dict[str, Any]) -> str:
    row = item.get("row") or {}
    name = str(row.get("product_name") or "").strip().lower()
    if not name:
        return str(row.get("product_code") or "").strip().lower()
    return name.split()[0].strip(".,;:/\\-_()[]{}<>\"'`")


def _diversify_by_product_line(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 1 or len(items) <= 1:
        return items

    buckets: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for item in items:
        key = _product_line_key(item)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(item)

    if len(order) <= 1:
        return items

    diversified: list[dict[str, Any]] = []
    while len(diversified) < len(items):
        added = False
        for key in order:
            bucket = buckets.get(key) or []
            if not bucket:
                continue
            diversified.append(bucket.pop(0))
            added = True
            if len(diversified) >= len(items):
                break
        if not added:
            break
    return diversified


def _num_from_item(item: dict[str, Any], key: str) -> float | None:
    row = item.get("row") or {}
    candidates = [row.get(key)]
    helper_map = {
        "power_max_w": "power_max_value",
        "lumen_output": "lumen_output_value",
        "efficacy_lm_w": "efficacy_value",
    }
    if key in helper_map:
        candidates.insert(0, row.get(helper_map[key]))
    for value in candidates:
        m = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
        if not m:
            continue
        try:
            return float(m.group(0))
        except ValueError:
            continue
    return None


def _sort_for_mode(items: list[dict[str, Any]], sort_mode: str) -> list[dict[str, Any]]:
    mode = str(sort_mode or "score_desc")
    if mode == "score_asc":
        return sorted(items, key=lambda x: (float(x.get("score") or 0.0), str((x.get("row") or {}).get("product_code") or "")))
    if mode == "score_desc":
        return sorted(
            items,
            key=lambda x: (float(x.get("score") or 0.0), float(x.get("text_relevance") or 0.0), str((x.get("row") or {}).get("product_code") or "")),
            reverse=True,
        )
    if mode == "code_asc":
        return sorted(items, key=lambda x: str((x.get("row") or {}).get("product_code") or ""))
    if mode == "code_desc":
        return sorted(items, key=lambda x: str((x.get("row") or {}).get("product_code") or ""), reverse=True)

    numeric_modes = {
        "price_asc": ("price", "asc"),
        "price_desc": ("price", "desc"),
        "power_asc": ("power_max_w", "asc"),
        "power_desc": ("power_max_w", "desc"),
        "efficacy_desc": ("efficacy_lm_w", "desc"),
        "lumen_desc": ("lumen_output", "desc"),
    }
    if mode in numeric_modes:
        key, direction = numeric_modes[mode]
        desc = direction == "desc"
        return sorted(
            items,
            key=lambda x: (
                _num_from_item(x, key) is None,
                -(_num_from_item(x, key) or 0.0) if desc else (_num_from_item(x, key) or 0.0),
                str((x.get("row") or {}).get("product_code") or ""),
            ),
        )
    return items


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
    sort_mode: str = "score_desc",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact_pool = _sort_for_mode(exact_pool, "score_desc")
    similar_pool = _sort_for_mode(similar_pool, "score_desc")

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

    family_only_query = (
        not hard_filters
        and set((soft_filters or {}).keys()) == {"product_family"}
        and bool((text_query or "").strip())
    )
    if family_only_query:
        exact_scored = _diversify_by_product_line(exact_scored, limit)

    if str(sort_mode or "score_desc") != "score_desc":
        exact_scored = _sort_for_mode(exact_scored, sort_mode)
        similar_scored = _sort_for_mode(similar_scored, sort_mode)

    exact_scored = exact_scored[:limit]
    if include_similar:
        similar_scored = similar_scored[:limit]
    else:
        similar_scored = []

    return exact_scored, similar_scored
