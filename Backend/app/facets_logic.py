from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from app.schema import FacetsResponse, FacetValue, SearchRequest


def handle_facets(
    req: SearchRequest,
    *,
    local_text_to_filters: Callable[[str], Dict[str, Any] | None],
    sanitize_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    normalize_ui_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    llm_intent_to_filters: Callable[..., Dict[str, Any]],
    allowed_families: List[str],
    allowed_families_norm: set[str],
    map_filters_to_sql: Callable[[Dict[str, Any]], Dict[str, Any]],
    facets_cache_key: Callable[[Dict[str, Any]], str],
    facets_cache_get: Callable[[str], Any],
    facets_cache_set: Callable[[str, Dict[str, Any]], None],
    cfg_int: Callable[[str, int], int],
    product_db: Any,
    db_dataframe: Any,
    product_name_short_from_rows: Callable[[List[Dict[str, Any]], int], List[FacetValue]],
    df_filtered_subset: Callable[[Any, Dict[str, Any]], Any],
    seed_filters_for_facets: Callable[[Dict[str, Any]], Dict[str, Any]],
    top_values: Callable[[Any, str, int], List[FacetValue]],
    top_product_name_short_values: Callable[[Any, int], List[FacetValue]],
    top_values_from_db_fallback: Callable[[str, int], List[FacetValue]],
    product_name_short_from_db_fallback: Callable[[int], List[FacetValue]],
    families_from_db_fallback: Callable[[int], List[FacetValue]],
    min_max_numeric: Callable[[Any, str], Dict[str, Any]],
    num_from_text_series: Callable[[pd.Series], pd.Series],
) -> FacetsResponse:
    parsed = local_text_to_filters(req.text or "") or {}
    parsed = sanitize_filters(parsed)

    llm_extra = {}
    try:
        llm_extra = (
            llm_intent_to_filters(req.text or "", allowed_families=allowed_families)
            if getattr(req, "allow_ai", True) and (req.text or "").strip()
            else {}
        )
        print("/facets LLM EXTRA:", llm_extra)
    except Exception as e:
        print("/facets LLM ERROR:", repr(e))
        llm_extra = {}

    if "product_family" in llm_extra and allowed_families_norm:
        fam = str(llm_extra.get("product_family") or "").strip().lower()
        if fam and fam not in allowed_families_norm:
            llm_extra.pop("product_family", None)

    for k, v in (llm_extra or {}).items():
        if k not in parsed and v is not None:
            parsed[k] = v

    user_filters = sanitize_filters(req.filters or {})
    user_filters = normalize_ui_filters(user_filters)
    filters = {**parsed, **user_filters}
    sql_filters = map_filters_to_sql(filters)

    cache_key = facets_cache_key(sql_filters)
    if not getattr(req, "debug", False):
        cached = facets_cache_get(cache_key)
        if cached is not None:
            return FacetsResponse(**cached)

    facet_value_limit = max(30, cfg_int("main.facets_value_limit", 200))
    name_facet_value_limit = max(facet_value_limit, cfg_int("main.facets_name_value_limit", 5000))
    narrowed = pd.DataFrame()
    product_name_short_prefill: List[FacetValue] = []

    if product_db:
        try:
            facets_sql_limit = cfg_int("main.facets_sql_limit", 10000)
            rows = product_db.search_products(sql_filters, limit=facets_sql_limit) if sql_filters else product_db.search_products({}, limit=facets_sql_limit)
            narrowed = pd.DataFrame(rows)
            product_name_short_prefill = product_name_short_from_rows(rows, limit=name_facet_value_limit)
        except Exception as e:
            print(f"Product database facets failed: {e}")

    if narrowed.empty:
        base = db_dataframe.copy() if db_dataframe is not None else pd.DataFrame()
        narrowed = df_filtered_subset(base, filters)
        narrowed = narrowed if narrowed is not None else pd.DataFrame()

    all_df = db_dataframe.copy() if db_dataframe is not None else pd.DataFrame()
    if all_df.empty and product_db:
        try:
            facets_all_limit = cfg_int("main.facets_all_sql_limit", 50000)
            all_rows = product_db.search_products({}, limit=facets_all_limit)
            all_df = pd.DataFrame(all_rows)
        except Exception:
            all_df = pd.DataFrame()

    seed_filters = seed_filters_for_facets(filters)
    broad_df = df_filtered_subset(all_df, seed_filters) if not all_df.empty else pd.DataFrame()
    family_seed_filters = {k: v for k, v in seed_filters.items() if k != "product_family"}
    broad_family_df = df_filtered_subset(all_df, family_seed_filters) if not all_df.empty else pd.DataFrame()
    strict_df = narrowed if narrowed is not None else pd.DataFrame()

    def facet_values(col: str, limit: int, fallback_col: Optional[str] = None) -> List[FacetValue]:
        vals = top_values(strict_df, col, limit=limit) or top_values(broad_df, col, limit=limit) or top_values(all_df, col, limit=limit)
        if vals:
            return vals
        if fallback_col:
            return top_values_from_db_fallback(fallback_col, limit=limit)
        return []

    def facet_values_broad_first(col: str, limit: int, fallback_col: Optional[str] = None) -> List[FacetValue]:
        src_df = broad_family_df if col == "product_family" else broad_df
        vals = top_values(src_df, col, limit=limit) or top_values(all_df, col, limit=limit)
        if vals:
            return vals
        if fallback_col:
            return top_values_from_db_fallback(fallback_col, limit=limit)
        return []

    def facet_min_max(col: str) -> Dict[str, Any]:
        mm = min_max_numeric(strict_df, col)
        if mm.get("min") is not None or mm.get("max") is not None:
            return mm
        mm = min_max_numeric(broad_df, col)
        if mm.get("min") is not None or mm.get("max") is not None:
            return mm
        return min_max_numeric(all_df, col)

    eff = num_from_text_series(strict_df["efficacy_lm_w"]) if "efficacy_lm_w" in strict_df.columns else pd.Series(dtype=float)
    pwr = num_from_text_series(strict_df["power_max_w"]) if "power_max_w" in strict_df.columns else pd.Series(dtype=float)
    if eff.empty or pwr.empty:
        eff = num_from_text_series(broad_df["efficacy_lm_w"]) if "efficacy_lm_w" in broad_df.columns else pd.Series(dtype=float)
        pwr = num_from_text_series(broad_df["power_max_w"]) if "power_max_w" in broad_df.columns else pd.Series(dtype=float)
    if eff.empty or pwr.empty:
        eff = num_from_text_series(all_df["efficacy_lm_w"]) if "efficacy_lm_w" in all_df.columns else pd.Series(dtype=float)
        pwr = num_from_text_series(all_df["power_max_w"]) if "power_max_w" in all_df.columns else pd.Series(dtype=float)
    lumen_calc = (eff * pwr).dropna()
    phot_lumen_minmax = {"min": float(lumen_calc.min()) if not lumen_calc.empty else None, "max": float(lumen_calc.max()) if not lumen_calc.empty else None}

    product_name_short_values = (
        product_name_short_prefill
        or top_product_name_short_values(strict_df, limit=name_facet_value_limit)
        or top_product_name_short_values(broad_df, limit=name_facet_value_limit)
        or top_product_name_short_values(all_df, limit=name_facet_value_limit)
        or product_name_short_from_db_fallback(limit=name_facet_value_limit)
    )

    resp = FacetsResponse(
        families=facet_values_broad_first("product_family", limit=facet_value_limit, fallback_col="product_family") or families_from_db_fallback(limit=facet_value_limit),
        product_name_short=product_name_short_values,
        similar_names=product_name_short_values,
        warranty_lifetime={
            "warranty_years": facet_values("warranty_years", limit=facet_value_limit, fallback_col="warranty_years"),
            "lifetime_hours": facet_values("lifetime_hours", limit=facet_value_limit, fallback_col="lifetime_hours"),
            "led_rated_life_h": facet_values("led_rated_life_h", limit=facet_value_limit, fallback_col="led_rated_life_h"),
            "lumen_maintenance_pct": facet_values("lumen_maintenance_pct", limit=facet_value_limit, fallback_col="lumen_maintenance_pct"),
            "certifications": facet_values("certifications", limit=facet_value_limit),
        },
        photometrics={
            "lumen_output": phot_lumen_minmax,
            "beam": [],
            "cct_k": facet_values("cct_k", limit=facet_value_limit),
            "cri": facet_values("cri", limit=facet_value_limit),
            "ugr": facet_values("ugr_value", limit=facet_value_limit, fallback_col="ugr_value"),
            "asymmetry_deg": facet_values("asymmetry", limit=facet_value_limit),
        },
        power_voltage={
            "power_max_w": facet_min_max("power_max_w"),
            "power_factor": facet_values("power_factor", limit=facet_value_limit),
            "voltage_range": facet_values("voltage_range", limit=facet_value_limit),
            "control_protocol": facet_values("control_protocol", limit=facet_value_limit),
            "interface": facet_values("interface", limit=facet_value_limit),
            "emergency_present": facet_values("emergency_present", limit=facet_value_limit),
            "manufacturer": facet_values("manufacturer", limit=facet_value_limit, fallback_col="manufacturer"),
        },
        dimensions_options={
            "mounting_type": facet_values("mounting_type", limit=facet_value_limit),
            "shape": facet_values("shape", limit=facet_value_limit),
            "housing_material": facet_values("housing_material", limit=facet_value_limit),
            "housing_color": facet_values("housing_color", limit=facet_value_limit),
            "protection_class": facet_values("protection_class", limit=facet_value_limit),
            "ik_rating": facet_values("ik_rating", limit=facet_value_limit),
            "ip_rating": facet_values("ip_rating", limit=facet_value_limit),
            "ip_visible": facet_values("ip_visible", limit=facet_value_limit),
            "ip_non_visible": facet_values("ip_non_visible", limit=facet_value_limit),
            "ranges": {
                "diameter": facet_min_max("diameter"),
                "luminaire_height": facet_min_max("luminaire_height"),
                "luminaire_width": facet_min_max("luminaire_width"),
                "luminaire_length": facet_min_max("luminaire_length"),
                "ambient_temp_min_c": facet_min_max("ambient_temp_min_c"),
                "ambient_temp_max_c": facet_min_max("ambient_temp_max_c"),
            },
            "options": {
                "housing_color": facet_values("housing_color", limit=facet_value_limit),
                "beam_angle_deg": facet_values("beam_angle_deg", limit=facet_value_limit),
            },
        },
        price_consumption={"efficacy_lm_w": facet_min_max("efficacy_lm_w")},
    )
    if (not resp.families) and (narrowed is not None) and (not narrowed.empty):
        print("Facets: narrowed has rows but no families. Columns:", list(narrowed.columns))

    facets_cache_set(cache_key, resp.model_dump())
    return resp
