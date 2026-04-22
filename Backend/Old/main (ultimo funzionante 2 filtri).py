# app/main.py (updated with better error handling + hard/soft filters + AI structured parsing)

from fastapi import FastAPI, HTTPException
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




from app.schema import (
    SearchRequest, ProductHit, SearchResponse,
    FacetsResponse, FacetValue,
    ALLOWED_FILTER_KEYS, HARD_FILTER_KEYS, SOFT_FILTER_KEYS,
)

from app.pim_loader import load_products
from app.scoring import score_product
from app.ai_parser import text_to_filters
from app.local_parser import local_text_to_filters

# Try to import database, but don't crash if it fails
try:
    from app.database import ProductDatabase
    HAS_DATABASE = True
except ImportError as e:
    print(f"⚠️  Database module import warning: {e}")
    print("⚠️  SQLite features will be disabled")
    HAS_DATABASE = False
    ProductDatabase = None

app = FastAPI(title="Product Finder MVP")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

@app.get("/")
def home():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


XLSX_PATH = os.getenv("PIM_XLSX", "data/ExportRO-2025-10-28_09.34.43.xlsx")
FAMILY_MAP_PATH = os.getenv("FAMILY_MAP_XLSX", "data/family_map.xlsx")
PIM_VERBOSE = os.getenv("PIM_VERBOSE", "1").strip() not in ("0", "false", "False", "no", "NO")
USE_SQLITE = os.getenv("USE_SQLITE", "1").strip() not in ("0", "false", "False", "no", "NO") and HAS_DATABASE

DB = None
PRODUCT_DB = None
FAMILY_BY_SHORT: Dict[str, str] = {}
FAMILY_BY_FIRSTWORD: Dict[str, str] = {}

# ------------------------------------------------------------
# Facets cache (in-memory)
# Keyed by HARD filters only (flat_filters)
# ------------------------------------------------------------
FACETS_CACHE = OrderedDict()   # key -> (timestamp, payload_dict)
FACETS_CACHE_MAX = 128         # max different filter combos cached
FACETS_CACHE_TTL_SEC = 180     # 3 minutes

def _facets_cache_key(flat_filters: Dict[str, Any]) -> str:
    # stable key: sort keys, normalize values to strings
    normalized = {}
    for k, v in (flat_filters or {}).items():
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
        # expired
        try:
            del FACETS_CACHE[key]
        except Exception:
            pass
        return None
    # refresh LRU position
    FACETS_CACHE.move_to_end(key)
    return payload

def _facets_cache_set(key: str, payload: Dict[str, Any]):
    FACETS_CACHE[key] = (time.time(), payload)
    FACETS_CACHE.move_to_end(key)
    while len(FACETS_CACHE) > FACETS_CACHE_MAX:
        FACETS_CACHE.popitem(last=False)



def _num_from_text_series(s: pd.Series) -> pd.Series:
    # prende il primo numero tipo 96 o 96.5 da "96 lm/W" / "15 W"
    extracted = s.astype(str).str.extract(r"(-?\d+(?:\.\d+)?)")[0]
    return pd.to_numeric(extracted, errors="coerce")


def _clean(x):
    if isinstance(x, float) and math.isnan(x):
        return None
    return x


