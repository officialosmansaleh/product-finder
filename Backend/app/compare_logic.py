from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException


def handle_compare_products(
    req: Any,
    *,
    find_product_by_code_any: Callable[[str], Optional[Dict[str, Any]]],
    manufacturer_label: Callable[[Any], str],
    build_website_url: Callable[[str, str], str],
    build_datasheet_url: Callable[[str, str], str],
    collect_compare_fields: Callable[[List[Optional[Dict[str, Any]]], bool, bool], List[str]],
    cmp_norm_value: Callable[[Any], str],
    quote_plus: Callable[[str], str],
) -> Dict[str, Any]:
    raw_codes = [str(c or "").strip() for c in (req.codes or [])]
    codes = [c for c in raw_codes if c]
    if len(codes) < 2:
        raise HTTPException(status_code=400, detail="At least 2 codes are required")
    if len(codes) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 codes supported")

    rows: List[Optional[Dict[str, Any]]] = []
    found_meta: List[Dict[str, Any]] = []
    items: List[Optional[Dict[str, Any]]] = []

    for idx, requested in enumerate(codes):
        row = find_product_by_code_any(requested)
        rows.append(row)
        if not row:
            found_meta.append(
                {
                    "slot": idx,
                    "requested_code": requested,
                    "found": False,
                    "product_code": None,
                }
            )
            items.append(None)
            continue
        manufacturer = manufacturer_label(row.get("manufacturer"))
        code = str(row.get("product_code") or requested).strip()
        website_url = build_website_url(code, manufacturer)
        found_meta.append(
            {
                "slot": idx,
                "requested_code": requested,
                "found": True,
                "product_code": code,
            }
        )
        items.append(
            {
                "slot": idx,
                "requested_code": requested,
                "product_code": code,
                "product_name": row.get("product_name"),
                "manufacturer": manufacturer,
                "housing_color": row.get("housing_color"),
                "beam_angle_deg": row.get("beam_angle_deg"),
                "warranty_years": row.get("warranty_years"),
                "lifetime_hours": row.get("lifetime_hours"),
                "led_rated_life_h": row.get("led_rated_life_h"),
                "lumen_maintenance_pct": row.get("lumen_maintenance_pct"),
                "failure_rate_pct": row.get("failure_rate_pct"),
                "datasheet_url": build_datasheet_url(code, manufacturer),
                "image_preview_url": (
                    f"/preview-image?product_code={quote_plus(code)}"
                    f"&manufacturer={quote_plus(manufacturer)}"
                    f"&website_url={quote_plus(website_url)}"
                ),
            }
        )

    compare_fields = collect_compare_fields(rows, include_empty=False, reference_only=True)
    differences: List[Dict[str, Any]] = []
    valid_rows = [r for r in rows if r is not None]
    if len(valid_rows) >= 2:
        for field in compare_fields:
            vals = [(r.get(field) if r is not None else None) for r in rows]
            norm_vals = [cmp_norm_value(v) for v in vals]
            normalized = {x for x in norm_vals if x != ""}
            has_any_value = any(x != "" for x in norm_vals)
            if not has_any_value:
                continue
            has_missing = any(x == "" for x in norm_vals)
            if len(normalized) <= 1 and not has_missing:
                continue
            differences.append({"field": field, "values": vals})

    return {
        "codes": codes,
        "found": found_meta,
        "items": items,
        "differences": differences,
    }


def handle_compare_codes(
    req: Any,
    *,
    compare_products_fn: Callable[[Any], Dict[str, Any]],
    compare_products_request_factory: Callable[[List[str]], Any],
) -> Dict[str, Any]:
    payload = compare_products_fn(compare_products_request_factory([req.code_a, req.code_b]))
    items = payload.get("items") or []
    found = payload.get("found") or []
    item_a = items[0] if len(items) > 0 else None
    item_b = items[1] if len(items) > 1 else None
    found_a = bool(found[0].get("found")) if len(found) > 0 else False
    found_b = bool(found[1].get("found")) if len(found) > 1 else False
    if not found_a or not found_b or not item_a or not item_b:
        return {
            "found_a": found_a,
            "found_b": found_b,
            "code_a": req.code_a,
            "code_b": req.code_b,
            "differences": [],
        }

    legacy_diffs: List[Dict[str, Any]] = []
    for diff in (payload.get("differences") or []):
        vals = diff.get("values") or []
        legacy_diffs.append(
            {
                "field": diff.get("field"),
                "a": vals[0] if len(vals) > 0 else None,
                "b": vals[1] if len(vals) > 1 else None,
            }
        )
    return {
        "found_a": True,
        "found_b": True,
        "code_a": item_a.get("product_code") or req.code_a,
        "code_b": item_b.get("product_code") or req.code_b,
        "a_info": item_a,
        "b_info": item_b,
        "differences": legacy_diffs,
    }


