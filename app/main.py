# app/main.py (SIMPLIFIED FILTER FLOW)
# - Single filter dict (no hard/soft duplication)
# - Local parser only (deterministic)
# - Always map to numeric SQLite columns for numeric comparisons
# - SQLite-first search; DataFrame fallback only if SQLite unavailable

from fastapi import FastAPI, HTTPException, Query
from typing import Any, Dict, List, Optional
import os
import math
import pandas as pd
import re
import html
import json
import time
from collections import OrderedDict
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen
import threading

from app.schema import (
    SearchRequest, ProductHit, SearchResponse,
    FacetsResponse, FacetValue,
    ALLOWED_FILTER_KEYS, HARD_FILTER_KEYS,
)
from app.scoring import score_product

from app.pim_loader import load_products
from app.local_parser import local_text_to_filters
from app.llm_intent import llm_intent_to_filters
import logging
logger = logging.getLogger("uvicorn.error")

# Tender ranking: performance/design fields are soft preferences by default.
SOFT_PRIORITY_KEYS = {
    "power_min_w",
    "power_max_w",
    "lumen_output",
    "efficacy_lm_w",
    "beam_angle_deg",
    "cct_k",
    "diameter",
    "luminaire_height",
    "luminaire_width",
    "luminaire_length",
    "housing_color",
    "asymmetry",
    "beam_type",
}

print("✅ LLM function loaded:", llm_intent_to_filters)
print("OPENAI_API_KEY present?", bool(os.getenv("OPENAI_API_KEY")))

# Try to import database, but don't crash if it fails
try:
    from app.database import ProductDatabase
    HAS_DATABASE = True
except ImportError as e:
    print(f"⚠️  Database module import warning: {e}")
    print("⚠️  SQLite features will be disabled")
    HAS_DATABASE = False
    ProductDatabase = None

app = FastAPI(title="Product Finder MVP (Simplified)")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

@app.post("/debug/clear_facets_cache")
def clear_facets_cache():
    FACETS_CACHE.clear()
    return {"ok": True, "message": "facets cache cleared"}


@app.get("/")
def home():
    resp = FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

XLSX_PATH = os.getenv("PIM_XLSX", "data/ExportRO-2025-10-28_09.34.43.xlsx")
FAMILY_MAP_PATH = os.getenv("FAMILY_MAP_XLSX", "data/family_map.xlsx")
PIM_VERBOSE = os.getenv("PIM_VERBOSE", "1").strip() not in ("0", "false", "False", "no", "NO")
USE_SQLITE = os.getenv("USE_SQLITE", "1").strip() not in ("0", "false", "False", "no", "NO") and HAS_DATABASE

DB: Optional[pd.DataFrame] = None
PRODUCT_DB: Optional[Any] = None
ALLOWED_FAMILIES: List[str] = []
ALLOWED_FAMILIES_NORM: set[str] = set()
IMAGE_URL_CACHE: Dict[str, Optional[str]] = {}
IMAGE_URL_CACHE_LOCK = threading.Lock()
IMAGE_ENRICH_MAX = int(os.getenv("IMAGE_ENRICH_MAX", "60"))
HCL_GRAPHQL_ENDPOINT = os.getenv("HCL_GRAPHQL_ENDPOINT", "https://www.disano.it/apis/hcl/graphql/")
HCL_STORE_ID = os.getenv("HCL_STORE_ID", "10151")
HCL_LANG_ID = os.getenv("HCL_LANG_ID", "-1")


# ------------------------------------------------------------
# Facets cache (in-memory)
# Keyed by FILTERS (mapped to SQLite)
# ------------------------------------------------------------
FACETS_CACHE = OrderedDict()   # key -> (timestamp, payload_dict)
FACETS_CACHE_MAX = 128
FACETS_CACHE_TTL_SEC = 180  # 3 minutes
FACETS_CACHE_SCHEMA_VER = 2

def _facets_cache_key(filters: Dict[str, Any]) -> str:
    normalized = {"__v": FACETS_CACHE_SCHEMA_VER}
    for k, v in (filters or {}).items():
        if isinstance(v, list):
            normalized[k] = [str(x).strip() for x in v]
        else:
            normalized[k] = str(v).strip()
    return json.dumps(normalized, sort_keys=True, ensure_ascii=False)

def _facets_cache_get(key: str):
    now = time.time()
    if key not in FACETS_CACHE:
        return None
    ts, payload = FACETS_CACHE[key]
    if now - ts > FACETS_CACHE_TTL_SEC:
        try:
            del FACETS_CACHE[key]
        except Exception:
            pass
        return None
    FACETS_CACHE.move_to_end(key)
    return payload

def _facets_cache_set(key: str, payload: Dict[str, Any]):
    FACETS_CACHE[key] = (time.time(), payload)
    FACETS_CACHE.move_to_end(key)
    while len(FACETS_CACHE) > FACETS_CACHE_MAX:
        FACETS_CACHE.popitem(last=False)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _clean(x):
    if isinstance(x, float) and math.isnan(x):
        return None
    return x

def _families_from_sqlite_fallback(limit: int = 30):
    """
    Guaranteed fallback: return top families from SQLite even if narrowed DF is missing product_family.
    """
    if not PRODUCT_DB or not PRODUCT_DB.conn:
        try:
            if PRODUCT_DB:
                PRODUCT_DB.connect()
        except Exception:
            return []

    try:
        cur = PRODUCT_DB.conn.execute("""
            SELECT TRIM(product_family) AS fam, COUNT(*) AS cnt
            FROM products
            WHERE product_family IS NOT NULL AND TRIM(product_family) <> ''
            GROUP BY TRIM(product_family)
            ORDER BY cnt DESC
            LIMIT ?
        """, (int(limit),))
        out = []
        for row in cur.fetchall():
            fam = (row["fam"] or "").strip()
            if fam:
                out.append({"value": fam, "count": int(row["cnt"]), "raw": fam})
        return out
    except Exception as e:
        print("⚠️ families sqlite fallback failed:", e)
        return []



def _sanitize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (filters or {}).items():
        if k not in ALLOWED_FILTER_KEYS:
            continue
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        out[k] = v
    return out

