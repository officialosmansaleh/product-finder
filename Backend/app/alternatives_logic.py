from __future__ import annotations

from typing import Any, Callable, Dict, List

from fastapi import HTTPException


def handle_alternatives_from_spec(
    req: Any,
    *,
    sanitize_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    normalize_ui_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    cfg_int: Callable[[str, int], int],
    map_filters_to_sql: Callable[[Dict[str, Any]], Dict[str, Any]],
    product_db: Any,
    db_dataframe: Any,
    row_to_public_dict: Callable[[Dict[str, Any]], Dict[str, Any]],
    score_product: Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Any],
    manufacturer_label: Callable[[Any], str],
    build_website_url: Callable[[str, str], str],
    build_datasheet_url: Callable[[str, str], str],
    quote_plus: Callable[[str], str],
    to_num: Callable[[Any], Any],
) -> Dict[str, Any]:
    ideal_spec = normalize_ui_filters(sanitize_filters(req.ideal_spec or {}))
    limit_raw = getattr(req, "limit", None)
    limit = max(1, min(int(limit_raw), cfg_int("main.alternatives_max_limit", 5000))) if limit_raw is not None else None
    sort_mode = str(getattr(req, "sort", "score_desc") or "score_desc").strip()
    min_score_raw = getattr(req, "min_score", None)
    min_score = None if min_score_raw is None else max(0.0, min(float(min_score_raw), 1.0))
    if not ideal_spec:
        raise HTTPException(status_code=400, detail="ideal_spec is empty")

    finder_filters = dict(ideal_spec)
    seed_filters = {
        k: v
        for k, v in ideal_spec.items()
        if k in {"product_family", "shape", "manufacturer"} and v is not None and str(v).strip() != ""
    }
    sql_filters = map_filters_to_sql(seed_filters)

    candidates: List[Dict[str, Any]] = []
    if product_db and product_db.conn:
        try:
            candidates = product_db.search_products(sql_filters, limit=2000) if sql_filters else product_db.search_products({}, limit=2000)
            candidates = [row_to_public_dict(dict(x)) if not isinstance(x, dict) else row_to_public_dict(x) for x in candidates]
        except Exception:
            candidates = []
    if not candidates and db_dataframe is not None and not db_dataframe.empty:
        try:
            rows = db_dataframe.head(2000).to_dict(orient="records")
            candidates = [row_to_public_dict(x) for x in rows]
        except Exception:
            candidates = []

    scored: List[Dict[str, Any]] = []
    for candidate in candidates:
        exact_score, _hm, _hd, _hmiss = score_product(candidate, finder_filters, {})
        similar_score, _sm, _sd, _smm = score_product(candidate, {}, finder_filters)
        score = float(similar_score)
        if score <= 0.0:
            score = float(exact_score)
        if score <= 0.0:
            continue
        manufacturer = manufacturer_label(candidate.get("manufacturer"))
        product_code = str(candidate.get("product_code") or "").strip()
        if not product_code:
            continue
        website_url = build_website_url(product_code, manufacturer)
        scored.append(
            {
                "product_code": product_code,
                "product_name": candidate.get("product_name"),
                "manufacturer": manufacturer,
                "product_family": candidate.get("product_family"),
                "score": round(float(score), 4),
                "price": candidate.get("price"),
                "datasheet_url": build_datasheet_url(product_code, manufacturer),
                "image_preview_url": f"/preview-image?product_code={quote_plus(product_code)}&manufacturer={quote_plus(manufacturer)}&website_url={quote_plus(website_url)}",
            }
        )

    if sort_mode == "score_asc":
        scored.sort(key=lambda x: (float(x.get("score") or 0.0), str(x.get("product_code") or "")))
    elif sort_mode == "price_asc":
        scored.sort(
            key=lambda x: (
                float(to_num(x.get("price"))) if to_num(x.get("price")) is not None else float("inf"),
                str(x.get("product_code") or ""),
            )
        )
    elif sort_mode == "price_desc":
        scored.sort(
            key=lambda x: (
                -(float(to_num(x.get("price"))) if to_num(x.get("price")) is not None else float("-inf")),
                str(x.get("product_code") or ""),
            )
        )
    else:
        sort_mode = "score_desc"
        scored.sort(key=lambda x: (x["score"], str(x.get("product_code") or "")), reverse=True)

    if min_score is not None:
        scored = [x for x in scored if float(x.get("score") or 0.0) >= min_score]
    out_rows = scored[:limit] if limit is not None else scored
    return {
        "found": True,
        "ideal_spec": ideal_spec,
        "sort": sort_mode,
        "score_fields_count": len(ideal_spec),
        "total_matches": len(scored),
        "alternatives": out_rows,
    }


