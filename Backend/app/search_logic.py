from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from app.schema import ProductHit, SearchRequest, SearchResponse


FAMILY_ALIASES = {
    "road lighting": "street lighting",
}


def _family_token_base(token: str) -> str:
    t = str(token or "").strip().lower()
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith("es"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s"):
        return t[:-1]
    return t


def _family_norm(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower())
    tokens = [_family_token_base(tok) for tok in text.split() if tok]
    return " ".join(tokens)


def _resolve_allowed_family(value: Any, allowed_families: List[str]) -> Any:
    raw = str(value or "").strip()
    if not raw or not allowed_families:
        return value
    raw = FAMILY_ALIASES.get(raw.lower(), raw)

    exact_map = {
        str(fam).strip().lower(): fam
        for fam in allowed_families
        if str(fam).strip()
    }
    if raw.lower() in exact_map:
        return exact_map[raw.lower()]

    norm_target = _family_norm(raw)
    if not norm_target:
        return value

    norm_map = {
        _family_norm(fam): fam
        for fam in allowed_families
        if str(fam).strip()
    }
    if norm_target in norm_map:
        return norm_map[norm_target]

    for fam in allowed_families:
        fam_norm = _family_norm(fam)
        if fam_norm and (fam_norm in norm_target or norm_target in fam_norm):
            return fam
    return value


def _normalize_product_family_filter(filters: Dict[str, Any], allowed_families: List[str]) -> Dict[str, Any]:
    out = dict(filters or {})
    if "product_family" not in out:
        return out
    value = out.get("product_family")
    if isinstance(value, list):
        out["product_family"] = [_resolve_allowed_family(item, allowed_families) for item in value]
    else:
        out["product_family"] = _resolve_allowed_family(value, allowed_families)
    return out


def handle_search(
    req: SearchRequest,
    *,
    local_text_to_filters: Callable[[str], Dict[str, Any] | None],
    sanitize_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    normalize_ui_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    llm_intent_to_filters: Callable[..., Dict[str, Any]],
    allowed_families: List[str],
    infer_interpreted: Callable[[str], Dict[str, Any]],
    map_filters_to_sql: Callable[[Dict[str, Any]], Dict[str, Any]],
    cfg_list: Callable[[str, list[str]], list[str]],
    cfg_int: Callable[[str, int], int],
    cfg_float: Callable[[str, float], float],
    score_product: Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Any],
    product_db: Any,
    db_runtime_backend: str,
    db_dataframe: Any,
    search_rows_by_text_db: Callable[[str, int], List[Dict[str, Any]]],
    dedupe_rows_by_product_code: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
    text_relevance: Callable[[Dict[str, Any], str], float],
    select_exact_and_similar: Callable[..., Any],
    manufacturer_label: Callable[[Any], str],
    build_website_url: Callable[[str, str], str],
    build_datasheet_url: Callable[[str, str], str],
    clean_value: Callable[[Any], Any],
    logger: Any,
    quote_plus: Callable[[str], str],
    include_price: bool = True,
    max_limit: int = 100,
    llm_intent_to_filters_with_meta: Optional[Callable[..., Dict[str, Any]]] = None,
) -> SearchResponse:
    print("=== /search START ===")
    print("req.filters RAW:", req.filters)

    parsed = local_text_to_filters(req.text or "") or {}
    parsed = sanitize_filters(parsed)

    logger.info(f"SEARCH CALLED text={req.text!r}")

    llm_extra: Dict[str, Any] = {}
    ai_meta: Dict[str, Any] = {"status": "skipped", "message": "", "used_retry": False, "model": "", "provider": "openai"}
    try:
        if getattr(req, "allow_ai", True) and (req.text or "").strip():
            logger.info("Calling LLM...")
            if callable(llm_intent_to_filters_with_meta):
                ai_meta = llm_intent_to_filters_with_meta(req.text or "", allowed_families=allowed_families) or ai_meta
                llm_extra = dict(ai_meta.get("filters") or {})
            else:
                llm_extra = llm_intent_to_filters(req.text or "", allowed_families=allowed_families) or {}
                ai_meta = {
                    "status": "ok",
                    "message": "",
                    "used_retry": False,
                    "model": "",
                    "provider": "openai",
                }
            logger.info(f"LLM EXTRA {llm_extra}")
    except Exception:
        logger.exception("LLM ERROR")
        llm_extra = {}
        ai_meta = {
            "status": "error",
            "message": "AI parsing failed, so the search continued with deterministic filters only.",
            "used_retry": False,
            "model": "",
            "provider": "openai",
        }

    if "ugr" in llm_extra and not any(ch.isdigit() for ch in (req.text or "")):
        llm_extra.pop("ugr", None)
        llm_extra.pop("ugr_value", None)
        llm_extra.pop("ugr_op", None)

    for k, v in llm_extra.items():
        if k not in parsed and v is not None:
            parsed[k] = v

    ignored_ai_filters = getattr(req, "ignored_ai_filters", None) or []
    if isinstance(ignored_ai_filters, list) and ignored_ai_filters:
        for item in ignored_ai_filters:
            if not isinstance(item, dict):
                continue
            k = str(item.get("key") or item.get("k") or "").strip()
            if not k or k not in parsed:
                continue
            v = item.get("value", item.get("v"))
            if v is None or str(v).strip() == "":
                parsed.pop(k, None)
                continue
            cur = parsed.get(k)
            if isinstance(cur, list):
                kept = [x for x in cur if str(x) != str(v)]
                if not kept:
                    parsed.pop(k, None)
                elif len(kept) == 1:
                    parsed[k] = kept[0]
                else:
                    parsed[k] = kept
            else:
                if str(cur) == str(v):
                    parsed.pop(k, None)

    user_filters = sanitize_filters(req.filters or {})
    user_filters = normalize_ui_filters(user_filters)
    if not str(req.text or "").strip() and not user_filters:
        return SearchResponse(
            exact=[],
            similar=[],
            interpreted={"empty_search": True},
            backend_debug_filters=({"filters": {}, "hard_filters": {}, "soft_filters": {}} if getattr(req, "debug", False) else None),
        )

    parsed_filters = _normalize_product_family_filter(dict(parsed), allowed_families)
    user_filters = _normalize_product_family_filter(dict(user_filters), allowed_families)
    filters = {**parsed_filters, **user_filters}
    hard_filters = dict(user_filters)
    ai_family = parsed_filters.get("product_family")
    if ai_family not in (None, "", []):
        # Treat AI-inferred family as a hard constraint so AI and UI family searches
        # behave the same way in the exact-match path.
        hard_filters.setdefault("product_family", ai_family)
    soft_filters: Dict[str, Any] = dict(parsed_filters)
    similar_score_filters = dict(filters)
    sql_filters = map_filters_to_sql(filters)
    hard_sql_filters = map_filters_to_sql(hard_filters)

    raw_text = str(req.text or "")
    spec_signal_keys = set(cfg_list("main.spec_signal_keys", [
        "ip_rating", "ip_visible", "ip_non_visible", "ik_rating", "cct_k", "cri", "ugr",
        "power_max_w", "power_min_w", "lumen_output", "efficacy_lm_w",
        "beam_angle_deg", "control_protocol", "emergency_present",
        "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct", "failure_rate_pct",
        "diameter", "luminaire_length", "luminaire_width", "luminaire_height",
        "ambient_temp_min_c", "ambient_temp_max_c", "shape",
    ]))
    parsed_spec_count = sum(1 for k in parsed.keys() if k in spec_signal_keys)
    spec_token_hits = len(re.findall(r"\b(?:ip\d{2}|ik\d{1,2}|cri|ugr|dali|lm/?w|lm|l\d{2}\s*b\s*\d{1,2})\b", raw_text.lower()))
    spec_like_search_mode = bool(
        raw_text.strip()
        and len(raw_text) >= cfg_int("main.spec_mode_min_text_len", 70)
        and (
            parsed_spec_count >= cfg_int("main.spec_mode_min_parsed_specs", 4)
            or (
                parsed_spec_count >= cfg_int("main.spec_mode_min_parsed_specs_with_tokens", 3)
                and spec_token_hits >= cfg_int("main.spec_mode_min_token_hits", 3)
            )
        )
    )
    spec_like_exact_threshold = cfg_float("main.spec_mode_exact_threshold", 0.72)
    q_l = raw_text.strip().lower()
    has_spec_markers = bool(re.search(r"\b(?:ip\d{1,2}|ik\d{1,2}|cri|ugr|dali|lm/?w|l\d{2}\s*b\s*\d{1,2})\b", q_l))
    has_cmp_markers = bool(re.search(r"(>=|<=|>|<|=)", q_l))
    name_search_mode = bool(
        q_l
        and len(q_l) <= 60
        and not parsed
        and not user_filters
        and not has_spec_markers
        and not has_cmp_markers
    )

    print("filters:", filters)
    print("sql_filters:", sql_filters)

    interpreted = infer_interpreted(req.text or "")
    if not isinstance(interpreted, dict):
        interpreted = {}
    if (req.text or "").strip():
        interpreted["ai_status"] = str(ai_meta.get("status") or "skipped")
        if ai_meta.get("message"):
            interpreted["ai_note"] = str(ai_meta.get("message") or "")
        if ai_meta.get("used_retry"):
            interpreted["ai_note"] = str(ai_meta.get("message") or "AI parsing succeeded after a retry/fallback.")
        if ai_meta.get("model"):
            interpreted["ai_model"] = str(ai_meta.get("model") or "")
    if parsed:
        label_map = {
            "product_family": "family",
            "ip_rating": "IP total",
            "ip_visible": "IP v.l.",
            "ip_non_visible": "IP v.a.",
            "ik_rating": "IK",
            "cct_k": "CCT",
            "cri": "CRI",
            "ugr": "UGR",
            "power_max_w": "Power",
            "lumen_output": "Lumens",
            "efficacy_lm_w": "Efficacy",
            "control_protocol": "Control",
            "interface": "Interface",
            "emergency_present": "Emergency",
            "shape": "Shape",
            "lifetime_hours": "Lifetime",
            "lumen_maintenance_pct": "L maint",
        }
        preferred_order = [
            "product_family", "ip_rating", "ip_visible", "ip_non_visible", "ik_rating", "cct_k", "cri", "ugr",
            "lumen_output", "power_max_w", "efficacy_lm_w", "shape",
            "control_protocol", "interface", "emergency_present", "lifetime_hours", "lumen_maintenance_pct",
        ]
        understood_items: List[Dict[str, Any]] = []
        parts: List[str] = []

        def append_understood_item(key: str, val: Any):
            if val is None:
                return
            s = str(val).strip()
            if not s:
                return
            understood_items.append({"key": key, "label": label_map.get(key, key), "value": s})

        for k in preferred_order:
            if k not in parsed:
                continue
            v = parsed.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            label = label_map.get(k, k)
            if isinstance(v, list):
                vals = [str(x) for x in v if str(x).strip()]
                if not vals:
                    continue
                parts.append(f"{label}: {', '.join(vals)}")
                for one in vals:
                    append_understood_item(k, one)
            else:
                val = str(v)
                parts.append(f"{label}: {val}")
                append_understood_item(k, val)
        for k, v in parsed.items():
            if k in preferred_order:
                continue
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            label = label_map.get(k, k)
            if isinstance(v, list):
                vals = [str(x) for x in v if str(x).strip()]
                if not vals:
                    continue
                parts.append(f"{label}: {', '.join(vals)}")
                for one in vals:
                    append_understood_item(k, one)
            else:
                parts.append(f"{label}: {v}")
                append_understood_item(k, v)
        if parts:
            interpreted["understood_summary"] = "Searching for: " + " | ".join(parts[:10])
            interpreted["understood_filters"] = parts
            interpreted["understood_filter_items"] = understood_items[:50]
    if spec_like_search_mode:
        interpreted["search_mode"] = "spec_first"
        interpreted["search_mode_note"] = "Tender/spec-like query detected; exact results use spec similarity threshold."

    recovery_actions: List[Dict[str, Any]] = []
    if parsed.get("ugr") is not None:
        recovery_actions.append({"id": "relax_ugr", "label": "Allow a higher UGR"})
    if parsed.get("ip_rating") is not None:
        recovery_actions.append({"id": "relax_ip", "label": "Lower the IP requirement"})
    if parsed.get("ik_rating") is not None:
        recovery_actions.append({"id": "relax_ik", "label": "Lower the IK requirement"})
    if parsed.get("power_max_w") is not None:
        recovery_actions.append({"id": "widen_power", "label": "Widen the power range"})
    if user_filters:
        recovery_actions.append({"id": "clear_filters", "label": "Clear some filters and keep the query"})

    limit = min(max(1, int(req.limit or 20)), max(1, int(max_limit or 100)))
    candidate_limit = min(
        max(limit * cfg_int("main.search_candidate_multiplier", 30), cfg_int("main.search_candidate_min", 500)),
        cfg_int("main.search_candidate_max", 10000),
    )
    rows: List[Dict[str, Any]] = []
    used_product_db = False
    exact_seed_codes: set[str] = set()

    if product_db:
        used_product_db = True
        try:
            exact_seed = product_db.search_products(hard_sql_filters, limit=candidate_limit) if hard_sql_filters else []
            exact_seed_codes = {
                str((row or {}).get("product_code", "")).strip()
                for row in exact_seed
                if str((row or {}).get("product_code", "")).strip()
            }
            name_seed_filters: Dict[str, Any] = {}
            for key in ("product_name_contains", "product_name_short", "name_prefix"):
                if key in hard_filters:
                    name_seed_filters[key] = hard_filters[key]
            name_seed_sql = map_filters_to_sql(name_seed_filters) if name_seed_filters else {}
            name_seed = product_db.search_products(name_seed_sql, limit=candidate_limit) if name_seed_sql else []

            family_seed_filters: Dict[str, Any] = {}
            family_value = filters.get("product_family")
            if family_value not in (None, "", []):
                family_seed_filters["product_family"] = family_value
            family_seed_sql = map_filters_to_sql(family_seed_filters) if family_seed_filters else {}
            family_seed = product_db.search_products(family_seed_sql, limit=candidate_limit) if family_seed_sql else []

            text_seed = search_rows_by_text_db(req.text or "", limit=candidate_limit)
            broad_rows = product_db.search_products({}, limit=candidate_limit)
            rows = dedupe_rows_by_product_code(exact_seed + family_seed + name_seed + text_seed + broad_rows)[:candidate_limit]
        except Exception as e:
            print(f"Product database search failed: {e}")
            used_product_db = False
            rows = []

    if not rows and (db_dataframe is not None and not db_dataframe.empty):
        narrowed = db_dataframe.copy()
        rows = narrowed.head(candidate_limit).fillna("").to_dict(orient="records")

    exact_pool: List[Dict[str, Any]] = []
    similar_pool: List[Dict[str, Any]] = []
    anchor_family = ""
    anchor_rel = -1.0
    for r in rows:
        product_code = str((r or {}).get("product_code", "")).strip()
        exact_score, exact_matched, exact_dev, exact_missing = score_product(r, hard_filters, {})
        sim_filter_score, soft_matched, soft_dev, soft_missing = score_product(r, {}, similar_score_filters)
        manual_score = 0.0
        if user_filters:
            manual_score, _mm, _md, _mms = score_product(r, {}, user_filters)
        rel = text_relevance(r, req.text or "")
        if name_search_mode and rel > anchor_rel:
            fam = str(r.get("product_family") or "").strip().lower()
            if fam:
                anchor_rel = float(rel)
                anchor_family = fam

        passes_manual_filters = float(exact_score) > 0.0
        if not passes_manual_filters:
            continue

        exact_candidate_score = float(sim_filter_score) if similar_score_filters else float(exact_score)
        exact_candidate_matched = soft_matched if similar_score_filters else exact_matched
        exact_candidate_dev = soft_dev if similar_score_filters else exact_dev
        exact_candidate_missing = soft_missing if similar_score_filters else exact_missing

        if spec_like_search_mode and similar_score_filters:
            if (
                float(sim_filter_score) >= spec_like_exact_threshold
                and passes_manual_filters
                and ((not hard_filters) or (product_code in exact_seed_codes))
            ):
                exact_pool.append({"row": r, "score": exact_candidate_score, "text_relevance": float(rel), "matched": exact_candidate_matched, "deviations": exact_candidate_dev, "missing": exact_candidate_missing})
        elif exact_candidate_score > 0 and ((not hard_filters) or (product_code in exact_seed_codes)):
            exact_pool.append({"row": r, "score": exact_candidate_score, "text_relevance": float(rel), "matched": exact_candidate_matched, "deviations": exact_candidate_dev, "missing": exact_candidate_missing})

        if similar_score_filters:
            sim_score = float(sim_filter_score)
            if user_filters:
                sim_score = max(0.0, min(1.0, 0.7 * float(manual_score) + 0.3 * float(sim_filter_score)))
        else:
            sim_score = max(float(sim_filter_score), min(1.0, float(sim_filter_score) + rel * cfg_float("main.similar_text_boost", 0.35)))
        if sim_score > 0 or rel > 0:
            similar_pool.append({"row": r, "score": sim_score, "text_relevance": float(rel), "matched": soft_matched, "deviations": soft_dev, "missing": soft_missing})

    if name_search_mode and anchor_family:
        similar_pool = [s for s in similar_pool if str((s.get("row") or {}).get("product_family") or "").strip().lower() == anchor_family]

    if spec_like_search_mode and not exact_pool and similar_score_filters:
        top_sim: List[Dict[str, Any]] = []
        floor = cfg_float("main.spec_mode_fallback_floor", 0.55)
        for x in similar_pool:
            if float(x.get("score") or 0.0) < floor:
                continue
            hard_s, _m, _d, _miss = score_product(x.get("row", {}), hard_filters, {})
            if float(hard_s) > 0.0:
                top_sim.append(x)
        top_sim.sort(key=lambda x: (float(x.get("score") or 0.0), float(x.get("text_relevance") or 0.0)), reverse=True)
        exact_pool = top_sim[: max(limit * 2, 10)]

    exact_scored, similar_scored = select_exact_and_similar(
        exact_pool=exact_pool,
        similar_pool=similar_pool,
        rows=rows,
        text_query=req.text or "",
        hard_filters=hard_filters,
        soft_filters=soft_filters,
        limit=limit,
        include_similar=getattr(req, "include_similar", True),
        text_relevance_fn=text_relevance,
    )

    exact_hits: List[ProductHit] = []
    similar_hits: List[ProductHit] = []
    for s in exact_scored:
        r = s["row"]
        manufacturer = manufacturer_label(r.get("manufacturer"))
        product_code = str(r.get("product_code", "")).strip()
        website_url = build_website_url(product_code, manufacturer)
        datasheet_url = build_datasheet_url(product_code, manufacturer)
        exact_hits.append(ProductHit(
            product_code=product_code,
            product_name=str(r.get("product_name", "")).strip(),
            score=s["score"],
            matched=s["matched"],
            deviations=s["deviations"],
            missing=s["missing"],
            preview={
                "ip_rating": clean_value(r.get("ip_rating")),
                "ik_rating": clean_value(r.get("ik_rating")),
                "cct_k": clean_value(r.get("cct_k")),
                "power_max_w": clean_value(r.get("power_max_w")),
                "lumen_output": clean_value(r.get("lumen_output")),
                "efficacy_lm_w": clean_value(r.get("efficacy_lm_w")),
                "ugr": clean_value(r.get("ugr")),
                "ugr_value": clean_value(r.get("ugr_value")),
                "warranty_years": clean_value(r.get("warranty_years")),
                "lifetime_hours": clean_value(r.get("lifetime_hours")),
                "led_rated_life_h": clean_value(r.get("led_rated_life_h")),
                "lumen_maintenance_pct": clean_value(r.get("lumen_maintenance_pct")),
                "manufacturer": manufacturer,
                "price": clean_value(r.get("price")) if include_price else None,
                "website_url": website_url,
                "datasheet_url": datasheet_url,
                "image_preview_url": f"/preview-image?product_code={quote_plus(product_code)}&manufacturer={quote_plus(manufacturer)}&website_url={quote_plus(website_url)}",
            },
            debug_filters=({
                "filters": filters,
                "hard_filters": hard_filters,
                "soft_filters": soft_filters,
                "sql_filters": sql_filters,
                "hard_sql_filters": hard_sql_filters,
                "used_product_db": used_product_db,
                "product_db_backend": getattr(product_db, "backend", db_runtime_backend),
                "text_relevance": s.get("text_relevance", 0.0),
                "match_tier": s.get("match_tier", "exact"),
            } if getattr(req, "debug", False) else None),
            raw=None,
        ))

    for s in similar_scored:
        r = s["row"]
        manufacturer = manufacturer_label(r.get("manufacturer"))
        product_code = str(r.get("product_code", "")).strip()
        website_url = build_website_url(product_code, manufacturer)
        datasheet_url = build_datasheet_url(product_code, manufacturer)
        similar_hits.append(ProductHit(
            product_code=product_code,
            product_name=str(r.get("product_name", "")).strip(),
            score=max(0.0, min(1.0, float(s["score"]))),
            matched=s["matched"],
            deviations=s["deviations"],
            missing=s["missing"],
            preview={
                "ip_rating": clean_value(r.get("ip_rating")),
                "ik_rating": clean_value(r.get("ik_rating")),
                "cct_k": clean_value(r.get("cct_k")),
                "power_max_w": clean_value(r.get("power_max_w")),
                "lumen_output": clean_value(r.get("lumen_output")),
                "efficacy_lm_w": clean_value(r.get("efficacy_lm_w")),
                "ugr": clean_value(r.get("ugr")),
                "ugr_value": clean_value(r.get("ugr_value")),
                "warranty_years": clean_value(r.get("warranty_years")),
                "lifetime_hours": clean_value(r.get("lifetime_hours")),
                "led_rated_life_h": clean_value(r.get("led_rated_life_h")),
                "lumen_maintenance_pct": clean_value(r.get("lumen_maintenance_pct")),
                "manufacturer": manufacturer,
                "price": clean_value(r.get("price")) if include_price else None,
                "website_url": website_url,
                "datasheet_url": datasheet_url,
                "image_preview_url": f"/preview-image?product_code={quote_plus(product_code)}&manufacturer={quote_plus(manufacturer)}&website_url={quote_plus(website_url)}",
            },
            debug_filters=({
                "filters": filters,
                "hard_filters": hard_filters,
                "soft_filters": soft_filters,
                "similar_score_filters": similar_score_filters,
                "sql_filters": sql_filters,
                "hard_sql_filters": hard_sql_filters,
                "used_product_db": used_product_db,
                "product_db_backend": getattr(product_db, "backend", db_runtime_backend),
                "text_relevance": s.get("text_relevance", 0.0),
                "match_tier": s.get("match_tier", "close"),
            } if getattr(req, "debug", False) else None),
            raw=None,
        ))

    if interpreted is None:
        interpreted = {}
    interpreted["result_tiers"] = {
        "exact": len(exact_hits),
        "close": sum(1 for s in similar_scored if str(s.get("match_tier") or "close") == "close"),
        "broader": sum(1 for s in similar_scored if str(s.get("match_tier") or "") == "broader"),
    }
    if recovery_actions:
        interpreted["recovery_actions"] = recovery_actions[:4]

    return SearchResponse(
        exact=exact_hits,
        similar=similar_hits,
        interpreted=interpreted or None,
        backend_debug_filters=({
            "filters": filters,
            "hard_filters": hard_filters,
            "soft_filters": soft_filters,
            "similar_score_filters": similar_score_filters,
            "sql_filters": sql_filters,
            "hard_sql_filters": hard_sql_filters,
            "used_product_db": used_product_db,
            "product_db_backend": getattr(product_db, "backend", db_runtime_backend),
            "llm_extra": llm_extra,
            "parsed_local": parsed,
        } if getattr(req, "debug", False) else None),
    )