def _sanitize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only allowed keys and drop empty values."""
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
def _norm(s: Any) -> str:
    return str(s or "").strip().lower()

def _normalize_facet_text(v: Any) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    # converti entità HTML (&lt; ecc.) e la roba tipo <lt/>
    s = html.unescape(s)
    s = s.replace("<lt/>", "<").replace("&lt;", "<").replace("&gt;", ">")
    # pulizia base
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

def _col_like(df: pd.DataFrame, *needles: str) -> Optional[str]:
    """Find a column whose name contains ALL needles (case-insensitive)."""
    if df is None or df.empty:
        return None
    cols = list(df.columns)
    for c in cols:
        cl = c.lower()
        if all(n.lower() in cl for n in needles):
            return c
    return None


def _numeric_buckets(df: pd.DataFrame, col: str, step: float = 20.0, max_buckets: int = 12) -> List[FacetValue]:
    if df is None or df.empty or col not in df.columns:
        return []

    nums = pd.to_numeric(df[col].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce").dropna()
    if nums.empty:
        return []

    mn, mx = float(nums.min()), float(nums.max())
    # evita range assurdi (es. 1605W) che ti rovinano la UI: cap a step*max_buckets
    cap = step * max_buckets
    mx_eff = min(mx, cap)

    # costruisci buckets [0-20), [20-40), ...
    buckets = []
    start = math.floor(mn / step) * step
    end = math.ceil(mx_eff / step) * step

    edges = []
    x = start
    while x < end + 1e-9:
        edges.append(x)
        x += step

    # conta
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        cnt = int(((nums >= lo) & (nums < hi)).sum())
        if cnt == 0:
            continue
        label = f"{int(lo)}-{int(hi)}"
        buckets.append(FacetValue(value=label, count=cnt, raw=label))

    return buckets[:max_buckets]



def _is_bad_facet_value(col: str, s: str) -> bool:
    c = (col or "").lower()
    t = (s or "").strip().lower()

    if not t:
        return True

    # valori zero generici
    if t in {"0", "0.0", "0 k", "0 w", "0 yr"}:
        return True

    # CCT: "0 K"
    if "cct" in c and t.startswith("0"):
        return True

    # CRI/UGR: 0 o 0.0
    if c in {"cri", "ugr"} and t in {"0", "0.0"}:
        return True

    return False



def _first_word(name: Any) -> str:
    s = str(name or "").strip()
    return s.split()[0].lower() if s else ""

def _pick_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    # trova una colonna per nome (case-insensitive), esatto o "contains"
    cols = list(df.columns)
    low = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in low:
            return low[cand.lower()]
    for c in cols:
        cl = c.lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    return None

def _load_family_map(path: str):
    global FAMILY_BY_SHORT, FAMILY_BY_FIRSTWORD

    if not os.path.exists(path):
        print(f"⚠️ family_map not found: {path}")
        FAMILY_BY_SHORT, FAMILY_BY_FIRSTWORD = {}, {}
        return

    fm = pd.read_excel(path)

    # prova a “capire” le colonne
    col_family = _pick_col(fm, ["famiglia", "family"])
    col_name   = _pick_col(fm, ["nome prodotto", "product_name", "prodotto", "name"])
    col_short  = _pick_col(fm, ["codice corto", "short_code", "codice", "code", "key"])

    if not col_family or not col_name:
        print("⚠️ family_map missing required columns (family + product_name).")
        print("   Columns:", list(fm.columns))
        FAMILY_BY_SHORT, FAMILY_BY_FIRSTWORD = {}, {}
        return

    # costruisci lookup: short_code -> family (se short_code esiste)
    FAMILY_BY_SHORT = {}
    if col_short:
        for _, r in fm.iterrows():
            fam = _norm(r.get(col_family))
            sc  = _norm(r.get(col_short))
            if fam and sc:
                FAMILY_BY_SHORT[sc] = fam

    # costruisci lookup: first_word(product_name) -> family
    FAMILY_BY_FIRSTWORD = {}
    for _, r in fm.iterrows():
        fam = _norm(r.get(col_family))
        fw = _first_word(r.get(col_name))
        if fam and fw:
            # tieni la prima occorrenza (evita sovrascritture casuali)
            FAMILY_BY_FIRSTWORD.setdefault(fw, fam)

    print(f"🧩 family_map loaded: short={len(FAMILY_BY_SHORT)} firstword={len(FAMILY_BY_FIRSTWORD)}")


def _df_filtered_subset(df: pd.DataFrame, sql_filters: Dict[str, Any]) -> pd.DataFrame:
    """
    Quick DataFrame filter approximation for facets.
    This is NOT scoring; it's just to narrow down for counts/options.
    """
    if df is None or df.empty or not sql_filters:
        return df.copy() if df is not None else pd.DataFrame()

    out = df.copy()

    # IP: support single value OR list of values
    ip = sql_filters.get("ip_rating")
    if ip and "ip_rating" in out.columns:
        ip_values = ip if isinstance(ip, list) else [ip]

        masks = []
        for one in ip_values:
            m = re.search(r"(\d+)", str(one))
            if not m:
                continue
            want = float(m.group(1))
            got = out["ip_rating"].astype(str).str.extract(r"(\d+)")[0]
            got_num = pd.to_numeric(got, errors="coerce")
            masks.append(got_num >= want)

        if masks:
            mask_any = masks[0]
            for mm in masks[1:]:
                mask_any = mask_any | mm
            out = out[mask_any]


    # CCT numeric match (handles "4000 K")
    cct = sql_filters.get("cct_k")
    if cct and "cct_k" in out.columns:
        cct_values = cct if isinstance(cct, list) else [cct]
        wants = []
        for one in cct_values:
            m = re.search(r"(\d+)", str(one))
            if m:
                wants.append(float(m.group(1)))

        if wants:
            got = out["cct_k"].astype(str).str.extract(r"(\d+)")[0]
            got_num = pd.to_numeric(got, errors="coerce")
            out = out[got_num.isin(wants)]

    # control protocol contains
    # control protocol contains (single OR list)
    cp = sql_filters.get("control_protocol")
    if cp and "control_protocol" in out.columns:
        cp_values = cp if isinstance(cp, list) else [cp]
        masks = []
        for one in cp_values:
            masks.append(out["control_protocol"].astype(str).str.lower().str.contains(str(one).lower(), na=False))
        if masks:
            mask_any = masks[0]
            for mm in masks[1:]:
                mask_any = mask_any | mm
            out = out[mask_any]


    # power_max_w supports single OR list of expressions
    p = sql_filters.get("power_max_w")
    if p and "power_max_w" in out.columns:
        p_values = p if isinstance(p, list) else [p]

        got = out["power_max_w"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0]
        got_num = pd.to_numeric(got, errors="coerce")

        masks = []
        for one in p_values:
            s = str(one).strip()
            if "-" in s:
                try:
                    a, b = s.split("-", 1)
                    lo = float(re.search(r"\d+(?:\.\d+)?", a).group())
                    hi = float(re.search(r"\d+(?:\.\d+)?", b).group())
                    masks.append((got_num >= lo) & (got_num <= hi))
                except Exception:
                    continue
            else:
                m = re.match(r"^(>=|<=|>|<)\s*(\d+(?:\.\d+)?)$", s)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    if op == ">=":
                        masks.append(got_num >= num)
                    elif op == ">":
                        masks.append(got_num > num)
                    elif op == "<=":
                        masks.append(got_num <= num)
                    elif op == "<":
                        masks.append(got_num < num)
                else:
                    try:
                        num = float(re.search(r"\d+(?:\.\d+)?", s).group())
                        masks.append(got_num == num)
                    except Exception:
                        continue

        if masks:
            mask_any = masks[0]
            for mm in masks[1:]:
                mask_any = mask_any | mm
            out = out[mask_any]
    # Lumen output supports single OR list of expressions
    lum = sql_filters.get("lumen_output")
    if lum and "lumen_output" in out.columns:
        lum_values = lum if isinstance(lum, list) else [lum]

        got = out["lumen_output"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0]
        got_num = pd.to_numeric(got, errors="coerce")

        masks = []
        for one in lum_values:
            s = str(one).strip()
            if "-" in s:
                try:
                    a, b = s.split("-", 1)
                    lo = float(re.search(r"\d+(?:\.\d+)?", a).group())
                    hi = float(re.search(r"\d+(?:\.\d+)?", b).group())
                    masks.append((got_num >= lo) & (got_num <= hi))
                except Exception:
                    continue
            else:
                m = re.match(r"^(>=|<=|>|<)\s*(\d+(?:\.\d+)?)$", s)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    if op == ">=":
                        masks.append(got_num >= num)
                    elif op == ">":
                        masks.append(got_num > num)
                    elif op == "<=":
                        masks.append(got_num <= num)
                    elif op == "<":
                        masks.append(got_num < num)
                else:
                    try:
                        num = float(re.search(r"\d+(?:\.\d+)?", s).group())
                        masks.append(got_num == num)
                    except Exception:
                        continue

        if masks:
            mask_any = masks[0]
            for mm in masks[1:]:
                mask_any = mask_any | mm
            out = out[mask_any]
    # Efficacy supports single OR list of expressions
    efff = sql_filters.get("efficacy_lm_w")
    if efff and "efficacy_lm_w" in out.columns:
        eff_values = efff if isinstance(efff, list) else [efff]

        got = out["efficacy_lm_w"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0]
        got_num = pd.to_numeric(got, errors="coerce")

        masks = []
        for one in eff_values:
            s = str(one).strip()
            if "-" in s:
                try:
                    a, b = s.split("-", 1)
                    lo = float(re.search(r"\d+(?:\.\d+)?", a).group())
                    hi = float(re.search(r"\d+(?:\.\d+)?", b).group())
                    masks.append((got_num >= lo) & (got_num <= hi))
                except Exception:
                    continue
            else:
                m = re.match(r"^(>=|<=|>|<)\s*(\d+(?:\.\d+)?)$", s)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    if op == ">=":
                        masks.append(got_num >= num)
                    elif op == ">":
                        masks.append(got_num > num)
                    elif op == "<=":
                        masks.append(got_num <= num)
                    elif op == "<":
                        masks.append(got_num < num)
                else:
                    try:
                        num = float(re.search(r"\d+(?:\.\d+)?", s).group())
                        masks.append(got_num == num)
                    except Exception:
                        continue

        if masks:
            mask_any = masks[0]
            for mm in masks[1:]:
                mask_any = mask_any | mm
            out = out[mask_any]
    # UGR supports single OR list (numeric + comparator)
    ugr = sql_filters.get("ugr")
    if ugr and "ugr" in out.columns:
        ugr_values = ugr if isinstance(ugr, list) else [ugr]

        got = out["ugr"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0]
        got_num = pd.to_numeric(got, errors="coerce")

        masks = []
        for one in ugr_values:
            s = str(one).strip()
            m = re.match(r"^(>=|<=|>|<)\s*(\d+(?:\.\d+)?)$", s)
            if m:
                op, num = m.group(1), float(m.group(2))
                if op == ">=":
                    masks.append(got_num >= num)
                elif op == ">":
                    masks.append(got_num > num)
                elif op == "<=":
                    masks.append(got_num <= num)
                elif op == "<":
                    masks.append(got_num < num)
            else:
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", s).group())
                    masks.append(got_num == num)
                except Exception:
                    continue

        if masks:
            mask_any = masks[0]
            for mm in masks[1:]:
                mask_any = mask_any | mm
            out = out[mask_any]
    # CRI supports single OR list (numeric + comparator)
    cri = sql_filters.get("cri")
    if cri and "cri" in out.columns:
        cri_values = cri if isinstance(cri, list) else [cri]

        got = out["cri"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0]
        got_num = pd.to_numeric(got, errors="coerce")

        masks = []
        for one in cri_values:
            s = str(one).strip()
            m = re.match(r"^(>=|<=|>|<)\s*(\d+(?:\.\d+)?)$", s)
            if m:
                op, num = m.group(1), float(m.group(2))
                if op == ">=":
                    masks.append(got_num >= num)
                elif op == ">":
                    masks.append(got_num > num)
                elif op == "<=":
                    masks.append(got_num <= num)
                elif op == "<":
                    masks.append(got_num < num)
            else:
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", s).group())
                    masks.append(got_num == num)
                except Exception:
                    continue

        if masks:
            mask_any = masks[0]
            for mm in masks[1:]:
                mask_any = mask_any | mm
            out = out[mask_any]


    return out


def _top_values(df: pd.DataFrame, col: str, limit: int = 30) -> List[FacetValue]:
    if df is None or df.empty or col not in df.columns:
        return []

    s = df[col].dropna().apply(_normalize_facet_text)
    s = s[s != ""]

    # rimuovi valori spazzatura
    s = s[~s.apply(lambda x: _is_bad_facet_value(col, x))]

    if s.empty:
        return []

    # calcola counts (sempre!)
    counts = s.value_counts()

    # ordinamento speciale numerico per IP / IK / CCT
    if col in ("ip_rating", "ik_rating", "cct_k"):
        items = [(k, int(v)) for k, v in counts.items()]
        items.sort(
            key=lambda kv: (
                _extract_int(str(kv[0])) is None,
                _extract_int(str(kv[0])) or 10**9
            )
        )
        items = items[:limit]
    else:
        # default: top per frequenza
        items = [(k, int(v)) for k, v in counts.head(limit).items()]

    return [
        {"value": _truncate(str(k), 80), "count": int(v), "raw": str(k)}
        for k, v in items
]







def _min_max_numeric(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    if df is None or df.empty or col not in df.columns:
        return {"min": None, "max": None}
    nums = pd.to_numeric(df[col].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce")
    nums = nums.dropna()
    if nums.empty:
        return {"min": None, "max": None}
    return {"min": float(nums.min()), "max": float(nums.max())}

def _to_float_series(df: pd.DataFrame, col: str) -> pd.Series:
    # estrae numeri anche da stringhe tipo "120 lm/W" o "40 W"
    s = df[col].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0]
    return pd.to_numeric(s, errors="coerce")


def _facet_options(df: pd.DataFrame, col: str, top: int = 50):
    if df is None or df.empty or col not in df.columns:
        return []
    s = df[col].fillna("").astype(str).str.strip()
    s = s[s != ""]
    vc = s.value_counts().head(top)
    return [{"value": k, "count": int(v)} for k, v in vc.items()]




# Temp
@app.get("/debug/sqlite_sample")
def debug_sqlite_sample():
    if not PRODUCT_DB:
        return {"error": "no sqlite"}
    return {"sample": PRODUCT_DB.debug_sample(5)}

@app.on_event("startup")
def startup():
    global DB, PRODUCT_DB

    print("🚀 Starting Product Finder MVP...")

    # Load to DataFrame (for backward compatibility)
    try:
        DB = load_products(XLSX_PATH, verbose=PIM_VERBOSE)
        try:
            _load_family_map(FAMILY_MAP_PATH)

            if DB is not None and not DB.empty:
                # colonne nel DB
                short_col = "Short product code" if "Short product code" in DB.columns else None

                name_col = None
                for cand in ["product_name", "Product name", "Nome prodotto", "name"]:
                    if cand in DB.columns:
                        name_col = cand
                        break

                if not name_col:
                    print("⚠️ Cannot build product_family: product name column not found in DB")
                else:
                    def _assign_family(row) -> Optional[str]:
                        # 1) prova short product code
                        if short_col:
                            sc = _norm(row.get(short_col))
                            if sc and sc in FAMILY_BY_SHORT:
                                return FAMILY_BY_SHORT[sc]

                        # 2) fallback: first word of product name
                        fw = _first_word(row.get(name_col))
                        if fw and fw in FAMILY_BY_FIRSTWORD:
                            return FAMILY_BY_FIRSTWORD[fw]

                        return None

                    DB["product_family"] = DB.apply(_assign_family, axis=1)
                    print("✅ product_family column created in DataFrame")
                    print("product_family non-null:", int(DB["product_family"].notna().sum()))

        except Exception as e:
            print(f"⚠️ family_map apply failed: {e}")

        if DB is not None:
            print(f"📊 Loaded {len(DB)} products to DataFrame")
        else:
            print("⚠️  DataFrame is None after loading")
    except Exception as e:
        print(f"❌ Failed to load DataFrame: {e}")
        DB = pd.DataFrame()  # Empty as fallback

    # Initialize SQLite database if enabled
    if USE_SQLITE and HAS_DATABASE:
        try:
            PRODUCT_DB = ProductDatabase()
            count = PRODUCT_DB.init_db(XLSX_PATH, FAMILY_MAP_PATH)
            print(f"💾 SQLite database ready: {count} products loaded")

            # Show database stats
            stats = PRODUCT_DB.get_stats()
            print(f"📈 Database stats: {stats.get('total_products', 0)} total products")

        except Exception as e:
            print(f"⚠️  SQLite initialization failed: {e}")
            print("⚠️  Falling back to DataFrame only")
            PRODUCT_DB = None
    else:
        print("ℹ️  SQLite is disabled or not available")

    print("✅ Startup complete")

# Map user-facing filter keys -> numeric SQLite columns
MAP_NUM = {
    "ugr": "ugr_value",
    "efficacy_lm_w": "efficacy_value",
    "lumen_output": "lumen_output_value",
    "power_max_w": "power_max_value",
    "power_min_w": "power_min_value",
    "lifetime_hours": "lifetime_h_value",
    "led_rated_life_h": "led_rated_life_value",
    "warranty_years": "warranty_y_value",
}



@app.on_event("shutdown")
def shutdown():
    """Clean shutdown"""
    if PRODUCT_DB:
        try:
            PRODUCT_DB.close()
            print("✅ Database connection closed")
        except Exception:
            pass


@app.get("/health")
def health():
    """Health check endpoint"""
    health_info = {
        "status": "ok",
        "xlsx_path": XLSX_PATH,
        "dataframe_loaded": DB is not None and not DB.empty,
        "dataframe_rows": int(len(DB)) if DB is not None else 0,
        "sqlite_available": HAS_DATABASE,
        "sqlite_enabled": USE_SQLITE,
        "sqlite_active": PRODUCT_DB is not None,
    }

    if PRODUCT_DB:
        try:
            stats = PRODUCT_DB.get_stats()
            health_info["sqlite_stats"] = stats
        except Exception as e:
            health_info["sqlite_error"] = str(e)

    return health_info


@app.get("/debug/data")
def debug_data():
    """Debug endpoint to see data status"""
    if DB is None or DB.empty:
        return {"error": "No data loaded"}

    sample = DB.head(3).fillna("").to_dict(orient="records")

    return {
        "total_rows": len(DB),
        "columns": list(DB.columns),
        "sample": sample,
        "using_sqlite": PRODUCT_DB is not None,
    }

@app.post("/facets", response_model=FacetsResponse)
def facets(req: SearchRequest):
    """
    Faceted navigation endpoint.
    Returns available facet values based on current HARD constraints only.
    Soft filters are NOT used to narrow the dataset (otherwise facets collapse).
    """

    # --- Parse filters (same logic as /search) ---
    ai_parsed: Dict[str, Any] = {"hard_filters": {}, "soft_filters": {}}
    try:
        ai_parsed = text_to_filters(req.text or "")
        if not isinstance(ai_parsed, dict):
            ai_parsed = {"hard_filters": {}, "soft_filters": {}}
    except Exception:
        ai_parsed = {"hard_filters": {}, "soft_filters": {}}

    fallback_filters = local_text_to_filters(req.text or "")





    # If query contains explicit comparators, OVERRIDE AI numeric parsing with local parser
    if any(op in (req.text or "") for op in [">=", "<=", ">", "<"]):
        for k in ["lumen_output", "efficacy_lm_w", "power_max_w", "ugr", "cri"]:
            if k in fallback_filters:
                # put into the right bucket
                if k in HARD_FILTER_KEYS:
                    ai_parsed.setdefault("hard_filters", {})
                    ai_parsed["hard_filters"][k] = fallback_filters[k]
                    # remove from soft if present
                    ai_parsed.setdefault("soft_filters", {})
                    ai_parsed["soft_filters"].pop(k, None)
                else:
                    ai_parsed.setdefault("soft_filters", {})
                    ai_parsed["soft_filters"][k] = fallback_filters[k]
                    # remove from hard if present
                    ai_parsed.setdefault("hard_filters", {})
                    ai_parsed["hard_filters"].pop(k, None)




    user_filters = _sanitize_filters(req.filters or {})
    ai_hard = _sanitize_filters(ai_parsed.get("hard_filters") or {})

    fb_all = _sanitize_filters(fallback_filters)
    fb_hard = {k: v for k, v in fb_all.items() if k in HARD_FILTER_KEYS}

    # FINAL hard filters only
    hard_filters = {
        **fb_hard,
        **ai_hard,
        **{k: v for k, v in user_filters.items() if k in HARD_FILTER_KEYS},
    }

    # 🔑 IMPORTANT: facets are computed using ONLY hard filters
    flat_filters = dict(hard_filters)

        # UGR class: treat "<19" as "<=19"
    if "ugr" in fallback_filters:
        v = str(fallback_filters["ugr"]).strip()
        if v.startswith("<") and not v.startswith("<="):
            fallback_filters["ugr"] = "<=" + v[1:]

    # Map UGR textual filter to numeric column in SQLite (facets)
    if "ugr" in flat_filters:
        flat_filters["ugr_value"] = flat_filters.pop("ugr")



    for k, kk in list(MAP_NUM.items()):
        if k in flat_filters:
            flat_filters[kk] = flat_filters.pop(k)


    # --- Cache check (HARD filters only) ---
    cache_key = _facets_cache_key(flat_filters)
    cached = _facets_cache_get(cache_key)
    if cached is not None:
        return FacetsResponse(**cached)

    # --- Data source selection ---
    narrowed = pd.DataFrame()

    if PRODUCT_DB:
        try:
            rows = PRODUCT_DB.search_products(flat_filters, limit=10000)
            narrowed = pd.DataFrame(rows)
        except Exception as e:
            print(f"⚠️ SQLite facets fallback: {e}")


    if narrowed.empty:
                base = DB.copy() if DB is not None else pd.DataFrame()
                narrowed = _df_filtered_subset(base, flat_filters)
                narrowed = narrowed if narrowed is not None else pd.DataFrame()


    eff = _num_from_text_series(narrowed["efficacy_lm_w"]) if "efficacy_lm_w" in narrowed.columns else pd.Series(dtype=float)
    pwr = _num_from_text_series(narrowed["power_max_w"]) if "power_max_w" in narrowed.columns else pd.Series(dtype=float)

    lumen_calc = (eff * pwr).dropna()

    phot_lumen_minmax = {
        "min": float(lumen_calc.min()) if not lumen_calc.empty else None,
        "max": float(lumen_calc.max()) if not lumen_calc.empty else None,
}



    # --- resolve Warranty columns ---
    COL_WARRANTY_YEARS = _col_like(narrowed, "garanzia")          # es: "Garanzia (anni)"
    COL_STANDARDS      = _col_like(narrowed, "norme")            # es: "Norme di riferimento"
    COL_LUM_MAINT      = _col_like(narrowed, "lumen", "maintenance")
    COL_FAILURE_RATE   = _col_like(narrowed, "failure", "rate")
    COL_LED_LIFE       = _col_like(narrowed, "rated", "life") or _col_like(narrowed, "life", "h")

    # --- resolve Photometrics columns ---
    COL_CCT            = _col_like(narrowed, "cct")
    COL_CRI            = _col_like(narrowed, "cri")
    COL_UGR            = _col_like(narrowed, "ugr")
    COL_ASYM           = _col_like(narrowed, "asimmet")  # "Gradi di asimmet..."

    # columns for lumen calc
    COL_EFFICACY       = _col_like(narrowed, "luminous", "efficacy") or _col_like(narrowed, "efficacy")
    COL_SYS_POWER      = _col_like(narrowed, "total", "system", "power") or _col_like(narrowed, "system", "power")


    # ---- Compute luminous flux (lm) = luminous efficacy (lm/W) * total system power (W)


   # if COL_EFFICACY and COL_SYS_POWER:
    #    eff = _to_float_series(narrowed, COL_EFFICACY)
     #   pwr = _to_float_series(narrowed, COL_SYS_POWER)
      #  narrowed["lumen_output_calc"] = eff * pwr
    #else:
     #   narrowed["lumen_output_calc"] = pd.NA

    # ---- DEBUG ----
    print(f"🧩 FACETS request: '{req.text[:60] if req.text else ''}'")
    print(f"   Hard filters: {hard_filters}")
    print(f"   Narrowed rows: {len(narrowed) if narrowed is not None else 'None'}")

    # --- Build facets ---
    resp = FacetsResponse(
    # 1) Families (derivata da family_map -> product_family)
    families=_top_values(narrowed, "product_family", limit=30),

    # 2) Warranty & Lifespan (colonne italiane dal tuo screenshot)
    warranty_lifetime={
        "warranty_years": _top_values(narrowed, "warranty_years", limit=10),
        "lifetime_hours": _top_values(narrowed, "lifetime_hours", limit=20),
        "certifications": _top_values(narrowed, "certifications", limit=20),
    },




    photometrics={
        "lumen_output": phot_lumen_minmax,
        "beam": [],  # lo agganciamo quando mi mandi il nome colonna BEAM esatto
        "cct_k": _top_values(narrowed, COL_CCT, limit=20) if COL_CCT else [],
        "cri": _top_values(narrowed, COL_CRI, limit=20) if COL_CRI else [],
        "ugr": _top_values(narrowed, COL_UGR, limit=20) if COL_UGR else [],
        "asymmetry_deg": _top_values(narrowed, COL_ASYM, limit=20) if COL_ASYM else [],
    },


    # 4) Power & Voltage (come avevi già + buckets)
    power_voltage={
        "power_max_w": _min_max_numeric(narrowed, "power_max_w"),
        "power_max_w_buckets": _numeric_buckets(narrowed, "power_max_w", step=20.0, max_buckets=12),
        "power_factor": _top_values(narrowed, "power_factor", limit=20),
        "voltage_range": _top_values(narrowed, "voltage_range", limit=20),
        "control_protocol": _top_values(narrowed, "control_protocol", limit=20),
        "emergency_present": _top_values(narrowed, "emergency_present", limit=10),
    },

    # 5) Dimensions & Options (come avevi già)
    dimensions_options={
        "mounting_type": _top_values(narrowed, "mounting_type", limit=20),
        "shape": _top_values(narrowed, "shape", limit=20),
        "housing_material": _top_values(narrowed, "housing_material", limit=20),
        "housing_color": _top_values(narrowed, "housing_color", limit=20),
        "protection_class": _top_values(narrowed, "protection_class", limit=20),
        "ik_rating": _top_values(narrowed, "ik_rating", limit=20),
        "ip_rating": _top_values(narrowed, "ip_rating", limit=20),
    },

    # 6) Price & Consumption
    price_consumption={
        "efficacy_lm_w": _min_max_numeric(narrowed, "efficacy_lm_w"),
        # "surge_protection_kv": _top_values(narrowed, "surge_protection_kv", limit=20),
    },
)
    _facets_cache_set(cache_key, resp.model_dump())
    return resp


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    """Main search endpoint"""
    print("RUNNING FILE:", __file__)

    # --- Parse filters (AI + fallback) ---
    ai_parsed: Dict[str, Any] = {"hard_filters": {}, "soft_filters": {}}
    ai_error: Optional[str] = None

    try:
        ai_parsed = text_to_filters(req.text or "")
        if not isinstance(ai_parsed, dict):
            ai_parsed = {"hard_filters": {}, "soft_filters": {}}
    except Exception as e:
        ai_error = str(e)
        ai_parsed = {"hard_filters": {}, "soft_filters": {}}

    fallback_filters = local_text_to_filters(req.text or "")

    # If query contains explicit comparators, OVERRIDE AI numeric parsing with local parser
    if any(op in (req.text or "") for op in [">=", "<=", ">", "<"]):
        for k in ["lumen_output", "efficacy_lm_w", "power_max_w", "ugr", "cri"]:
            if k in fallback_filters:
                # put into the right bucket
                if k in HARD_FILTER_KEYS:
                    ai_parsed.setdefault("hard_filters", {})
                    ai_parsed["hard_filters"][k] = fallback_filters[k]
                    # remove from soft if present
                    ai_parsed.setdefault("soft_filters", {})
                    ai_parsed["soft_filters"].pop(k, None)
                else:
                    ai_parsed.setdefault("soft_filters", {})
                    ai_parsed["soft_filters"][k] = fallback_filters[k]
                    # remove from hard if present
                    ai_parsed.setdefault("hard_filters", {})
                    ai_parsed["hard_filters"].pop(k, None)


    # --- Build FINAL hard/soft filters (sanitized) ---
    user_filters = _sanitize_filters(req.filters or {})

    ai_hard = _sanitize_filters(ai_parsed.get("hard_filters") or {})
    ai_soft = _sanitize_filters(ai_parsed.get("soft_filters") or {})

    fb_all = _sanitize_filters(fallback_filters)
    fb_hard = {k: v for k, v in fb_all.items() if k in HARD_FILTER_KEYS}
    fb_soft = {k: v for k, v in fb_all.items() if k in SOFT_FILTER_KEYS}


    # If query is about efficacy (lm/w), DO NOT treat the same number as lumen output
    t = (req.text or "").lower().replace(" ", "")
    if "lm/w" in t or "lmw" in t:
        ai_soft.pop("lumen_output", None)
        ai_hard.pop("lumen_output", None)
        fb_soft.pop("lumen_output", None)
        fb_hard.pop("lumen_output", None)

    # Priority: user overrides AI; AI overrides fallback
    hard_filters = {
        **fb_hard,
        **ai_hard,
        **{k: v for k, v in user_filters.items() if k in HARD_FILTER_KEYS},
    }
    soft_filters = {
        **fb_soft,
        **ai_soft,
        **{k: v for k, v in user_filters.items() if k in SOFT_FILTER_KEYS},
    }
# Normalize UGR class once and safely on FINAL filters
    for d in (hard_filters, soft_filters):
        if "ugr" in d:
            v = str(d["ugr"]).strip()
            if v.startswith("<") and not v.startswith("<="):
                d["ugr"] = "<=" + v[1:]

    print("✅ user_filters:", user_filters)
    print("✅ hard_filters FINAL:", hard_filters)
    print("✅ soft_filters FINAL:", soft_filters)


    print(f"🔍 Search request: '{req.text[:50] if req.text else 'No text'}'")
    print(f"   Hard: {hard_filters}")
    print(f"   Soft: {soft_filters}")

    # --- Choose data source ---
    subset = None

    # --- Build SQLite filters (raw + mapped) ---
    sql_filters_raw = {**hard_filters, **soft_filters}

    sql_filters_mapped = dict(sql_filters_raw)
    for k, kk in MAP_NUM.items():
        if k in sql_filters_mapped:
            sql_filters_mapped[kk] = sql_filters_mapped.pop(k)

    print("✅ sql_filters_raw:", sql_filters_raw)
    print("✅ sql_filters_mapped:", sql_filters_mapped)

    # --- Try SQLite first ---
    subset = None
    if PRODUCT_DB:
        try:
            sql_results = PRODUCT_DB.search_products(sql_filters_mapped, limit=200)

            if sql_results:
                hits = []
                for r in sql_results:
                    hits.append(
                        ProductHit(
                            product_code=str(r.get("product_code", "")).strip(),
                            product_name=str(r.get("product_name", "")).strip(),
                            score=1.0,
                            matched={},
                            deviations=[],
                            missing=[],
                            preview={
                                "ugr": _clean(r.get("ugr")),
                                "ugr_value": _clean(r.get("ugr_value")),
                                "lumen_output": _clean(r.get("lumen_output")),
                                "efficacy_lm_w": _clean(r.get("efficacy_lm_w")),
                                "cct_k": _clean(r.get("cct_k")),
                                "ip_rating": _clean(r.get("ip_rating")),
                            },
                            debug_filters=(
                                {
                                    "hard_filters": hard_filters,
                                    "soft_filters": soft_filters,
                                    "sql_filters_raw": sql_filters_raw,
                                    "sql_filters_mapped": sql_filters_mapped,
                                    "used_sqlite": True,
                                }
                                if getattr(req, "debug", False)
                                else None
                            ),
                            raw=None,
                        )
                    )

                limit = max(1, int(req.limit or 20))
                hits = hits[:limit]
                return SearchResponse(exact=hits, similar=[])

            # SQLite returned nothing -> fallback to DataFrame
            subset = DB.copy() if DB is not None else pd.DataFrame()

        except Exception as e:
            print(f"⚠️  SQLite search failed: {e}")
            subset = DB.copy() if DB is not None else pd.DataFrame()
    else:
        subset = DB.copy() if DB is not None else pd.DataFrame()


    # Check if we have data
    if subset is None or subset.empty:
        print("   No data available for search")
        return SearchResponse(exact=[], similar=[])

    print(f"   Searching in {len(subset)} products")

    # --- Apply basic pre-filtering using FINAL hard filters ---
    if hard_filters.get("ip_rating") and "ip_rating" in subset.columns:
        subset = subset[subset["ip_rating"].notna()].copy()

    if hard_filters.get("control_protocol") and "control_protocol" in subset.columns:
        subset = subset[subset["control_protocol"].notna()].copy()

    # --- Score products ---
    hits: List[ProductHit] = []

    for prod in subset.to_dict(orient="records"):
        try:
            score, matched, deviations, missing = score_product(
                prod,
                hard_filters=hard_filters,
                soft_filters=soft_filters,
            )

            debug_payload = None
            if getattr(req, "debug", False):
                debug_payload = {
                    "hard_filters": hard_filters,
                    "soft_filters": soft_filters,
                    "ai_parsed": ai_parsed,
                    "fallback_filters": fallback_filters,
                    "ai_error": ai_error,
                    "used_sqlite": PRODUCT_DB is not None and bool(sql_filters_mapped),
                    "sql_filters": sql_filters_mapped,
                }

            preview = {
                "ip_rating": _clean(prod.get("ip_rating")),
                "cct_k": _clean(prod.get("cct_k")),
                "power_max_w": _clean(prod.get("power_max_w")),
                "control_protocol": _clean(prod.get("control_protocol")),
                "lumen_output": _clean(prod.get("lumen_output")),
                "beam_angle_deg": _clean(prod.get("beam_angle_deg")),
            }

            family = _clean(prod.get("product_family"))
            if family:
                preview["product_family"] = family

            hits.append(
                ProductHit(
                    product_code=str(prod.get("product_code", "")).strip(),
                    product_name=str(prod.get("product_name", "")).strip(),
                    score=float(_clean(score) or 0.0),
                    matched={k: _clean(v) for k, v in (matched or {}).items()},
                    deviations=[str(d) for d in (deviations or [])],
                    missing=[str(m) for m in (missing or [])],
                    preview=preview,
                    debug_filters=debug_payload,
                    raw=None,
                )
            )
        except Exception as e:
            print(f"⚠️  Error scoring product {prod.get('product_code')}: {e}")
            continue

    # --- Sort and limit results ---
    hits.sort(key=lambda x: x.score, reverse=True)

    if not hits and PRODUCT_DB:
        sql_results = PRODUCT_DB.search_products(sql_filters_mapped, limit=20)
        hits = [
            ProductHit(
                product_code=str(r.get("product_code", "")).strip(),
                product_name=str(r.get("product_name", "")).strip(),
                score=1.0,
                matched={},
                deviations=[],
                missing=[],
                preview={},
                debug_filters={
                    "hard_filters": hard_filters,
                    "soft_filters": soft_filters,
                    "sql_filters_raw": sql_filters_raw,
                    "sql_filters_mapped": sql_filters_mapped,
                    "used_sqlite": True,
                } if getattr(req, "debug", False) else None,
                raw=None,
            )
            for r in sql_results
        ]


    exact = [h for h in hits if h.score >= 0.999]
    similar = [h for h in hits if 0.4 <= h.score < 0.999]


    limit = max(1, int(req.limit or 20))
    exact = exact[:limit]
    remaining = max(0, limit - len(exact))
    similar = similar[:remaining]

    print(f"   Results: {len(exact)} exact, {len(similar)} similar")

    return SearchResponse(exact=exact, similar=similar)


# Add database management endpoints
@app.get("/database/stats")
def database_stats():
    """Get database statistics"""
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="SQLite database not available")

    try:
        stats = PRODUCT_DB.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/database/refresh")
def refresh_database():
    """Refresh database from Excel file"""
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="SQLite database not available")

    try:
        count = PRODUCT_DB.init_db(XLSX_PATH, FAMILY_MAP_PATH)
        return {"success": True, "message": f"Database refreshed with {count} products", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")


if __name__ == "__main__":
    # For debugging
    startup()
    print("\n✅ Server ready. Run with: uvicorn app.main:app --reload")

@app.get("/debug/test_filters")
def debug_test_filters():
    # prova con filtri vuoti e con alcuni esempi comuni
    tests = [
        ("EMPTY", {}),
        ("IP>=65", {"ip_rating": ">=IP65"}),
        ("CCT=4000", {"cct_k": "4000"}),
        ("UGR<=19", {"ugr": "<=19"}),
        ("CRI>=80", {"cri": ">=80"}),
        ("LUM>=5000", {"lumen_output": ">=5000"}),
        ("EFF>=120", {"efficacy_lm_w": ">=120"}),
        ("IP>=65 + CCT=4000", {"ip_rating": ">=IP65", "cct_k": "4000"}),
    ]

    out = []
    for name, f in tests:
        if PRODUCT_DB:
            rows = PRODUCT_DB.search_products(f, limit=5)
            out.append({"test": name, "filters": f, "count_sample": len(rows), "sample": rows[:1]})
        else:
            out.append({"test": name, "filters": f, "error": "no sqlite"})
    return {"tests": out}
@app.get("/debug/efficacy_ge_120")
def debug_efficacy_ge_120():
    if not PRODUCT_DB:
        return {"error": "no sqlite"}

    rows = PRODUCT_DB.search_products({"efficacy_lm_w": ">=120"}, limit=5)
    return {
        "sample_count": len(rows),
        "sample": rows[:1],
    }
@app.get("/debug/parse")
def debug_parse(q: str = ""):
    a = {}
    b = {}
    try:
        a = text_to_filters(q)  # AI parser
    except Exception as e:
        a = {"error": str(e)}
    try:
        b = local_text_to_filters(q)  # local parser
    except Exception as e:
        b = {"error": str(e)}
    return {"q": q, "ai": a, "local": b}
@app.get("/debug/search_run")
def debug_search_run(q: str = ""):
    # parse
    ai_parsed = {"hard_filters": {}, "soft_filters": {}}
    try:
        ai_parsed = text_to_filters(q or "")
        if not isinstance(ai_parsed, dict):
            ai_parsed = {"hard_filters": {}, "soft_filters": {}}
    except Exception as e:
        ai_parsed = {"hard_filters": {}, "soft_filters": {}, "error": str(e)}

    fallback_filters = local_text_to_filters(q or "")

    # If query contains explicit comparators, OVERRIDE AI numeric parsing with local parser
    if any(op in (q or "") for op in [">=", "<=", ">", "<"]):
        for k in ["lumen_output", "efficacy_lm_w", "power_max_w", "ugr", "cri"]:
            if k in fallback_filters:
                if k in HARD_FILTER_KEYS:
                    ai_parsed.setdefault("hard_filters", {})
                    ai_parsed["hard_filters"][k] = fallback_filters[k]
                    ai_parsed.setdefault("soft_filters", {})
                    ai_parsed["soft_filters"].pop(k, None)
                else:
                    ai_parsed.setdefault("soft_filters", {})
                    ai_parsed["soft_filters"][k] = fallback_filters[k]
                    ai_parsed.setdefault("hard_filters", {})
                    ai_parsed["hard_filters"].pop(k, None)

    # Extra safety: if query is about lm/w, remove mistaken lumen_output from AI
    if "lm/w" in (q or "").lower():
        ai_parsed.setdefault("soft_filters", {})
        ai_parsed["soft_filters"].pop("lumen_output", None)


        # sanitize
        ai_hard = _sanitize_filters(ai_parsed.get("hard_filters") or {})
        ai_soft = _sanitize_filters(ai_parsed.get("soft_filters") or {})
        fb_all = _sanitize_filters(fallback_filters)
        fb_hard = {k: v for k, v in fb_all.items() if k in HARD_FILTER_KEYS}
        fb_soft = {k: v for k, v in fb_all.items() if k in SOFT_FILTER_KEYS}

        hard_filters = {**fb_hard, **ai_hard}
        soft_filters = {**fb_soft, **ai_soft}

        sql_filters = {**hard_filters, **soft_filters}

        # query sqlite
        sqlite_count = None
        sqlite_sample = []
        if PRODUCT_DB and sql_filters:
            rows = PRODUCT_DB.search_products(sql_filters, limit=5)
            sqlite_count = len(rows)
            sqlite_sample = rows[:1]

        # score sample (first 20 rows only)
        hits = []
        if PRODUCT_DB and sql_filters:
            rows = PRODUCT_DB.search_products(sql_filters, limit=20)
            for prod in rows:
                s, matched, dev, missing = score_product(prod, hard_filters=hard_filters, soft_filters=soft_filters)
                hits.append({"product_code": prod.get("product_code"), "score": float(s), "matched": matched, "dev": dev, "missing": missing})

        return {
            "q": q,
            "ai_parsed": ai_parsed,
            "fallback_filters": fallback_filters,
            "hard_filters_final": hard_filters,
            "soft_filters_final": soft_filters,
            "sql_filters": sql_filters,
            "sqlite_sample_count": sqlite_count,
            "sqlite_sample_row": sqlite_sample,
            "scored_hits_count": len(hits),
            "scored_hits_sample": hits[:3],
        }
@app.get("/debug/search_sqlite_count")
def debug_search_sqlite_count(q: str = ""):
    ai_parsed = text_to_filters(q or "")
    fallback_filters = local_text_to_filters(q or "")

    if any(op in (q or "") for op in [">=", "<=", ">", "<"]):
        for k in ["lumen_output", "efficacy_lm_w", "power_max_w", "ugr", "cri"]:
            if k in fallback_filters:
                ai_parsed.setdefault("soft_filters", {})
                ai_parsed["soft_filters"][k] = fallback_filters[k]
        if "lm/w" in (q or "").lower():
            ai_parsed.setdefault("soft_filters", {})
            ai_parsed["soft_filters"].pop("lumen_output", None)

    sql_filters = _sanitize_filters({**ai_parsed.get("hard_filters", {}), **ai_parsed.get("soft_filters", {})})

    if not PRODUCT_DB:
        return {"error": "no sqlite"}

    rows = PRODUCT_DB.search_products(sql_filters, limit=5)
    return {"q": q, "sql_filters": sql_filters, "count": len(rows), "sample": rows[:1]}

@app.get("/debug/ugr_nonnull_sample")
def debug_ugr_nonnull_sample():
    if not PRODUCT_DB:
        return {"error": "no sqlite"}

    # rows where UGR text exists
    cur = PRODUCT_DB.conn.execute(
        "SELECT product_code, ugr, ugr_value, ugr_op FROM products WHERE ugr IS NOT NULL LIMIT 20"
    )
    rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "rows": rows[:10]}

@app.get("/debug/search_run_min")
def debug_search_run_min(q: str = ""):
    # parse (AI + local)
    ai_parsed = {"hard_filters": {}, "soft_filters": {}}
    try:
        ai_parsed = text_to_filters(q or "")
        if not isinstance(ai_parsed, dict):
            ai_parsed = {"hard_filters": {}, "soft_filters": {}}
    except Exception:
        ai_parsed = {"hard_filters": {}, "soft_filters": {}}

    fallback_filters = local_text_to_filters(q or "")

    # IMPORTANT: treat UGR class "<19" as "<=19"
    if "ugr" in fallback_filters and str(fallback_filters["ugr"]).startswith("<"):
        fallback_filters["ugr"] = "<=" + str(fallback_filters["ugr"])[1:]

    # comparator override (local wins)
    if any(op in (q or "") for op in [">=", "<=", ">", "<"]):
        for k in ["lumen_output", "efficacy_lm_w", "power_max_w", "ugr", "cri"]:
            if k in fallback_filters:
                ai_parsed.setdefault("soft_filters", {})
                ai_parsed["soft_filters"][k] = fallback_filters[k]
                ai_parsed.setdefault("hard_filters", {})
                ai_parsed["hard_filters"].pop(k, None)

    hard_filters = _sanitize_filters(ai_parsed.get("hard_filters") or {})
    soft_filters = _sanitize_filters(ai_parsed.get("soft_filters") or {})

    sql_filters = {**hard_filters, **soft_filters}

    # map ugr -> ugr_value for SQLite numeric filtering
    if "ugr" in sql_filters:
        sql_filters["ugr_value"] = sql_filters.pop("ugr")

    if not PRODUCT_DB:
        return {"q": q, "error": "no sqlite", "sql_filters": sql_filters}

    rows = PRODUCT_DB.search_products(sql_filters, limit=5)
    return {
        "q": q,
        "sql_filters": sql_filters,
        "sqlite_sample_count": len(rows),
        "sqlite_sample_row": rows[:1],
    }


from fastapi import Query

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
