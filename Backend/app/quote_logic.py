from __future__ import annotations

from typing import Any, Callable, List, Optional

from fastapi import HTTPException


def handle_export_quote_pdf(
    req: Any,
    *,
    frontend_dir: str,
    html_module: Any,
    os_module: Any,
    streaming_response_cls: Any,
) -> Any:
    items = req.items or []
    if not items:
        raise HTTPException(status_code=400, detail="Quote cart is empty")

    company = str(req.company or "").strip()
    project = str(req.project or "").strip()
    project_status = str(getattr(req, "project_status", "") or "design_phase").strip().replace("_", " ")
    contractor_name = str(getattr(req, "contractor_name", "") or "").strip()
    consultant_name = str(getattr(req, "consultant_name", "") or "").strip()
    project_notes = str(getattr(req, "project_notes", "") or "").strip()
    if not company or not project or not contractor_name or not consultant_name:
        raise HTTPException(status_code=400, detail="Company, project, contractor, and consultant are required")

    try:
        from io import BytesIO
        from datetime import datetime
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="PDF export dependency missing. Install reportlab on backend.",
        )

    disano_items: List[Any] = []
    fosnova_items: List[Any] = []
    for item in items:
        manufacturer = str(item.manufacturer or "").strip().lower()
        if "fosnova" in manufacturer:
            fosnova_items.append(item)
        else:
            disano_items.append(item)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    story: List[Any] = []
    title_style = styles["Title"].clone("QuoteTitle")
    title_style.textColor = colors.HexColor("#0f172a")
    title_style.fontSize = 21
    title_style.leading = 24
    subtitle_style = styles["Heading3"].clone("QuoteSubtitle")
    subtitle_style.textColor = colors.HexColor("#475569")
    subtitle_style.fontSize = 11
    subtitle_style.leading = 14
    subtitle_style.alignment = TA_LEFT
    section_title_style = styles["Heading4"].clone("QuoteSectionTitle")
    section_title_style.textColor = colors.HexColor("#0f172a")
    section_title_style.fontSize = 11
    section_title_style.leading = 13
    section_title_style.spaceAfter = 3
    note_style = styles["BodyText"].clone("QuoteNote")
    note_style.fontName = "Helvetica"
    note_style.fontSize = 8.5
    note_style.leading = 11
    note_style.textColor = colors.HexColor("#334155")

    def find_logo_path(brand: str) -> Optional[str]:
        base = str(brand or "").strip().lower()
        if base == "laiting":
            candidates = ["laiting-logo-ai.png", "laiting-logo.png"]
        elif base == "fosnova":
            candidates = ["logo-fosnova.png", "logo-fosnova.jpg", "logo-fosnova.webp"]
        else:
            candidates = ["logo-disano.png", "logo-disano.jpg", "logo-disano.webp"]
        for name in candidates:
            path = os_module.path.join(frontend_dir, name)
            if os_module.path.exists(path):
                return path
        return None

    main_logo_path = find_logo_path("laiting")
    if main_logo_path:
        try:
            story.append(Image(main_logo_path, width=40 * mm, height=10 * mm))
        except Exception:
            pass

    story.append(Paragraph("Quote Proposal", title_style))
    story.append(Paragraph("Prepared from the Laiting workspace", subtitle_style))
    story.append(Spacer(1, 3 * mm))

    total_qty = sum(max(1, int(getattr(item, "qty", 1) or 1)) for item in items)
    summary_rows = [
        [
            Paragraph("<b>Company</b>", styles["Normal"]),
            Paragraph(html_module.escape(company), styles["Normal"]),
            Paragraph("<b>Project</b>", styles["Normal"]),
            Paragraph(html_module.escape(project), styles["Normal"]),
        ],
        [
            Paragraph("<b>Status</b>", styles["Normal"]),
            Paragraph(html_module.escape(project_status.title()), styles["Normal"]),
            Paragraph("<b>Exported at</b>", styles["Normal"]),
            Paragraph(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), styles["Normal"]),
        ],
        [
            Paragraph("<b>Contractor</b>", styles["Normal"]),
            Paragraph(html_module.escape(contractor_name), styles["Normal"]),
            Paragraph("<b>Consultant</b>", styles["Normal"]),
            Paragraph(html_module.escape(consultant_name), styles["Normal"]),
        ],
        [
            Paragraph("<b>Items</b>", styles["Normal"]),
            Paragraph(str(len(items)), styles["Normal"]),
            Paragraph("<b>Total quantity</b>", styles["Normal"]),
            Paragraph(str(total_qty), styles["Normal"]),
        ],
    ]
    summary_table = Table(summary_rows, colWidths=[26 * mm, 58 * mm, 26 * mm, 58 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 4 * mm))

    if project_notes:
        story.append(Paragraph("Project notes", section_title_style))
        story.append(Paragraph(html_module.escape(project_notes), note_style))
        story.append(Spacer(1, 4 * mm))

    def add_group_table(title: str, group_items: List[Any]) -> None:
        if not group_items:
            return
        group_logo_path = find_logo_path(title)
        if group_logo_path:
            try:
                head = Table(
                    [[Image(group_logo_path, width=26 * mm, height=6.5 * mm), Paragraph(f"<b>({len(group_items)})</b>", styles["Heading4"])]],
                    colWidths=[30 * mm, 140 * mm],
                )
                head.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (0, 0), "LEFT"),
                            ("ALIGN", (1, 0), (1, 0), "LEFT"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 0),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ]
                    )
                )
                story.append(head)
            except Exception:
                story.append(Paragraph(f"<b>{html_module.escape(title)} ({len(group_items)})</b>", styles["Heading4"]))
        else:
            story.append(Paragraph(f"<b>{html_module.escape(title)} ({len(group_items)})</b>", styles["Heading4"]))

        group_qty = sum(max(1, int(getattr(item, "qty", 1) or 1)) for item in group_items)
        story.append(
            Paragraph(
                f"Products: {len(group_items)} | Total quantity: {group_qty}",
                subtitle_style,
            )
        )
        story.append(Spacer(1, 1.5 * mm))

        headers = ["#", "Code", "Name", "Qty", "Notes", "Project Ref"]
        body_style = styles["BodyText"].clone("QuoteBodyCell")
        body_style.fontName = "Helvetica"
        body_style.fontSize = 8
        body_style.leading = 9.2
        body_style.wordWrap = "CJK"

        rows: List[List[Any]] = [headers]
        for idx, item in enumerate(group_items, start=1):
            rows.append(
                [
                    str(idx),
                    str(item.product_code or ""),
                    Paragraph(html_module.escape(str(item.product_name or "")), body_style),
                    str(max(1, int(item.qty or 1))),
                    Paragraph(html_module.escape(str(item.notes or "")), body_style),
                    Paragraph(html_module.escape(str(item.project_reference or "")), body_style),
                ]
            )

        table = Table(rows, colWidths=[8 * mm, 24 * mm, 44 * mm, 10 * mm, 53 * mm, 38 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (3, 0), (3, -1), "CENTER"),
                    ("ALIGN", (5, 0), (5, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 4 * mm))

    add_group_table("Disano", disano_items)
    add_group_table("Fosnova", fosnova_items)

    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "This document is intended as a project quote summary. Please verify any required accessories or configuration notes on the product datasheets before final submission.",
            note_style,
        )
    )

    doc.build(story)
    buf.seek(0)
    filename = f"quote_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
    return streaming_response_cls(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def handle_export_quote_datasheets_zip(
    req: Any,
    *,
    build_datasheet_url: Callable[[str, str], str],
    safe_open_url: Callable[..., Any],
    cfg_int: Callable[[str, int], int],
    public_fetch_hosts: Any,
    re_module: Any,
    zipfile_module: Any,
    streaming_response_cls: Any,
) -> Any:
    items = req.items or []
    if not items:
        raise HTTPException(status_code=400, detail="Quote cart is empty")

    from io import BytesIO
    from datetime import datetime

    buf = BytesIO()
    added = 0
    errors: List[str] = []
    seen_codes: set[str] = set()

    def safe_name(value: str) -> str:
        s = re_module.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
        return s.strip("._") or "item"

    with zipfile_module.ZipFile(buf, mode="w", compression=zipfile_module.ZIP_DEFLATED) as zf:
        for item in items:
            code = str(getattr(item, "product_code", "") or "").strip()
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            manufacturer = str(getattr(item, "manufacturer", "") or "").strip()
            datasheet_url = build_datasheet_url(code, manufacturer)
            if not datasheet_url:
                errors.append(f"{code}: datasheet URL unavailable")
                continue
            try:
                with safe_open_url(
                    datasheet_url,
                    timeout=cfg_int("main.http_timeout_datasheet_sec", 12),
                    allowed_hosts=public_fetch_hosts,
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/pdf,*/*;q=0.5"},
                ) as resp:
                    data = resp.read()
                    ctype = str(getattr(resp, "headers", {}).get("Content-Type", "") or "").lower()
                if not data:
                    errors.append(f"{code}: empty response")
                    continue
                if ("pdf" not in ctype) and not data.startswith(b"%PDF"):
                    errors.append(f"{code}: non-PDF response from datasheet URL")
                    continue
                zf.writestr(f"{safe_name(code)}.pdf", data)
                added += 1
            except Exception as exc:
                errors.append(f"{code}: {exc}")

        summary_lines = [
            "Datasheet ZIP export summary",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Requested items: {len(items)}",
            f"Unique product codes: {len(seen_codes)}",
            f"Datasheets added: {added}",
            f"Errors: {len(errors)}",
            "",
        ]
        if errors:
            summary_lines.append("Failed / skipped datasheets:")
            summary_lines.extend(f"- {x}" for x in errors[: cfg_int("main.zip_error_preview_limit", 500)])
        else:
            summary_lines.append("All requested datasheets downloaded successfully.")
        zf.writestr("_datasheet_export_summary.txt", "\n".join(summary_lines))

    if added <= 0:
        raise HTTPException(status_code=502, detail="No datasheets could be downloaded for selected items")

    buf.seek(0)
    filename = f"datasheets_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    return streaming_response_cls(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