def handle_compare_spec_products(
    req: Any,
    *,
    sanitize_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    normalize_ui_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    find_product_by_code_any: Callable[[str], Optional[Dict[str, Any]]],
    manufacturer_label: Callable[[Any], str],
    build_website_url: Callable[[str, str], str],
    build_datasheet_url: Callable[[str, str], str],
    collect_compare_fields: Callable[[List[Optional[Dict[str, Any]]], bool, bool], List[str]],
    cmp_norm_value: Callable[[Any], str],
    to_num: Callable[[Any], Optional[float]],
    quote_plus: Callable[[str], str],
    dimension_tolerance: float,
    dimension_keys: set[str],
) -> Dict[str, Any]:
    raw_spec = sanitize_filters(req.ideal_spec or {})
    spec = normalize_ui_filters(raw_spec)
    raw_codes = [str(c or "").strip() for c in (req.codes or [])]
    codes = [c for c in raw_codes if c][:2]
    if not codes:
        raise HTTPException(status_code=400, detail="At least 1 product code is required")

    ideal_item = {
        "slot": 0,
        "requested_code": "IDEAL_SPEC",
        "product_code": "Project requirement",
        "product_name": str(spec.get("product_name") or "Tender / Ideal Product"),
        "manufacturer": "Tender Spec",
        "datasheet_url": None,
        "image_preview_url": None,
        **dict(spec),
    }
    rows: List[Optional[Dict[str, Any]]] = [spec]
    items: List[Optional[Dict[str, Any]]] = [ideal_item]
    found_meta: List[Dict[str, Any]] = [
        {
            "slot": 0,
            "requested_code": "IDEAL_SPEC",
            "found": True,
            "product_code": "Project requirement",
        }
    ]

    for idx, requested in enumerate(codes, start=1):
        row = find_product_by_code_any(requested)
        rows.append(row)
        if not row:
            items.append(None)
            found_meta.append(
                {"slot": idx, "requested_code": requested, "found": False, "product_code": None}
            )
            continue
        manufacturer = manufacturer_label(row.get("manufacturer"))
        code = str(row.get("product_code") or requested).strip()
        website_url = build_website_url(code, manufacturer)
        found_meta.append(
            {"slot": idx, "requested_code": requested, "found": True, "product_code": code}
        )
        items.append(
            {
                "slot": idx,
                "requested_code": requested,
                "product_code": code,
                "product_name": row.get("product_name"),
                "manufacturer": manufacturer,
                "housing_color": row.get("housing_color"),
                "beam_angle_deg": row.get("beam_angle_deg"),
                "warranty_years": row.get("warranty_years"),
                "lifetime_hours": row.get("lifetime_hours"),
                "led_rated_life_h": row.get("led_rated_life_h"),
                "lumen_maintenance_pct": row.get("lumen_maintenance_pct"),
                "failure_rate_pct": row.get("failure_rate_pct"),
                "datasheet_url": build_datasheet_url(code, manufacturer),
                "image_preview_url": (
                    f"/preview-image?product_code={quote_plus(code)}"
                    f"&manufacturer={quote_plus(manufacturer)}"
                    f"&website_url={quote_plus(website_url)}"
                ),
            }
        )

    def parse_cmp_expr(value: Any) -> Optional[tuple[str, float]]:
        txt = str(value or "").strip().replace(",", ".")
        if not txt:
            return None
        import re

        match = re.match(r"^(>=|<=|>|<|=)\s*(-?\d+(?:\.\d+)?)$", txt)
        if match:
            return (match.group(1), float(match.group(2)))
        match = re.match(r"^(-?\d+(?:\.\d+)?)$", txt)
        if match:
            return ("=", float(match.group(1)))
        return None

    def cmp_ok(op: str, got: float, want: float, field: str = "") -> bool:
        tol = abs(want) * dimension_tolerance if field in dimension_keys else 0.0
        if field == "ambient_temp_min_c" and op in {">=", ">"}:
            return got <= (want + tol) if op == ">=" else got < (want + tol)
        if op == ">=":
            return got >= (want - tol)
        if op == "<=":
            return got <= (want + tol)
        if op == ">":
            return got > (want - tol)
        if op == "<":
            return got < (want + tol)
        return abs(got - want) <= max(tol, 1e-9)

    def parse_ipik_num(value: Any, prefix: str) -> Optional[int]:
        import re

        s = str(value or "").strip().upper().replace(" ", "")
        match = re.search(rf"(?:>=|<=|>|<|=)?{prefix}(\d{{1,2}})", s)
        if match:
            return int(match.group(1))
        match = re.search(r"(\d{1,2})", s)
        if match:
            return int(match.group(1))
        return None

    def ideal_satisfied(field: str, ideal_v: Any, actual_v: Any) -> bool:
        if actual_v is None or str(actual_v).strip() == "":
            return False
        ideal_s = str(ideal_v or "").strip()
        if not ideal_s:
            return True

        import re

        if field == "ip_rating":
            match = re.match(r"^(>=|<=|>|<|=)?\s*IP(\d{2})$", ideal_s.strip().upper().replace(" ", ""))
            if match:
                op = match.group(1) or ">="
                want = float(int(match.group(2)))
                got_n = parse_ipik_num(actual_v, "IP")
                return got_n is not None and cmp_ok(op, float(got_n), want, field)
        if field == "ik_rating":
            match = re.match(r"^(>=|<=|>|<|=)?\s*IK(\d{1,2})$", ideal_s.strip().upper().replace(" ", ""))
            if match:
                op = match.group(1) or ">="
                want = float(int(match.group(2)))
                got_n = parse_ipik_num(actual_v, "IK")
                return got_n is not None and cmp_ok(op, float(got_n), want, field)

        expr = parse_cmp_expr(ideal_s)
        got_num = to_num(actual_v)
        if expr and got_num is not None:
            op, want = expr
            return cmp_ok(op, float(got_num), float(want), field)

        actual_s = str(actual_v or "").strip().lower()
        ideal_cmp = ideal_s.strip().lower()
        if not ideal_cmp:
            return True
        if any(ideal_cmp.startswith(op) for op in (">=", "<=", ">", "<", "=")):
            return False
        return actual_s == ideal_cmp or (ideal_cmp in actual_s)

    compare_fields = collect_compare_fields(rows, include_empty=False, reference_only=True)
    differences: List[Dict[str, Any]] = []
    if sum(1 for r in rows[1:] if r is not None) >= 1:
        for field in compare_fields:
            vals = [(r.get(field) if r is not None else None) for r in rows]
            norm_vals = [cmp_norm_value(v) for v in vals]
            non_empty = [x for x in norm_vals if x != ""]
            if not non_empty:
                continue
            has_missing = any(x == "" for x in norm_vals)
            if len(set(non_empty)) <= 1 and not has_missing:
                continue
            ideal_v = vals[0]
            actual_vals = [v for v in vals[1:] if v is not None and str(v).strip() != ""]
            ideal_s = str(ideal_v or "").strip()
            if ideal_s and actual_vals and all(ideal_satisfied(field, ideal_v, actual_v) for actual_v in actual_vals):
                continue
            differences.append({"field": field, "values": vals})

    return {
        "found": found_meta,
        "items": items,
        "differences": differences,
        "ideal_spec": spec,
    }