def handle_alternatives(
    req: Any,
    *,
    find_product_by_code_any: Callable[[str], Dict[str, Any] | None],
    cfg_int: Callable[[str, int], int],
    product_db: Any,
    db_dataframe: Any,
    row_to_public_dict: Callable[[Dict[str, Any]], Dict[str, Any]],
    alt_similarity: Callable[[Dict[str, Any], Dict[str, Any]], float],
    manufacturer_label: Callable[[Any], str],
    build_website_url: Callable[[str, str], str],
    build_datasheet_url: Callable[[str, str], str],
    quote_plus: Callable[[str], str],
) -> Dict[str, Any]:
    base = find_product_by_code_any(req.code)
    if not base:
        return {"found": False, "code": req.code, "alternatives": []}

    limit_raw = getattr(req, "limit", None)
    limit = max(1, min(int(limit_raw), cfg_int("main.alternatives_max_limit", 5000))) if limit_raw is not None else None
    min_score_raw = getattr(req, "min_score", None)
    min_score = None if min_score_raw is None else max(0.0, min(float(min_score_raw), 1.0))
    base_code = str(base.get("product_code") or "").strip()
    family = str(base.get("product_family") or "").strip()

    candidates: List[Dict[str, Any]] = []
    if product_db and product_db.conn:
        try:
            if family:
                query = (
                    "SELECT * FROM products WHERE LOWER(TRIM(product_family)) = LOWER(TRIM(?)) "
                    "AND LOWER(TRIM(product_code)) <> LOWER(TRIM(?)) LIMIT ?"
                )
                rows = product_db.conn.execute(query, (family, base_code, cfg_int("main.search_candidate_min", 500))).fetchall()
            else:
                query = "SELECT * FROM products WHERE LOWER(TRIM(product_code)) <> LOWER(TRIM(?)) LIMIT ?"
                rows = product_db.conn.execute(query, (base_code, cfg_int("main.search_candidate_min", 500))).fetchall()
            candidates = [row_to_public_dict(dict(r)) for r in rows]
        except Exception:
            candidates = []

    if not candidates and db_dataframe is not None and not db_dataframe.empty:
        tmp = db_dataframe.copy()
        if "product_code" in tmp.columns:
            tmp = tmp[tmp["product_code"].astype(str).str.lower() != base_code.lower()]
        if family and "product_family" in tmp.columns:
            tmp = tmp[tmp["product_family"].astype(str).str.lower() == family.lower()]
        candidates = [row_to_public_dict(x) for x in tmp.head(cfg_int("main.search_candidate_min", 500)).to_dict(orient="records")]

    scored: List[Dict[str, Any]] = []
    for candidate in candidates:
        score = alt_similarity(base, candidate)
        if score <= 0:
            continue
        manufacturer = manufacturer_label(candidate.get("manufacturer"))
        product_code = str(candidate.get("product_code") or "").strip()
        website_url = build_website_url(product_code, manufacturer)
        scored.append(
            {
                "product_code": product_code,
                "product_name": candidate.get("product_name"),
                "manufacturer": manufacturer,
                "product_family": candidate.get("product_family"),
                "score": round(float(score), 4),
                "price": candidate.get("price"),
                "datasheet_url": build_datasheet_url(product_code, manufacturer),
                "image_preview_url": f"/preview-image?product_code={quote_plus(product_code)}&manufacturer={quote_plus(manufacturer)}&website_url={quote_plus(website_url)}",
            }
        )

    scored.sort(key=lambda x: (x["score"], str(x.get("product_code") or "")), reverse=True)
    if min_score is not None:
        scored = [x for x in scored if float(x.get("score") or 0.0) >= min_score]
    top = scored[:limit] if limit is not None else scored
    base_public = row_to_public_dict(base)
    base_code_out = str(base_public.get("product_code") or base_code).strip()
    base_mfr = manufacturer_label(base_public.get("manufacturer"))
    base_public["manufacturer"] = base_mfr
    base_public["datasheet_url"] = build_datasheet_url(base_code_out, base_mfr)
    base_public["website_url"] = build_website_url(base_code_out, base_mfr)
    return {
        "found": True,
        "code": base_code,
        "base": base_public,
        "total_matches": len(scored),
        "alternatives": top,
    }