def _expand_control_protocol(filters: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(filters or {})
    if "control_protocol" not in out:
        return out
    vals = out["control_protocol"] if isinstance(out["control_protocol"], list) else [out["control_protocol"]]
    norm = [str(v).strip().lower() for v in vals if str(v).strip()]
    if any("dali" in v for v in norm):
        merged: List[str] = []
        for v in vals:
            sv = str(v).strip()
            if sv and sv.lower() not in [x.lower() for x in merged]:
                merged.append(sv)
        if "yes" not in [x.lower() for x in merged]:
            merged.append("yes")
        out["control_protocol"] = merged if len(merged) > 1 else merged[0]
    return out
# ------------------------------------------------------------
# Normalize UI filters so "low" inputs accept only improving values
    # - IP / IK / CRI: higher is better => default to >=
    # - UGR: lower is better => default to <=
    # This makes UI filters behave like the text parser.
    # ------------------------------------------------------------
def _normalize_ui_filters(f: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizza i valori provenienti dalla UI in formato filtrabile.
    Regole "migliorative":
      - IP / IK: >=
      - CRI: >=
      - Warranty / Lifetime: >=
      - UGR: <=
    """
    import re
    out = dict(f or {})

    def has_op(s: str) -> bool:
        return any(s.startswith(op) for op in (">=", "<=", ">", "<", "="))

    def _as_list(v: Any) -> List[Any]:
        return v if isinstance(v, list) else [v]

    # IP (UI spesso manda "40.0") -> ">=IP40"
    if "ip_rating" in out:
        v = str(out["ip_rating"]).strip().upper().replace(" ", "").replace("IPX", "IP0")
        if not has_op(v):
            m = re.search(r"(\d{2})", v)
            if m:
                out["ip_rating"] = f">=IP{m.group(1)}"
        else:
            m = re.search(r"(>=|<=|>|<)\s*IP?(\d{2})", v)
            if m:
                out["ip_rating"] = f"{m.group(1)}IP{m.group(2)}"

    # IK ("IK5" / "IK05") -> ">=IK05"
    if "ik_rating" in out:
        v = str(out["ik_rating"]).strip().upper().replace(" ", "")
        if not has_op(v):
            m = re.search(r"(\d{1,2})", v)
            if m:
                out["ik_rating"] = f">=IK{m.group(1).zfill(2)}"
        else:
            m = re.search(r"(>=|<=|>|<)\s*IK?(\d{1,2})", v)
            if m:
                out["ik_rating"] = f"{m.group(1)}IK{m.group(2).zfill(2)}"

    # UGR migliorativo (più basso è meglio): "19" -> "<=19" ; "<19" -> "<=19"
    if "ugr" in out:
        v = str(out["ugr"]).strip().replace(" ", "")
        if not has_op(v):
            m = re.search(r"(\d+(?:\.\d+)?)", v.replace(",", "."))
            if m:
                out["ugr"] = f"<={m.group(1)}"
        else:
            if v.startswith("<") and not v.startswith("<="):
                out["ugr"] = "<=" + v[1:]

    # CRI migliorativo: "80" -> ">=80"
    if "cri" in out:
        v = str(out["cri"]).strip().replace(" ", "")
        if not has_op(v):
            m = re.search(r"(\d+(?:\.\d+)?)", v.replace(",", "."))
            if m:
                out["cri"] = f">={m.group(1)}"

    # Warranty anni: "5 yr" / "5" -> ">=5"
    if "warranty_years" in out:
        vals: List[str] = []
        for one in _as_list(out["warranty_years"]):
            v = str(one).strip().upper().replace(" ", "")
            if not has_op(v):
                m = re.search(r"(\d+)", v)
                if m:
                    vals.append(f">={m.group(1)}")
            else:
                m = re.search(r"(>=|<=|>|<|=)\s*(\d+)", v)
                if m:
                    vals.append(f"{m.group(1)}{m.group(2)}")
        if vals:
            out["warranty_years"] = vals[0] if len(vals) == 1 else vals

    # Lifetime ore: "50000 hr" / "50000" -> ">=50000"
    if "lifetime_hours" in out:
        vals: List[str] = []
        for one in _as_list(out["lifetime_hours"]):
            v = str(one).strip().upper().replace(" ", "")
            if not has_op(v):
                m = re.search(r"(\d+)", v)
                if m:
                    vals.append(f">={m.group(1)}")
            else:
                m = re.search(r"(>=|<=|>|<|=)\s*(\d+)", v)
                if m:
                    vals.append(f"{m.group(1)}{m.group(2)}")
        if vals:
            out["lifetime_hours"] = vals[0] if len(vals) == 1 else vals

    # LED rated life (h): default >=
    if "led_rated_life_h" in out:
        vals: List[str] = []
        for one in _as_list(out["led_rated_life_h"]):
            v = str(one).strip().upper().replace(" ", "")
            if not has_op(v):
                m = re.search(r"(\d+)", v)
                if m:
                    vals.append(f">={m.group(1)}")
            else:
                m = re.search(r"(>=|<=|>|<|=)\s*(\d+)", v)
                if m:
                    vals.append(f"{m.group(1)}{m.group(2)}")
        if vals:
            out["led_rated_life_h"] = vals[0] if len(vals) == 1 else vals

    # Lumen maintenance % (Ta 25°): default >=
    if "lumen_maintenance_pct" in out:
        vals: List[str] = []
        for one in _as_list(out["lumen_maintenance_pct"]):
            v = str(one).strip().upper().replace(" ", "")
            if not has_op(v):
                m = re.search(r"(\d+(?:\.\d+)?)", v.replace(",", "."))
                if m:
                    vals.append(f">={m.group(1)}")
            else:
                m = re.search(r"(>=|<=|>|<|=)\s*(\d+(?:\.\d+)?)", v.replace(",", "."))
                if m:
                    vals.append(f"{m.group(1)}{m.group(2)}")
        if vals:
            out["lumen_maintenance_pct"] = vals[0] if len(vals) == 1 else vals


    return out



def _normalize_facet_text(v: Any) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    s = html.unescape(s)
    s = s.replace("<lt/>", "<").replace("&lt;", "<").replace("&gt;", ">")
    s = " ".join(s.split())
    return s

def _truncate(s: str, n: int = 80) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"

def _extract_int(s: str) -> Optional[int]:
    m = re.search(r"(\d+)", s or "")
    return int(m.group(1)) if m else None

def _top_values(df: pd.DataFrame, col: str, limit: int = 30) -> List[FacetValue]:
    if df is None or df.empty or col not in df.columns:
        return []
    s = df[col].dropna().apply(_normalize_facet_text)
    s = s[s != ""]
    if s.empty:
        return []
    counts = s.value_counts()

    if col in ("ip_rating", "ik_rating", "cct_k"):
        items = [(k, int(v)) for k, v in counts.items()]
        items.sort(key=lambda kv: (_extract_int(str(kv[0])) is None, _extract_int(str(kv[0])) or 10**9))
        items = items[:limit]
    else:
        items = [(k, int(v)) for k, v in counts.head(limit).items()]

    return [{"value": _truncate(str(k), 80), "count": int(v), "raw": str(k)} for k, v in items]

def _top_name_prefixes(df: pd.DataFrame, limit: int = 30) -> List[FacetValue]:
    if df is None or df.empty or "product_name" not in df.columns:
        return []
    s = (
        df["product_name"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.split()
        .str[0]
        .fillna("")
        .str.lower()
    )
    s = s[s != ""]
    if s.empty:
        return []
    counts = s.value_counts().head(limit)
    return [{"value": str(k), "count": int(v), "raw": str(k)} for k, v in counts.items()]

def _name_prefixes_from_sqlite_fallback(limit: int = 30) -> List[FacetValue]:
    if not PRODUCT_DB or not PRODUCT_DB.conn:
        try:
            if PRODUCT_DB:
                PRODUCT_DB.connect()
        except Exception:
            return []
    try:
        cur = PRODUCT_DB.conn.execute(
            """
            SELECT LOWER(SUBSTR(TRIM(product_name), 1, INSTR(TRIM(product_name) || ' ', ' ') - 1)) AS pref,
                   COUNT(*) AS cnt
            FROM products
            WHERE product_name IS NOT NULL AND TRIM(product_name) <> ''
            GROUP BY pref
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        out = []
        for row in cur.fetchall():
            pref = str(row["pref"] or "").strip()
            if pref:
                out.append({"value": pref, "count": int(row["cnt"]), "raw": pref})
        return out
    except Exception:
        return []

def _top_values_from_sqlite_fallback(col: str, limit: int = 30) -> List[FacetValue]:
    if not PRODUCT_DB or not PRODUCT_DB.conn:
        try:
            if PRODUCT_DB:
                PRODUCT_DB.connect()
        except Exception:
            return []
    try:
        cur = PRODUCT_DB.conn.execute(
            f'''
            SELECT TRIM("{col}") AS v, COUNT(*) AS cnt
            FROM products
            WHERE "{col}" IS NOT NULL AND TRIM("{col}") <> ''
            GROUP BY TRIM("{col}")
            ORDER BY cnt DESC, v ASC
            LIMIT ?
            ''',
            (int(limit),),
        )
        out = []
        for row in cur.fetchall():
            v = str(row["v"] or "").strip()
            if v:
                out.append({"value": v, "count": int(row["cnt"]), "raw": v})
        return out
    except Exception:
        return []

def _website_search_url(order_code: str) -> str:
    return f"https://www.disano.it/en/search/?q={quote(str(order_code or '').strip())}"

def _extract_image_url_from_html(html_text: str) -> Optional[str]:
    if not html_text:
        return None
    # Try to capture next/image wrapper src and decode its `url=` payload.
    m = re.search(r'/_next/image/\?url=([^"&]+)&w=\d+&q=\d+', html_text, flags=re.IGNORECASE)
    if m:
        raw = m.group(1)
        try:
            return unquote(raw)
        except Exception:
            return raw
    # Fallback: first direct blob image if present
    m2 = re.search(r'https://azprodmedia\.blob\.core\.windows\.net/mediafiles/[^"\']+\.(?:jpg|jpeg|png|webp)', html_text, flags=re.IGNORECASE)
    if m2:
        return m2.group(0)
    return None

def _resolve_product_image_url(order_code: str) -> Optional[str]:
    code = str(order_code or "").strip()
    if not code:
        return None
    key = code.upper()
    with IMAGE_URL_CACHE_LOCK:
        if key in IMAGE_URL_CACHE:
            return IMAGE_URL_CACHE[key]
    found: Optional[str] = None
    try:
        # Preferred source: HCL GraphQL by part number (stable, no HTML scraping).
        gql = """
        query GET_PRODUCT_BY_PARTNUMBER($storeId: String!, $langId: String!, $partNumber: String!) {
          productViewFindProductByPartNumber(storeId: $storeId, langId: $langId, partNumber: $partNumber) {
            catalogEntryView {
              partNumber
              thumbnail
              fullImage
            }
          }
        }
        """
        payload = json.dumps({
            "query": gql,
            "variables": {
                "storeId": str(HCL_STORE_ID),
                "langId": str(HCL_LANG_ID),
                "partNumber": code,
            },
        }).encode("utf-8")
        req = Request(
            HCL_GRAPHQL_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 ProductFinder/1.0"},
        )
        with urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        cv = (((data or {}).get("data") or {}).get("productViewFindProductByPartNumber") or {}).get("catalogEntryView") or []
        if cv:
            first = cv[0] or {}
            found = first.get("thumbnail") or first.get("fullImage")

        # Fallback: lightweight HTML parsing (kept for resiliency).
        if not found:
            url = _website_search_url(code)
            req2 = Request(url, headers={"User-Agent": "Mozilla/5.0 ProductFinder/1.0"})
            with urlopen(req2, timeout=4.0) as resp2:
                body = resp2.read(350000).decode("utf-8", errors="ignore")
                found = _extract_image_url_from_html(body)
    except Exception:
        found = None
    with IMAGE_URL_CACHE_LOCK:
        IMAGE_URL_CACHE[key] = found
    return found

def _name_prefixes_from_rows(rows: List[Dict[str, Any]], limit: int = 30) -> List[FacetValue]:
    if not rows:
        return []
    pref = []
    for r in rows:
        name = str(r.get("product_name") or "").strip().lower()
        if not name:
            continue
        first = name.split()[0]
        if first:
            pref.append(first)
    if not pref:
        return []
    counts = pd.Series(pref, dtype="string").value_counts().head(int(limit))
    return [{"value": str(k), "count": int(v), "raw": str(k)} for k, v in counts.items()]

def _db_text_relevance(row: Dict[str, Any], text: str) -> float:
    q = str(text or "").strip().lower()
    if not q:
        return 0.0

    def _norm_code_like(s: str) -> str:
        # Normalize code-like strings: ignore spaces, dashes, slashes, punctuation.
        return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())

    q_compact = _norm_code_like(q)
    code = str(row.get("product_code") or "").strip().lower()
    short_code = str(row.get("short_product_code") or "").strip().lower()
    code_compact = _norm_code_like(code)
    short_code_compact = _norm_code_like(short_code)
    name = str(row.get("product_name") or "").strip().lower()
    manufacturer = str(row.get("manufacturer") or "").strip().lower()
    score = 0.0

    # Strong exact matches
    if code and (code == q or code_compact == q_compact):
        score += 220.0
    if short_code and (short_code == q or short_code_compact == q_compact):
        score += 180.0
    if name and name == q:
        score += 140.0
    if manufacturer and manufacturer == q:
        score += 130.0

    # Partial matches
    if code and q in code:
        score += 120.0
    if code_compact and q_compact and q_compact in code_compact:
        score += 120.0
    if short_code and q in short_code:
        score += 100.0
    if short_code_compact and q_compact and q_compact in short_code_compact:
        score += 100.0
    if name and q in name:
        score += 90.0
    if manufacturer and q in manufacturer:
        score += 70.0

    # Token overlap for multi-word product names
    tokens = [t for t in re.split(r"\s+", q) if t]
    if tokens and name:
        token_hits = sum(1 for t in tokens if t in name)
        score += token_hits * 12.0

    return score

def _min_max_numeric(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    if df is None or df.empty or col not in df.columns:
        return {"min": None, "max": None}
    nums = pd.to_numeric(df[col].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce").dropna()
    if nums.empty:
        return {"min": None, "max": None}
    return {"min": float(nums.min()), "max": float(nums.max())}

def _num_from_text_series(s: pd.Series) -> pd.Series:
    extracted = s.astype(str).str.extract(r"(-?\d+(?:\.\d+)?)")[0]
    return pd.to_numeric(extracted, errors="coerce")

def _df_filtered_subset(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    if df is None or df.empty or not filters:
        return df.copy() if df is not None else pd.DataFrame()

    out = df.copy()

    def _apply_numeric(col: str, expr: Any):
        nonlocal out
        if col not in out.columns:
            return
        default_op = "<=" if col == "ugr" else ">="
        values = expr if isinstance(expr, list) else [expr]
        got = out[col].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0]
        got_num = pd.to_numeric(got, errors="coerce")
        masks = []
        for one in values:
            s = str(one).strip().replace(" ", "")
            m = re.match(r"^(>=|<=|>|<)(\d+(?:\.\d+)?)$", s)
            if m:
                op, num = m.group(1), float(m.group(2))
                if op == ">=": masks.append(got_num >= num)
                elif op == ">": masks.append(got_num > num)
                elif op == "<=": masks.append(got_num <= num)
                elif op == "<": masks.append(got_num < num)
            else:
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", s).group())
                    if default_op == "<=":
                        masks.append(got_num <= num)
                    else:
                        masks.append(got_num >= num)
                except Exception:
                    continue
        if masks:
            m0 = masks[0]
            for mm in masks[1:]:
                m0 = m0 | mm
            out = out[m0]

    def _apply_contains(col: str, val: Any):
        nonlocal out
        if col not in out.columns:
            return
        values = val if isinstance(val, list) else [val]
        masks = []
        for one in values:
            masks.append(out[col].astype(str).str.lower().str.contains(str(one).lower(), na=False))
        if masks:
            m0 = masks[0]
            for mm in masks[1:]:
                m0 = m0 | mm
            out = out[m0]

    def _apply_name_prefix(val: Any):
        nonlocal out
        if "product_name" not in out.columns:
            return
        values = val if isinstance(val, list) else [val]
        name_prefix = (
            out["product_name"]
            .astype(str)
            .str.strip()
            .str.split()
            .str[0]
            .fillna("")
            .str.lower()
        )
        masks = []
        for one in values:
            masks.append(name_prefix == str(one).strip().lower())
        if masks:
            m0 = masks[0]
            for mm in masks[1:]:
                m0 = m0 | mm
            out = out[m0]

                # --- Special handling for IP / IK comparisons (>=, <=, etc.) ---
    def _apply_ip_ik(col: str, expr: Any, prefix: str):
        nonlocal out
        if col not in out.columns:
            return

        # Extract numeric part from the column values (e.g. "IK07" -> 7, "65.0" -> 65)
        got = out[col].astype(str).str.upper().str.replace(" ", "")
        if prefix == "IP":
            got = got.str.replace("IPX", "IP0", regex=False)
        got_num = pd.to_numeric(got.str.extract(r"(\d{1,2})")[0], errors="coerce")

        s = str(expr).strip().upper().replace(" ", "")
        if prefix == "IP":
            s = s.replace("IPX", "IP0")

        # Determine operator (default is >= for IP/IK)
        op_match = re.match(r"^(>=|<=|>|<)", s)
        op = op_match.group(1) if op_match else ">="

        # Extract wanted number (e.g. ">=IK04" -> 4)
        m = re.search(r"(\d{1,2})", s)
        if not m:
            return
        want = float(m.group(1))

        if op == ">=":
            out = out[got_num >= want]
        elif op == ">":
            out = out[got_num > want]
        elif op == "<=":
            out = out[got_num <= want]
        elif op == "<":
            out = out[got_num < want]
        else:
            out = out[got_num == want]

    if "ip_rating" in filters:
        _apply_ip_ik("ip_rating", filters["ip_rating"], "IP")

    if "ik_rating" in filters:
        _apply_ip_ik("ik_rating", filters["ik_rating"], "IK")


    for col in [
        "ip_rating", "ik_rating", "power_max_w", "power_min_w", "lumen_output",
        "efficacy_lm_w", "cri", "ugr", "beam_angle_deg", "diameter",
        "luminaire_height", "luminaire_width", "luminaire_length",
        "luminaire_size_min", "luminaire_size_max",
        "warranty_years", "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct",
    ]:
        if col in filters:
            if col == "ugr":
                v = str(filters[col]).strip()
                if v.startswith("<") and not v.startswith("<="):
                    filters[col] = "<=" + v[1:]
            _apply_numeric(col, filters[col])

    for col in ["control_protocol", "emergency_present", "mounting_type", "shape", "housing_material", "housing_color", "product_family", "manufacturer"]:
        if col in filters:
            _apply_contains(col, filters[col])
    if "name_prefix" in filters:
        _apply_name_prefix(filters["name_prefix"])

    if "cct_k" in filters and "cct_k" in out.columns:
        wants = filters["cct_k"] if isinstance(filters["cct_k"], list) else [filters["cct_k"]]
        nums = []
        for w in wants:
            m = re.search(r"(\d+)", str(w))
            if m:
                nums.append(float(m.group(1)))
        if nums:
            got = out["cct_k"].astype(str).str.extract(r"(\d+)")[0]
            got_num = pd.to_numeric(got, errors="coerce")
            out = out[got_num.isin(nums)]

    return out

# ------------------------------------------------------------
# SQLite numeric mapping
# ------------------------------------------------------------

MAP_NUM = {
    #"ugr": "ugr_value",
    #"efficacy_lm_w": "efficacy_value",
    #"lumen_output": "lumen_output_value",
    #"power_max_w": "power_max_value",
    #"power_min_w": "power_min_value",
    #"lifetime_hours": "lifetime_h_value",
    #"led_rated_life_h": "led_rated_life_value",
    #"warranty_years": "warranty_y_value",
}

def map_filters_to_sql(filters: Dict[str, Any]) -> Dict[str, Any]:
    import re

    sql = dict(filters or {})

    # Keep canonical keys used by DB columns.
    # Normalize values only; don't remap to *_value columns unless those columns exist.

    # ---- IK (improving: higher is better) ----
    def _op_and_number(expr: str):
        s = str(expr).strip().upper().replace(" ", "")
        m = re.search(r"(>=|<=|>|<)?IK?(\d{1,2})", s)
        if not m:
            return None
        op = m.group(1) or ">="
        num = int(m.group(2))
        return op, num

    if "ik_rating" in sql:
        parsed = _op_and_number(sql["ik_rating"])
        if parsed:
            op, num = parsed
            sql["ik_rating"] = f"{op}IK{str(num).zfill(2)}"

    # ---- UGR (improving: lower is better) ----
    if "ugr" in sql:
        v = str(sql["ugr"]).strip()
        if v.startswith("<") and not v.startswith("<="):
            v = "<=" + v[1:]
        sql["ugr"] = v

    return sql

# ------------------------------------------------------------
# Lifecycle
# ------------------------------------------------------------

@app.on_event("startup")
def startup():
    global DB, PRODUCT_DB, ALLOWED_FAMILIES, ALLOWED_FAMILIES_NORM
    print("🚀 Starting Product Finder (Simplified)...")

    try:
        DB = load_products(XLSX_PATH, verbose=PIM_VERBOSE)
        print(f"📊 Loaded {len(DB)} products to DataFrame")
                # Verifica la presenza di product_family
        if 'product_family' in DB.columns:
            families = DB['product_family'].dropna().unique()
            print(f"🏷️ Found {len(families)} unique families in DataFrame")
            print(f"   Sample families: {list(families)[:10]}")
        else:
            print("⚠️ 'product_family' not found in DataFrame!")
    except Exception as e:
        print(f"❌ Failed to load DataFrame: {e}")
        DB = pd.DataFrame()

    if USE_SQLITE and HAS_DATABASE:
        try:
            PRODUCT_DB = ProductDatabase()
            xlsx_exists = os.path.exists(XLSX_PATH)
            if not xlsx_exists:
                print(f"⚠️ XLSX not found at '{XLSX_PATH}'. SQLite refresh/recreate will be skipped.")
                        # Verifica se il database esiste e ha la colonna product_family
            if os.path.exists(PRODUCT_DB.db_path):
                PRODUCT_DB.connect()
                cursor = PRODUCT_DB.conn.execute("PRAGMA table_info(products)")
                columns = [row[1] for row in cursor.fetchall()]
                print(f"📋 Existing DB columns: {columns}")
                
                if 'product_family' not in columns:
                    if xlsx_exists:
                        print("⚠️ 'product_family' missing in DB. Recreating database...")
                        PRODUCT_DB.close()
                        count = PRODUCT_DB.recreate_database(XLSX_PATH, FAMILY_MAP_PATH)
                    else:
                        print("⚠️ Cannot recreate DB because XLSX source is missing.")
                        count = 0
                else:
                     if xlsx_exists:
                         count = PRODUCT_DB.init_db(XLSX_PATH, FAMILY_MAP_PATH)
                     else:
                         print("ℹ️ Keeping existing SQLite DB as-is (no XLSX source).")
                         count = PRODUCT_DB.get_stats().get("total_products", 0)

            else:
                if xlsx_exists:
                    count = PRODUCT_DB.init_db(XLSX_PATH, FAMILY_MAP_PATH)
                else:
                    print("⚠️ SQLite DB file missing and XLSX source missing: cannot initialize DB.")
                    count = 0
            if PRODUCT_DB:
                try:
                    sample = PRODUCT_DB.debug_sample(1)
                    print("DB SAMPLE KEYS:", list(sample[0].keys()) if sample else "no rows")
                    print("DB SAMPLE ROW:", sample[0] if sample else "no rows")
                except Exception as e:
                    print("DB SAMPLE ERROR:", e)

            print(f"💾 SQLite database ready: {count} products loaded")
        except Exception as e:
            print(f"⚠️  SQLite initialization failed: {e}")
            PRODUCT_DB = None
    else:
        print("ℹ️  SQLite is disabled or not available")

    print("✅ Startup complete")
    if PRODUCT_DB:
            try:
                ALLOWED_FAMILIES = PRODUCT_DB.get_distinct_families()
                ALLOWED_FAMILIES_NORM = {str(f).strip().lower() for f in ALLOWED_FAMILIES if str(f).strip()}
                print(f"🏷️ Loaded {len(ALLOWED_FAMILIES)} distinct families from DB")
                if len(ALLOWED_FAMILIES) == 0:
                    print("⚠️ WARNING: No families found in database!")
                    # Debug: stampa qualche riga dal database
                    sample = PRODUCT_DB.debug_sample(5)
                    for i, row in enumerate(sample):
                        print(f"  Sample {i+1}: family='{row.get('product_family', 'MISSING')}'")
            except Exception as e:
                print(f"⚠️ Failed to load families: {e}")
                ALLOWED_FAMILIES = []
                ALLOWED_FAMILIES_NORM = set()
    else:
        ALLOWED_FAMILIES = []
        ALLOWED_FAMILIES_NORM = set()

# In main.py, aggiungi:

@app.post("/database/recreate")
def recreate_database():
    """Forza la ricreazione del database"""
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="SQLite database not available")
    try:
        count = PRODUCT_DB.recreate_database(XLSX_PATH, FAMILY_MAP_PATH)
        return {
            "success": True, 
            "message": f"Database recreated with {count} products", 
            "count": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recreation failed: {str(e)}")

@app.on_event("shutdown")
def shutdown():
    if PRODUCT_DB:
        try:
            PRODUCT_DB.close()
            print("✅ Database connection closed")
        except Exception:
            pass
@app.get("/debug/families")
def debug_families():
        """Endpoint per debug delle famiglie"""
        result = {
            "allowed_families": ALLOWED_FAMILIES,
            "allowed_families_count": len(ALLOWED_FAMILIES),
            "database_available": PRODUCT_DB is not None,
        }
        
        if PRODUCT_DB:
            try:
                # Query diretta per vedere le famiglie nel DB
                cur = PRODUCT_DB.conn.execute("""
                    SELECT DISTINCT product_family, COUNT(*) as count
                    FROM products
                    WHERE product_family IS NOT NULL 
                    AND TRIM(product_family) <> ''
                    GROUP BY product_family
                    ORDER BY product_family
                    LIMIT 50
                """)
                families = [{"family": r[0], "count": r[1]} for r in cur.fetchall()]
                result["families_in_db"] = families
                result["total_products"] = PRODUCT_DB.get_stats()["total_products"]
            except Exception as e:
                result["error"] = str(e)
        
        return result

# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "xlsx_path": XLSX_PATH,
        "dataframe_loaded": DB is not None and not DB.empty,
        "dataframe_rows": int(len(DB)) if DB is not None else 0,
        "sqlite_available": HAS_DATABASE,
        "sqlite_enabled": USE_SQLITE,
        "sqlite_active": PRODUCT_DB is not None,
    }

@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    print("=== /search START ===")
    print("req.filters RAW:", req.filters)

    # 1) Parse from text (local + LLM)
    parsed = local_text_to_filters(req.text or "") or {}
    parsed = _sanitize_filters(parsed)

    logger.info(f"SEARCH CALLED ✅ text={req.text!r}")

    llm_extra: Dict[str, Any] = {}
    try:
        if (req.text or "").strip():
            logger.info("Calling LLM...")
            llm_extra = llm_intent_to_filters(req.text or "", allowed_families=ALLOWED_FAMILIES) or {}
            logger.info(f"LLM EXTRA ✅ {llm_extra}")
    except Exception:
        logger.exception("LLM ERROR ❌")
        llm_extra = {}

    # TEMP FIX: don't hard-filter on UGR unless user explicitly wrote a number
    if "ugr" in llm_extra and not any(ch.isdigit() for ch in (req.text or "")):
        llm_extra.pop("ugr", None)
        llm_extra.pop("ugr_value", None)
        llm_extra.pop("ugr_op", None)

    # merge safe: don't overwrite local parsed keys
    for k, v in llm_extra.items():
        if k not in parsed and v is not None:
            parsed[k] = v

    # 2) UI filters

    user_filters = _sanitize_filters(req.filters or {})
    user_filters = _normalize_ui_filters(user_filters)

    filters = {**parsed, **user_filters}
    filters = _expand_control_protocol(filters)
    # Keep UI filters as hard constraints (discriminative), keep parsed/text as soft.
    hard_filters = _expand_control_protocol(dict(user_filters))
    # Dimensions inferred from query should be discriminative (e.g. "60x60")
    for k in ("luminaire_size_min", "luminaire_size_max", "luminaire_length", "luminaire_width", "luminaire_height", "diameter"):
        if k in parsed and k not in hard_filters:
            hard_filters[k] = parsed[k]
    soft_filters = dict(filters)
    sql_filters = map_filters_to_sql(filters)
    hard_sql_filters = map_filters_to_sql(hard_filters)



    print("✅ filters:", filters)
    print("✅ sql_filters:", sql_filters)

    # 3) Candidate search (broad), then weighted ranking with UI hard constraints
    limit = max(1, int(req.limit or 20))
    candidate_limit = min(max(limit * 30, 500), 10000)
    rows: List[Dict[str, Any]] = []
    used_sqlite = False

    if PRODUCT_DB:
        used_sqlite = True
        try:
            rows = PRODUCT_DB.search_products({}, limit=candidate_limit)
        except Exception as e:
            print(f"⚠️ SQLite search failed: {e}")
            used_sqlite = False
            rows = []

    if not rows and (DB is not None and not DB.empty):
        narrowed = DB.copy()
        rows = narrowed.head(candidate_limit).fillna("").to_dict(orient="records")

    # 4) Score candidates
    scored: List[Dict[str, Any]] = []
    text_query = str(req.text or "").strip()
    has_text_query = bool(text_query)
    has_structured_filters = bool(filters)
    for r in rows:
        score, matched, deviations, missing = score_product(r, hard_filters, soft_filters)
        if score <= 0:
            continue
        text_rel = _db_text_relevance(r, text_query)
        # Query-only searches should be database-aware on code/name/manufacturer.
        if has_text_query and not has_structured_filters and text_rel <= 0:
            continue
        scored.append({
            "row": r,
            "score": float(score),
            "text_rel": float(text_rel),
            "matched": matched,
            "deviations": deviations,
            "missing": missing,
        })

    scored.sort(
        key=lambda x: (
            x.get("text_rel", 0.0),
            x["score"],
            str(x["row"].get("product_code", "")),
        ),
        reverse=True,
    )

    exact_scored: List[Dict[str, Any]] = []
    similar_scored: List[Dict[str, Any]] = []
    for s in scored:
        if s["score"] >= 0.999 and not s["deviations"] and not s["missing"]:
            exact_scored.append(s)
        else:
            similar_scored.append(s)

    exact_scored = exact_scored[:limit]
    if getattr(req, "include_similar", True):
        similar_scored = similar_scored[:limit]
    else:
        similar_scored = []

    # 4b) Safety fallback: never return 0 results when catalog has candidates.
    # If strict matching yields nothing, relax hard constraints and return best similars.
    fallback_used = False
    if not exact_scored and not similar_scored and rows:
        relaxed_soft = dict(filters or {})
        fallback_scored: List[Dict[str, Any]] = []
        for r in rows:
            score, matched, deviations, missing = score_product(r, {}, relaxed_soft)
            text_rel = _db_text_relevance(r, text_query)

            # With text queries, keep text-related candidates first.
            if has_text_query and text_rel <= 0 and score <= 0:
                continue

            if score <= 0:
                # Keep a tiny positive floor if text relevance exists, so we can sort/display.
                if text_rel > 0:
                    score = min(1.0, max(0.05, text_rel / 300.0))
                else:
                    continue

            fallback_scored.append({
                "row": r,
                "score": float(score),
                "text_rel": float(text_rel),
                "matched": matched,
                "deviations": (["fallback: strict constraints relaxed"] + list(deviations))[:6],
                "missing": missing,
            })

        if fallback_scored:
            fallback_scored.sort(
                key=lambda x: (
                    x.get("text_rel", 0.0),
                    x["score"],
                    str(x["row"].get("product_code", "")),
                ),
                reverse=True,
            )
            similar_scored = fallback_scored[:limit]
            fallback_used = True

    # 5) Build response
    interpreted: Dict[str, Any] = {}
    size_min = parsed.get("luminaire_size_min")
    size_max = parsed.get("luminaire_size_max")
    if size_min and size_max:
        def _mid_mm(expr: Any) -> Optional[int]:
            s = str(expr).strip()
            m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$", s)
            if m:
                a = float(m.group(1)); b = float(m.group(2))
                return int(round((a + b) / 2.0))
            m2 = re.search(r"(\d+(?:\.\d+)?)", s)
            return int(round(float(m2.group(1)))) if m2 else None
        a = _mid_mm(size_min)
        b = _mid_mm(size_max)
        if a and b:
            interpreted["size_mm"] = f"{a}x{b} mm"
    elif parsed.get("luminaire_length") and parsed.get("luminaire_width"):
        interpreted["size_mm"] = f"{parsed.get('luminaire_length')}x{parsed.get('luminaire_width')} mm"

    interpreted["parsed_filters"] = parsed
    if fallback_used:
        interpreted["fallback_mode"] = "relaxed"

    exact_hits: List[ProductHit] = []
    similar_hits: List[ProductHit] = []
    for i, s in enumerate(exact_scored):
        r = s["row"]
        image_url = _resolve_product_image_url(r.get("product_code")) if i < IMAGE_ENRICH_MAX else None
        exact_hits.append(
            ProductHit(
                product_code=str(r.get("product_code", "")).strip(),
                product_name=str(r.get("product_name", "")).strip(),
                score=s["score"],
                matched=s["matched"],
                deviations=s["deviations"],
                missing=s["missing"],
                preview={
                    "manufacturer": _clean(r.get("manufacturer")),
                    "ip_rating": _clean(r.get("ip_rating")),
                    "ik_rating": _clean(r.get("ik_rating")),
                    "cct_k": _clean(r.get("cct_k")),
                    "power_max_w": _clean(r.get("power_max_w")),
                    "lumen_output": _clean(r.get("lumen_output")),
                    "efficacy_lm_w": _clean(r.get("efficacy_lm_w")),
                    "ugr": _clean(r.get("ugr")),
                    "ugr_value": _clean(r.get("ugr_value")),
                    "warranty_years": _clean(r.get("warranty_years")),
                    "lifetime_hours": _clean(r.get("lifetime_hours")),
                    "led_rated_life_h": _clean(r.get("led_rated_life_h")),
                    "lumen_maintenance_pct": _clean(r.get("lumen_maintenance_pct")),
                    "price": _clean(r.get("price")),
                    "price_value": _clean(r.get("price_value")),
                    "image_url": _clean(image_url),
                },
                debug_filters=(
                    {
                        "filters": filters,
                        "hard_filters": hard_filters,
                        "soft_filters": soft_filters,
                        "sql_filters": sql_filters,
                        "hard_sql_filters": hard_sql_filters,
                        "used_sqlite": used_sqlite,
                    }
                    if getattr(req, "debug", False)
                    else None
                ),
                raw=None,
            )
        )

    for i, s in enumerate(similar_scored):
        r = s["row"]
        image_url = _resolve_product_image_url(r.get("product_code")) if i < IMAGE_ENRICH_MAX else None
        similar_hits.append(
            ProductHit(
                product_code=str(r.get("product_code", "")).strip(),
                product_name=str(r.get("product_name", "")).strip(),
                score=s["score"],
                matched=s["matched"],
                deviations=s["deviations"],
                missing=s["missing"],
                preview={
                    "manufacturer": _clean(r.get("manufacturer")),
                    "ip_rating": _clean(r.get("ip_rating")),
                    "ik_rating": _clean(r.get("ik_rating")),
                    "cct_k": _clean(r.get("cct_k")),
                    "power_max_w": _clean(r.get("power_max_w")),
                    "lumen_output": _clean(r.get("lumen_output")),
                    "efficacy_lm_w": _clean(r.get("efficacy_lm_w")),
                    "ugr": _clean(r.get("ugr")),
                    "ugr_value": _clean(r.get("ugr_value")),
                    "warranty_years": _clean(r.get("warranty_years")),
                    "lifetime_hours": _clean(r.get("lifetime_hours")),
                    "led_rated_life_h": _clean(r.get("led_rated_life_h")),
                    "lumen_maintenance_pct": _clean(r.get("lumen_maintenance_pct")),
                    "price": _clean(r.get("price")),
                    "price_value": _clean(r.get("price_value")),
                    "image_url": _clean(image_url),
                },
                debug_filters=(
                    {
                        "filters": filters,
                        "hard_filters": hard_filters,
                        "soft_filters": soft_filters,
                        "sql_filters": sql_filters,
                        "hard_sql_filters": hard_sql_filters,
                        "used_sqlite": used_sqlite,
                    }
                    if getattr(req, "debug", False)
                    else None
                ),
                raw=None,
            )
        )

    return SearchResponse(
        exact=exact_hits,
        similar=similar_hits,
        interpreted=interpreted,
        backend_debug_filters=(
            {
                "filters": filters,
                "hard_filters": hard_filters,
                "soft_filters": soft_filters,
                "sql_filters": sql_filters,
                "hard_sql_filters": hard_sql_filters,
                "used_sqlite": used_sqlite,
                "llm_extra": llm_extra,
                "parsed_local": parsed,
            }
            if getattr(req, "debug", False)
            else None
        ),
    )


@app.post("/facets", response_model=FacetsResponse)
def facets(req: SearchRequest):

    # 1) Local deterministic parsing
    parsed = local_text_to_filters(req.text or "") or {}
    parsed = _sanitize_filters(parsed)
    

    # 2) LLM intent → adds missing filters (does NOT override local)
    llm_extra = {}
    try:
        llm_extra = llm_intent_to_filters(req.text or "", allowed_families=ALLOWED_FAMILIES) if (req.text or "").strip() else {}
        print("🧠 /facets LLM EXTRA:", llm_extra)
    except Exception as e:
        print("🧠 /facets LLM ERROR:", repr(e))
        llm_extra = {}

    # safety: drop invalid family returned by LLM
    if "product_family" in llm_extra and ALLOWED_FAMILIES_NORM:
        fam = str(llm_extra.get("product_family") or "").strip().lower()
        if fam and fam not in ALLOWED_FAMILIES_NORM:
            llm_extra.pop("product_family", None)

    # merge safe: never overwrite local parsed filters
    for k, v in (llm_extra or {}).items():
        if k not in parsed and v is not None:
                parsed[k] = v

    # 3) User filters from UI override everything
    user_filters = _sanitize_filters(req.filters or {})
    user_filters = _normalize_ui_filters(user_filters)

    filters = {**parsed, **user_filters}
    filters = _expand_control_protocol(filters)
    sql_filters = map_filters_to_sql(filters)



    cache_key = _facets_cache_key(sql_filters)

    # ✅ IMPORTANT: when debug is ON, bypass cache to see real behavior
    if not getattr(req, "debug", False):
        cached = _facets_cache_get(cache_key)
        if cached is not None:
            return FacetsResponse(**cached)


    narrowed = pd.DataFrame()
    similar_names_prefill: List[FacetValue] = []

    if PRODUCT_DB:
        try:
            rows = PRODUCT_DB.search_products(sql_filters, limit=10000) if sql_filters else PRODUCT_DB.search_products({}, limit=10000)
            narrowed = pd.DataFrame(rows)
            similar_names_prefill = _name_prefixes_from_rows(rows, limit=30)


            
        except Exception as e:
            print(f"⚠️ SQLite facets failed: {e}")

    if narrowed.empty:
        base = DB.copy() if DB is not None else pd.DataFrame()
        narrowed = _df_filtered_subset(base, filters)
        narrowed = narrowed if narrowed is not None else pd.DataFrame()

    all_df = DB.copy() if DB is not None else pd.DataFrame()

    eff = _num_from_text_series(narrowed["efficacy_lm_w"]) if "efficacy_lm_w" in narrowed.columns else pd.Series(dtype=float)
    pwr = _num_from_text_series(narrowed["power_max_w"]) if "power_max_w" in narrowed.columns else pd.Series(dtype=float)
    lumen_calc = (eff * pwr).dropna()
    phot_lumen_minmax = {
        "min": float(lumen_calc.min()) if not lumen_calc.empty else None,
        "max": float(lumen_calc.max()) if not lumen_calc.empty else None,
    }

    resp = FacetsResponse(
        families=_top_values(narrowed, "product_family", limit=30) or _families_from_sqlite_fallback(limit=30),
        manufacturers=_top_values(narrowed, "manufacturer", limit=40) or _top_values(all_df, "manufacturer", limit=40) or _top_values_from_sqlite_fallback("manufacturer", limit=40),
        similar_names=similar_names_prefill or _top_name_prefixes(narrowed, limit=30) or _name_prefixes_from_sqlite_fallback(limit=30),
        warranty_lifetime={
            "warranty_years": _top_values(narrowed, "warranty_years", limit=10) or _top_values(all_df, "warranty_years", limit=10) or _top_values_from_sqlite_fallback("warranty_years", limit=10),
            "lifetime_hours": _top_values(narrowed, "lifetime_hours", limit=20) or _top_values(all_df, "lifetime_hours", limit=20) or _top_values_from_sqlite_fallback("lifetime_hours", limit=20),
            "led_rated_life_h": _top_values(narrowed, "led_rated_life_h", limit=20) or _top_values(all_df, "led_rated_life_h", limit=20) or _top_values_from_sqlite_fallback("led_rated_life_h", limit=20),
            "lumen_maintenance_pct": _top_values(narrowed, "lumen_maintenance_pct", limit=20) or _top_values(all_df, "lumen_maintenance_pct", limit=20) or _top_values_from_sqlite_fallback("lumen_maintenance_pct", limit=20),
            "certifications": _top_values(narrowed, "certifications", limit=20),
        },
        photometrics={
            "lumen_output": phot_lumen_minmax,
            "beam": [],
            "cct_k": _top_values(narrowed, "cct_k", limit=20),
            "cri": _top_values(narrowed, "cri", limit=20),
            "ugr": _top_values(narrowed, "ugr", limit=20),
            "asymmetry_deg": _top_values(narrowed, "asymmetry", limit=20),
        },
        power_voltage={
            "power_max_w": _min_max_numeric(narrowed, "power_max_w"),
            "power_factor": _top_values(narrowed, "power_factor", limit=20),
            "voltage_range": _top_values(narrowed, "voltage_range", limit=20),
            "control_protocol": _top_values(narrowed, "control_protocol", limit=20),
            "emergency_present": _top_values(narrowed, "emergency_present", limit=10),
        },
        dimensions_options={
            "mounting_type": _top_values(narrowed, "mounting_type", limit=20),
            "shape": _top_values(narrowed, "shape", limit=20),
            "housing_material": _top_values(narrowed, "housing_material", limit=20),
            "housing_color": _top_values(narrowed, "housing_color", limit=20),
            "protection_class": _top_values(narrowed, "protection_class", limit=20),
            "ik_rating": _top_values(narrowed, "ik_rating", limit=20),
            "ip_rating": _top_values(narrowed, "ip_rating", limit=20),
              "ranges": {
                    "diameter": _min_max_numeric(narrowed, "diameter"),
                    "luminaire_height": _min_max_numeric(narrowed, "luminaire_height"),
                    "luminaire_width": _min_max_numeric(narrowed, "luminaire_width"),
                    "luminaire_length": _min_max_numeric(narrowed, "luminaire_length"),
                },
                "options": {
                    "housing_color": _top_values(narrowed, "housing_color", limit=40),
                    "beam_angle_deg": _top_values(narrowed, "beam_angle_deg", limit=40),
                }
                
        },
        price_consumption={
            "efficacy_lm_w": _min_max_numeric(narrowed, "efficacy_lm_w"),
        },
    )
    # If families are empty but we have data, don't cache the broken payload
    if (not resp.families) and (narrowed is not None) and (not narrowed.empty):
        print("⚠️ Facets: narrowed has rows but no families. Columns:", list(narrowed.columns))


    _facets_cache_set(cache_key, resp.model_dump())
    return resp

@app.get("/database/stats")
def database_stats():
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="SQLite database not available")
    try:
        return PRODUCT_DB.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/database/refresh")
def refresh_database():
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="SQLite database not available")
    try:
        count = PRODUCT_DB.init_db(XLSX_PATH, FAMILY_MAP_PATH)
        return {"success": True, "message": f"Database refreshed with {count} products", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")

@app.get("/debug/parse")
def debug_parse(q: str = ""):
    parsed = local_text_to_filters(q or "") or {}
    parsed = _sanitize_filters(parsed)
    return {"q": q, "local": parsed, "sql": map_filters_to_sql(parsed)}

@app.get("/debug/nonnull_sample")
def debug_nonnull_sample(
    col: str = Query(..., description="Column name to check, e.g. efficacy_value"),
    limit: int = 10,
):
    if not PRODUCT_DB:
        return {"error": "no sqlite"}

    allowed = {
        "ugr_value",
        "efficacy_value",
        "lumen_output_value",
        "power_max_value",
        "power_min_value",
        "lifetime_h_value",
        "led_rated_life_value",
        "warranty_y_value",
    }

    if col not in allowed:
        return {"error": f"col not allowed. choose one of: {sorted(list(allowed))}"}

    q = f'SELECT product_code, product_name, "{col}" as value FROM products WHERE "{col}" IS NOT NULL LIMIT ?'
    cur = PRODUCT_DB.conn.execute(q, (int(limit),))
    rows = [dict(r) for r in cur.fetchall()]
    return {"col": col, "count": len(rows), "rows": rows}

if __name__ == "__main__":
    startup()
    print("\n✅ Server ready. Run with: uvicorn app.main:app --reload")