def handle_export_compare_pdf(
    req: Any,
    *,
    compare_products_fn: Callable[[Any], Dict[str, Any]],
    compare_products_request_factory: Callable[[List[str]], Any],
    compare_spec_products_fn: Callable[[Any], Dict[str, Any]],
    compare_spec_products_request_factory: Callable[[Dict[str, Any], List[str]], Any],
    sanitize_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    normalize_ui_filters: Callable[[Dict[str, Any]], Dict[str, Any]],
    find_product_by_code_any: Callable[[str], Optional[Dict[str, Any]]],
    collect_compare_fields: Callable[[List[Optional[Dict[str, Any]]], bool, bool], List[str]],
    cmp_norm_value: Callable[[Any], str],
    humanize_compare_field: Callable[[str], str],
    extract_graphql_image_url: Callable[[str], Optional[str]],
    extract_first_site_image_url: Callable[[str, str], Optional[str]],
    build_website_url: Callable[[str, str], str],
    preview_image_fn: Callable[..., Any],
    safe_open_url: Callable[..., Any],
    cfg_int: Callable[[str, int], int],
    cfg_float: Callable[[str, float], float],
    public_fetch_hosts: Any,
    frontend_dir: str,
    html_module: Any,
    os_module: Any,
    re_module: Any,
    streaming_response_cls: Any,
) -> Any:
    codes_in = [str(c or "").strip() for c in (req.codes or []) if str(c or "").strip()]
    ideal_spec_raw = req.ideal_spec or {}
    use_ideal = bool(ideal_spec_raw)
    if use_ideal:
        product_codes = [c for c in codes_in if c.lower() not in {"project requirement", "ideal spec"}]
        if not product_codes:
            raise HTTPException(status_code=400, detail="At least 1 product code is required for Project requirement compare")
        compare_payload = compare_spec_products_fn(compare_spec_products_request_factory(ideal_spec_raw, product_codes))
    else:
        if len(codes_in) < 2:
            raise HTTPException(status_code=400, detail="At least 2 codes are required")
        compare_payload = compare_products_fn(compare_products_request_factory(codes_in[:3]))

    try:
        from io import BytesIO
        from datetime import datetime
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        try:
            from PIL import Image as PILImage  # type: ignore
        except Exception:
            PILImage = None  # type: ignore
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="PDF export dependency missing. Install reportlab on backend.",
        )

    field_labels = {
        "product_name": "Product name",
        "manufacturer": "Manufacturer",
        "product_family": "Family",
        "ip_rating": "IP",
        "ik_rating": "IK",
        "cct_k": "CCT",
        "cri": "CRI",
        "ugr": "UGR",
        "power_max_w": "Power W",
        "lumen_output": "Lumen",
        "efficacy_lm_w": "Efficacy",
        "beam_angle_deg": "Beam",
        "housing_color": "Color",
        "shape": "Shape",
        "control_protocol": "Control",
        "emergency_present": "Emergency",
        "warranty_years": "Warranty",
        "led_rated_life_h": "LED rated life",
        "lifetime_hours": "Lifetime h",
        "lumen_maintenance_pct": "Lumen maint. %",
        "failure_rate_pct": "Failure rate %",
        "diameter": "Diameter",
        "luminaire_length": "Length",
        "luminaire_width": "Width",
        "luminaire_height": "Height",
        "ambient_temp_min_c": "Min temp (C)",
        "ambient_temp_max_c": "Max temp (C)",
    }

    def fmt_val(value: Any) -> str:
        return "" if value is None else str(value).strip()

    found_meta = list(compare_payload.get("found") or [])
    items = list(compare_payload.get("items") or [])
    item_map = {int(i): (items[i] if i < len(items) else None) for i in range(len(found_meta))}

    def safe_filename_token(value: Any) -> str:
        s = str(value or "").strip()
        s = re_module.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-_.")
        return s or "item"

    rows: List[Optional[Dict[str, Any]]] = []
    if use_ideal:
        spec = normalize_ui_filters(sanitize_filters(ideal_spec_raw or {}))
        rows.append(spec)
        product_codes = [
            str(c or "").strip()
            for c in codes_in
            if str(c or "").strip() and str(c or "").strip().lower() not in {"project requirement", "ideal spec"}
        ][:2]
        for code in product_codes:
            rows.append(find_product_by_code_any(code))
        while len(rows) < len(found_meta):
            rows.append(None)
    else:
        for meta in found_meta:
            requested_code = str((meta or {}).get("requested_code") or "").strip()
            rows.append(find_product_by_code_any(requested_code) if requested_code else None)

    compare_fields = collect_compare_fields(rows, include_empty=True)
    diff_fields = {str(d.get("field") or "") for d in (compare_payload.get("differences") or [])}

    styles = getSampleStyleSheet()
    body_style = styles["BodyText"].clone("CmpPdfCell")
    body_style.fontName = "Helvetica"
    body_style.fontSize = 8
    body_style.leading = 9.2
    body_style.wordWrap = "CJK"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    def find_logo_path(brand: str = "disano") -> Optional[str]:
        base = str(brand or "").strip().lower()
        candidates = ["logo-fosnova.png", "logo-fosnova.jpg", "logo-fosnova.webp"] if base == "fosnova" else ["logo-disano.png", "logo-disano.jpg", "logo-disano.webp"]
        for name in candidates:
            path = os_module.path.join(frontend_dir, name)
            if os_module.path.exists(path):
                return path
        return None

    def fetch_product_image_bytes(code: str, manufacturer: str) -> Optional[bytes]:
        c = str(code or "").strip()
        if not c:
            return None
        mfg = str(manufacturer or "").strip()
        try:
            img_url = extract_graphql_image_url(c) or extract_first_site_image_url(build_website_url(c, manufacturer), product_code=c)
            if not img_url:
                resp = preview_image_fn(product_code=c, manufacturer=mfg, website_url=build_website_url(c, mfg))
                body = getattr(resp, "body", None)
                return body if body else None
            with safe_open_url(
                img_url,
                timeout=cfg_int("main.http_timeout_gql_sec", 6),
                allowed_hosts=public_fetch_hosts,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5",
                },
            ) as resp:
                data = resp.read()
                if data:
                    return data
        except Exception:
            pass
        try:
            resp = preview_image_fn(product_code=c, manufacturer=mfg, website_url=build_website_url(c, mfg))
            body = getattr(resp, "body", None)
            return body if body else None
        except Exception:
            return None

    def prepare_pdf_image_bytes(raw: Optional[bytes]) -> Optional[bytes]:
        if not raw:
            return None
        if PILImage is None:
            return raw
        try:
            with BytesIO(raw) as src_buf:
                with PILImage.open(src_buf) as image:
                    out = BytesIO()
                    if getattr(image, "mode", "") in ("RGBA", "LA") or (getattr(image, "mode", "") == "P" and "transparency" in (image.info or {})):
                        bg = PILImage.new("RGB", image.size, (255, 255, 255))
                        rgba = image.convert("RGBA")
                        bg.paste(rgba, mask=rgba.split()[-1])
                        bg.save(out, format="PNG")
                    else:
                        image.convert("RGB").save(out, format="PNG")
                    return out.getvalue()
        except Exception:
            return raw

    def slot_title(slot_idx: int) -> str:
        return ["Reference", "Option 1", "Option 2"][slot_idx] if slot_idx < 3 else f"Option {slot_idx + 1}"

    def compare_slot_card(meta: Dict[str, Any], item: Optional[Dict[str, Any]], slot_idx: int):
        code_label = slot_title(slot_idx)
        requested_code = str((meta or {}).get("requested_code") or "")
        if not item:
            return [Paragraph(f"<b>{code_label}</b>", styles["Heading5"]), Paragraph("<i>Not found</i>", styles["BodyText"])]
        product_code = str(item.get("product_code") or requested_code or "")
        manufacturer = str(item.get("manufacturer") or "")
        flows: List[Any] = [Paragraph(f"<b>{code_label}</b>", styles["Heading5"])]
        if product_code and product_code.lower() != "project requirement":
            img_bytes = prepare_pdf_image_bytes(fetch_product_image_bytes(product_code, manufacturer))
            if img_bytes:
                try:
                    image = Image(BytesIO(img_bytes), width=55 * mm, height=38 * mm, kind="proportional")
                    try:
                        image.hAlign = "CENTER"
                    except Exception:
                        pass
                    flows.append(Spacer(1, 1.5 * mm))
                    flows.append(image)
                except Exception:
                    flows.append(Spacer(1, 1.5 * mm))
                    flows.append(Paragraph("<i>Image render failed</i>", styles["BodyText"]))
        return flows

    story: List[Any] = []
    logo_path = find_logo_path("disano")
    if logo_path:
        try:
            header_tbl = Table(
                [[Image(logo_path, width=34 * mm, height=8.5 * mm), Paragraph("<b>Comparison Sheet</b>", styles["Title"])]],
                colWidths=[38 * mm, doc.width - 38 * mm],
            )
            header_tbl.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(header_tbl)
        except Exception:
            story.append(Paragraph("<b>Comparison Sheet</b>", styles["Title"]))
    else:
        story.append(Paragraph("<b>Comparison Sheet</b>", styles["Title"]))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            f"Exported at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Mode: {'Project requirement' if use_ideal else 'Product vs Product'}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 3 * mm))

    field_col = cfg_float("main.pdf.field_col_mm", 40.0) * mm
    try:
        slot_cells = []
        for idx, meta in enumerate(found_meta):
            card_flows = compare_slot_card(meta, item_map.get(idx), idx)
            data_cols = max(1, len(found_meta))
            data_col_w = max(cfg_float("main.pdf.min_data_col_mm", 25.0) * mm, (doc.width - field_col) / data_cols)
            card_tbl = Table([[x] for x in card_flows], colWidths=[data_col_w - 12])
            card_tbl.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            slot_cells.append(card_tbl)
        if slot_cells:
            data_cols = len(slot_cells)
            data_col_w = max(cfg_float("main.pdf.min_data_col_mm", 25.0) * mm, (doc.width - field_col) / data_cols)
            slot_tbl = Table([[""] + slot_cells], colWidths=[field_col] + [data_col_w] * data_cols)
            slot_tbl.setStyle(
                TableStyle(
                    [
                        ("GRID", (1, 0), (-1, -1), cfg_float("main.pdf.grid_width", 0.35), colors.HexColor("#e5e7eb")),
                        ("BACKGROUND", (1, 0), (-1, -1), colors.HexColor("#f8fafc")),
                        ("BACKGROUND", (0, 0), (0, 0), colors.white),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(slot_tbl)
            story.append(Spacer(1, 3 * mm))
    except Exception as exc:
        story.append(Paragraph(f"<i>Images strip render failed: {html_module.escape(str(exc))}</i>", styles["BodyText"]))
        story.append(Spacer(1, 2 * mm))

    header_cells: List[Any] = ["Field"]
    for idx, meta in enumerate(found_meta):
        item = item_map.get(idx)
        requested_code = str((meta or {}).get("requested_code") or "")
        found = bool((meta or {}).get("found"))
        if item and found:
            code = str(item.get("product_code") or requested_code or f"Code {idx + 1}")
            header_cells.append(f"{slot_title(idx)}: {code}")
        else:
            label = f"{slot_title(idx)}: {requested_code or '-'}"
            header_cells.append(f"{label} (missing)")

    table_rows: List[List[Any]] = [header_cells]
    row_is_diff: List[bool] = [False]
    for field in compare_fields:
        vals = []
        for row in rows[: len(found_meta)]:
            vals.append((row or {}).get(field) if isinstance(row, dict) else None)
        label = field_labels.get(field, humanize_compare_field(field))
        row_cells = [Paragraph(html_module.escape(label), body_style)]
        for value in vals:
            row_cells.append(Paragraph(html_module.escape(fmt_val(value)), body_style))
        table_rows.append(row_cells)
        row_is_diff.append(field in diff_fields)

    n_cols = len(header_cells)
    usable_w = doc.width
    rem = max(cfg_float("main.pdf.min_remaining_width_mm", 30.0) * mm, usable_w - field_col)
    other_w = rem / max(1, n_cols - 1)
    tbl = Table(table_rows, colWidths=[field_col] + [other_w] * (n_cols - 1), repeatRows=1)
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), cfg_float("main.pdf.grid_width", 0.35), colors.HexColor("#dbe2ea")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for idx in range(1, len(table_rows)):
        style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#fff7ed" if row_is_diff[idx] else "#ffffff")))
        if row_is_diff[idx]:
            style_cmds.append(("TEXTCOLOR", (0, idx), (0, idx), colors.HexColor("#9a3412")))
            style_cmds.append(("FONTNAME", (0, idx), (0, idx), "Helvetica-Bold"))
    tbl.setStyle(TableStyle(style_cmds))

    story.append(tbl)
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Highlighted rows indicate divergent fields.", styles["Italic"]))

    doc.build(story)
    buf.seek(0)
    name_parts: List[str] = []
    for idx, meta in enumerate(found_meta):
        item = item_map.get(idx)
        code = str((item or {}).get("product_code") or (meta or {}).get("requested_code") or "").strip()
        if not code:
            continue
        if code.lower() in {"project requirement", "ideal spec", "ideal_spec"}:
            code = "Project-requirement"
        name_parts.append(safe_filename_token(code))
    filename = "comparison_sheet.pdf"
    if name_parts:
        filename = f"{'_vs_'.join(name_parts)}.pdf"
    return streaming_response_cls(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
    )
