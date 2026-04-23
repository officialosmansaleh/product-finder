# -*- coding: utf-8 -*-
# app/main.py (SIMPLIFIED FILTER FLOW)
# - Single filter dict (no hard/soft duplication)
# - Local parser only (deterministic)
# - Always map to numeric DB columns for numeric comparisons
# - Product-DB-first search; DataFrame fallback only if DB unavailable

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request as FastAPIRequest, Depends
from typing import Any, Dict, List, Optional
import os
import sys
import math
import glob
import base64
import pandas as pd
import re
import html
import json
import time
import zipfile
from collections import OrderedDict, Counter
from urllib.parse import quote_plus, quote
from urllib.request import Request as UrlRequest, urlopen
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse, JSONResponse
from pydantic import BaseModel
from starlette.middleware.gzip import GZipMiddleware

from app.schema import (
    SearchRequest, ProductHit, SearchResponse,
    FacetsResponse, FacetValue,
    ALLOWED_FILTER_KEYS, HARD_FILTER_KEYS,
    CompareCodesRequest, CompareProductsRequest,
    IdealSpecAlternativesRequest, CompareSpecProductsRequest,
    CompareExportPdfRequest, AlternativesRequest,
    QuotePdfItem, QuotePdfRequest, QuoteDatasheetsZipRequest,
)
from app.scoring import score_product

from app.alternatives_logic import handle_alternatives, handle_alternatives_from_spec
from app.pim_loader import load_products
from app.local_parser import local_text_to_filters
from app.llm_intent import (
    llm_image_to_filters,
    llm_image_to_inference,
    llm_intent_to_filters,
    llm_intent_to_filters_with_meta,
)
from app.ranking import select_exact_and_similar
from app.runtime_config import cfg, cfg_bool, cfg_float, cfg_int, cfg_list
from app.auth import AuthService, UserPublic, build_auth_dependencies
from app.auth_router import create_auth_router
from app.compare_logic import (
    handle_compare_codes,
    handle_export_compare_pdf,
    handle_compare_products,
    handle_compare_spec_products,
)
from app.db_runtime import load_database_runtime_settings
from app.debug_router import create_debug_router
from app.facets_logic import handle_facets
from app.public_router import create_public_router
from app.quote_logic import handle_export_quote_datasheets_zip, handle_export_quote_pdf
from app.search_logic import handle_search
from app.security import (
    PUBLIC_FETCH_HOSTS,
    SecurityManager,
    looks_like_pdf,
    looks_like_supported_image,
    safe_open_url,
    setup_cors,
)
import logging
logger = logging.getLogger("uvicorn.error")

PRODUCT_NAME_FILTER_KEY = "product_name_short"
LEGACY_PRODUCT_NAME_FILTER_KEY = "name_prefix"

# Prevent Windows cp1252 console crashes on unicode log/print output.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Tender ranking: performance/design fields are soft preferences by default.
SOFT_PRIORITY_KEYS = {
    x for x in cfg_list("main.soft_priority_keys", [
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
    ])
}
DIMENSION_TOLERANCE = cfg_float("main.dimension_tolerance", 0.05)
DIMENSION_KEYS = {
    x for x in cfg_list("main.dimension_keys", [
        "diameter",
        "luminaire_height",
        "luminaire_width",
        "luminaire_length",
    ])
}

logger.info("LLM function loaded: %s", bool(llm_intent_to_filters))
logger.info("OPENAI_API_KEY present? %s", bool(os.getenv("OPENAI_API_KEY")))

# Try to import database, but don't crash if it fails
try:
    from app.database import ProductDatabase
    HAS_DATABASE = True
except ImportError as e:
    logger.warning("Database module import warning: %s", e)
    logger.warning("Product database features will be disabled")
    HAS_DATABASE = False
    ProductDatabase = None

security = SecurityManager()
db_runtime = load_database_runtime_settings()
auth_service = AuthService(
    db_path=db_runtime.auth_db_path,
    database_url=db_runtime.auth_database_url,
)
_get_current_user_dep, require_admin_dep, require_leadership_dep, require_staff_dep, _get_token_dep = build_auth_dependencies(auth_service)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    auth_service.init_db()
    skip_runtime_init = str(os.getenv("PF_SKIP_RUNTIME_INIT", "")).strip().lower() in {"1", "true", "yes", "on"}
    if skip_runtime_init:
        logger.warning("Skipping catalog runtime initialization because PF_SKIP_RUNTIME_INIT is enabled")
    else:
        initialize_runtime_state()
    try:
        yield
    finally:
        if not skip_runtime_init:
            close_runtime_state()


app = FastAPI(title="Product Finder MVP (Simplified)", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
setup_cors(app)

AUTH_EXEMPT_PATHS = {
    "/",
    "/health",
    "/openapi.json",
    "/search",
    "/facets",
    "/codes/suggest",
    "/preview-image",
    "/full-image",
}
AUTH_EXEMPT_PREFIXES = ("/auth", "/frontend", "/docs", "/redoc", "/debug")
APP_STARTED_AT = time.time()
REQUEST_LOG_SLOW_MS = cfg_int("main.request_log_slow_ms", 1500)
ACCESS_MATRIX = [
    {"path": "/", "method": "GET", "access": "public", "purpose": "Frontend home"},
    {"path": "/health", "method": "GET", "access": "public", "purpose": "Health check"},
    {"path": "/search", "method": "POST", "access": "public", "purpose": "Catalog search teaser with public limits"},
    {"path": "/facets", "method": "POST", "access": "public", "purpose": "Facet loading for search teaser"},
    {"path": "/codes/suggest", "method": "GET", "access": "public", "purpose": "Code suggestions"},
    {"path": "/preview-image", "method": "GET", "access": "public", "purpose": "Catalog previews with rate limiting"},
    {"path": "/full-image", "method": "GET", "access": "public", "purpose": "Full product images with rate limiting"},
    {"path": "/auth/*", "method": "POST/GET", "access": "public", "purpose": "Authentication and consent flows"},
    {"path": "/compare-products", "method": "POST", "access": "authenticated", "purpose": "Product comparison"},
    {"path": "/compare-spec-products", "method": "POST", "access": "authenticated", "purpose": "Specification comparison"},
    {"path": "/compare/export-pdf", "method": "POST", "access": "authenticated", "purpose": "Compare PDF export"},
    {"path": "/alternatives", "method": "POST", "access": "authenticated", "purpose": "Alternatives workflow"},
    {"path": "/alternatives-from-spec", "method": "POST", "access": "authenticated", "purpose": "Spec alternatives workflow"},
    {"path": "/quote/export-pdf", "method": "POST", "access": "authenticated", "purpose": "Quote PDF export"},
    {"path": "/quote/datasheets-zip", "method": "POST", "access": "authenticated", "purpose": "Datasheet ZIP export"},
    {"path": "/parse-pdf", "method": "POST", "access": "authenticated", "purpose": "Tender parsing"},
    {"path": "/parse-image", "method": "POST", "access": "authenticated", "purpose": "Image parsing"},
    {"path": "/admin/*", "method": "GET/POST/PUT/DELETE", "access": "manager/director/admin", "purpose": "Workspace and admin operations"},
    {"path": "/admin/catalog-release-diff", "method": "GET", "access": "director/admin", "purpose": "Latest catalog release diff summary"},
    {"path": "/admin/catalog-release-diff/export", "method": "GET", "access": "director/admin", "purpose": "Latest catalog release diff CSV export"},
    {"path": "/debug/*", "method": "GET/POST", "access": "admin/local-debug", "purpose": "Debug-only operations"},
    {"path": "/database/recreate", "method": "POST", "access": "admin/local-debug", "purpose": "Database rebuild"},
    {"path": "/database/refresh", "method": "POST", "access": "admin/local-debug", "purpose": "Database refresh"},
    {"path": "/database/stats", "method": "GET", "access": "authenticated", "purpose": "Database stats"},
]


def _get_optional_current_user(request: Optional[FastAPIRequest]) -> Optional[Dict[str, Any]]:
    if request is None:
        return None
    cached = getattr(getattr(request, "state", None), "current_user", None)
    if cached:
        return cached
    auth = str(request.headers.get("authorization") or "").strip()
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        token = str(request.cookies.get(auth_service.access_cookie_name) or "").strip()
    if not token:
        return None
    try:
        user = auth_service.decode_token(token)
    except HTTPException:
        return None
    try:
        request.state.current_user = user
    except Exception:
        pass
    return user


def _has_analytics_consent(request: Optional[FastAPIRequest]) -> bool:
    if request is None:
        return False
    try:
        return bool(auth_service.consent_from_request(request).get("analytics"))
    except Exception:
        return False


def _analytics_session_id(request: Optional[FastAPIRequest]) -> str:
    if request is None:
        return ""
    try:
        return auth_service.analytics_session_from_request(request)
    except Exception:
        return ""


def _record_analytics_event(
    request: Optional[FastAPIRequest],
    *,
    event_type: str,
    user: Optional[Dict[str, Any]] = None,
    page: str = "",
    path: str = "",
    product_code: str = "",
    query_text: str = "",
    filters: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if request is None or not _has_analytics_consent(request):
        return
    try:
        auth_service.record_activity_event(
            event_type=event_type,
            user_id=(int(user.id) if user is not None and getattr(user, "id", None) is not None else None),
            session_id=_analytics_session_id(request),
            page=page,
            path=path or str(request.url.path or ""),
            product_code=product_code,
            query_text=query_text,
            filters=filters,
            metadata=metadata,
            ip_address=str(getattr(getattr(request, "client", None), "host", "") or ""),
            user_agent=str(request.headers.get("user-agent") or ""),
        )
    except Exception:
        logger.exception("analytics event logging failed for %s", event_type)


@app.middleware("http")
async def require_authenticated_user(request: FastAPIRequest, call_next):
    path = str(request.url.path or "")
    if request.method.upper() == "OPTIONS":
        return await call_next(request)
    if path in AUTH_EXEMPT_PATHS or any(path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES):
        return await call_next(request)

    auth = str(request.headers.get("authorization") or "").strip()
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        token = str(request.cookies.get(auth_service.access_cookie_name) or "").strip()
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    try:
        request.state.current_user = auth_service.decode_token(token)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: FastAPIRequest, call_next):
    started = time.perf_counter()
    method = request.method.upper()
    path = str(request.url.path or "")
    client_host = str(getattr(getattr(request, "client", None), "host", "") or "-")
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        logger.exception(
            "request failed method=%s path=%s client=%s duration_ms=%s",
            method,
            path,
            client_host,
            elapsed_ms,
        )
        raise
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    status_code = getattr(response, "status_code", 0)
    level = logging.WARNING if elapsed_ms >= REQUEST_LOG_SLOW_MS or status_code >= 500 else logging.INFO
    logger.log(
        level,
        "request completed method=%s path=%s status=%s client=%s duration_ms=%s",
        method,
        path,
        status_code,
        client_host,
        elapsed_ms,
    )
    return response


@app.middleware("http")
async def add_frontend_asset_cache_headers(request: FastAPIRequest, call_next):
    response = await call_next(request)
    path = str(request.url.path or "")
    if response.status_code == 200 and path.startswith("/frontend/"):
        lower_path = path.lower()
        cacheable_suffixes = (".css", ".js", ".png", ".webp", ".svg", ".jpg", ".jpeg", ".ico")
        if lower_path.endswith(cacheable_suffixes):
            response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    return response

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
# Enable directory index resolution so /frontend/ serves frontend/index.html.
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


def clear_facets_cache_impl() -> dict[str, Any]:
    FACETS_CACHE.clear()
    return {"ok": True, "message": "facets cache cleared"}


def home_impl():
    resp = FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

def _resolve_pim_xlsx_path() -> str:
    env_path = str(os.getenv("PIM_XLSX", "")).strip()
    if env_path:
        return env_path

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    pim_candidates = glob.glob(os.path.join(base_dir, "PIM_*.xlsx"))
    if pim_candidates:
        # Prefer newest date encoded in filename (e.g. PIM_20260224.xlsx), fallback to lexical max.
        def _pim_sort_key(path: str):
            name = os.path.basename(path)
            m = re.search(r"PIM_(\d{8})\.xlsx$", name, flags=re.IGNORECASE)
            if m:
                return (1, m.group(1), name.lower())
            return (0, "", name.lower())
        return sorted(pim_candidates, key=_pim_sort_key, reverse=True)[0]

    return str(cfg("main.default_pim_xlsx", "data/ExportRO-2025-10-28_09.34.43.xlsx"))


def _resolve_family_map_path() -> str:
    env_path = str(os.getenv("FAMILY_MAP_XLSX", "")).strip()
    if env_path:
        return env_path
    return str(cfg("main.default_family_map_xlsx", "data/family_map.xlsx"))


XLSX_PATH = _resolve_pim_xlsx_path()
FAMILY_MAP_PATH = _resolve_family_map_path()
_pim_verbose_default = "1" if cfg_bool("main.pim_verbose_default", True) else "0"
_use_sqlite_default = "1" if cfg_bool("main.use_sqlite_default", True) else "0"
PIM_VERBOSE = os.getenv("PIM_VERBOSE", _pim_verbose_default).strip() not in ("0", "false", "False", "no", "NO")
USE_SQLITE = os.getenv("USE_SQLITE", _use_sqlite_default).strip() not in ("0", "false", "False", "no", "NO") and HAS_DATABASE
USE_PRODUCT_DB = HAS_DATABASE and (USE_SQLITE or db_runtime.product_postgres_requested)

DB: Optional[pd.DataFrame] = None
PRODUCT_DB: Optional[Any] = None
ALLOWED_FAMILIES: List[str] = []
ALLOWED_FAMILIES_NORM: set[str] = set()
IMAGE_CACHE: Dict[str, str] = {}
PIM_CODES_CACHE: Dict[str, Any] = {"path": "", "mtime": 0.0, "rows": []}

# ------------------------------------------------------------
# Facets cache (in-memory)
# Keyed by FILTERS (mapped to product DB)
# ------------------------------------------------------------
FACETS_CACHE = OrderedDict()   # key -> (timestamp, payload_dict)
FACETS_CACHE_MAX = cfg_int("main.facets_cache_max", 128)
FACETS_CACHE_TTL_SEC = cfg_int("main.facets_cache_ttl_sec", 180)  # 3 minutes
FACETS_CACHE_SCHEMA_VER = cfg_int("main.facets_cache_schema_ver", 4)

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

def _families_from_db_fallback(limit: int = 30):
    """
    Guaranteed fallback: return top families from product DB even if narrowed DF is missing product_family.
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
        print("⚠️ families db fallback failed:", e)
        return []



def _sanitize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (filters or {}).items():
        kk = PRODUCT_NAME_FILTER_KEY if k == LEGACY_PRODUCT_NAME_FILTER_KEY else k
        if kk not in ALLOWED_FILTER_KEYS:
            continue
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        out[kk] = v
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
    if LEGACY_PRODUCT_NAME_FILTER_KEY in out and PRODUCT_NAME_FILTER_KEY not in out:
        out[PRODUCT_NAME_FILTER_KEY] = out.get(LEGACY_PRODUCT_NAME_FILTER_KEY)
    out.pop(LEGACY_PRODUCT_NAME_FILTER_KEY, None)

    def has_op(s: str) -> bool:
        return any(s.startswith(op) for op in (">=", "<=", ">", "<", "="))

    def has_range(s: str) -> bool:
        return bool(re.match(r"^-?\d+(?:\.\d+)?\s*-\s*-?\d+(?:\.\d+)?$", str(s or "").strip().replace(",", ".")))

    def _as_list(v: Any) -> List[Any]:
        return v if isinstance(v, list) else [v]

    def _normalize_numeric_values(key: str, default_op: str) -> None:
        if key not in out:
            return
        vals = _as_list(out[key])
        norm_vals: List[str] = []
        for one in vals:
            v = str(one).strip().replace(" ", "")
            if not v:
                continue
            v = v.replace(",", ".")
            if has_range(v) or has_op(v):
                norm_vals.append(v)
                continue
            m = re.search(r"(-?\d+(?:\.\d+)?)", v)
            if m:
                norm_vals.append(f"{default_op}{m.group(1)}")
        if norm_vals:
            out[key] = norm_vals if isinstance(out[key], list) else norm_vals[0]

    def _norm_multivalue_text(key: str) -> None:
        if key not in out:
            return
        vals = [str(x).strip() for x in _as_list(out[key]) if str(x).strip()]
        if not vals:
            out.pop(key, None)
            return
        seen = set()
        uniq: List[str] = []
        for v in vals:
            k = v.lower()
            if k in seen:
                continue
            seen.add(k)
            uniq.append(v)
        out[key] = uniq if isinstance(out.get(key), list) else uniq[0]

    # IP fields (UI often sends plain values like "40.0") -> ">=IP40"
    for ip_key in ("ip_rating", "ip_visible", "ip_non_visible"):
        if ip_key in out:
            ip_vals = _as_list(out[ip_key])
            norm_vals = []
            for one in ip_vals:
                v = str(one).strip().upper().replace(" ", "").replace("IPX", "IP0")
                if not has_op(v):
                    m = re.search(r"(\d{2})", v)
                    if m:
                        norm_vals.append(f">=IP{m.group(1)}")
                else:
                    m = re.search(r"(>=|<=|>|<)\s*IP?(\d{2})", v)
                    if m:
                        norm_vals.append(f"{m.group(1)}IP{m.group(2)}")
            if norm_vals:
                out[ip_key] = norm_vals if isinstance(out[ip_key], list) else norm_vals[0]

    # IK ("IK5" / "IK05") -> ">=IK05"
    if "ik_rating" in out:
        ik_vals = _as_list(out["ik_rating"])
        norm_vals = []
        for one in ik_vals:
            v = str(one).strip().upper().replace(" ", "")
            if not has_op(v):
                m = re.search(r"(\d{1,2})", v)
                if m:
                    norm_vals.append(f">=IK{m.group(1).zfill(2)}")
            else:
                m = re.search(r"(>=|<=|>|<)\s*IK?(\d{1,2})", v)
                if m:
                    norm_vals.append(f"{m.group(1)}IK{m.group(2).zfill(2)}")
        if norm_vals:
            out["ik_rating"] = norm_vals if isinstance(out["ik_rating"], list) else norm_vals[0]

    # Multi-choice UI filters that must preserve list semantics.
    for multi_key in ("product_family", PRODUCT_NAME_FILTER_KEY, "cct_k", "interface"):
        _norm_multivalue_text(multi_key)

    # UGR migliorativo (più basso è meglio): "19" -> "<=19" ; "<19" -> "<=19"
    if "ugr" in out:
        vals: List[str] = []
        for one in _as_list(out["ugr"]):
            v = str(one).strip().replace(" ", "").replace(",", ".")
            if not v:
                continue
            if has_range(v):
                vals.append(v)
                continue
            if not has_op(v):
                m = re.search(r"(\d+(?:\.\d+)?)", v)
                if m:
                    vals.append(f"<={m.group(1)}")
            elif v.startswith("<") and not v.startswith("<="):
                vals.append("<=" + v[1:])
            else:
                vals.append(v)
        if vals:
            out["ugr"] = vals if isinstance(out["ugr"], list) else vals[0]

    # CRI migliorativo: "80" -> ">=80"
    if "cri" in out:
        vals: List[str] = []
        for one in _as_list(out["cri"]):
            v = str(one).strip().replace(" ", "").replace(",", ".")
            if not v:
                continue
            if has_range(v):
                vals.append(v)
                continue
            if not has_op(v):
                m = re.search(r"(\d+(?:\.\d+)?)", v)
                if m:
                    vals.append(f">={m.group(1)}")
            else:
                m = re.match(r"^(>=|<=|>|<|=)\s*(\d+(?:\.\d+)?)$", v)
                if m:
                    op = m.group(1)
                    if op == ">":
                        op = ">="
                    vals.append(f"{op}{m.group(2)}")
        if vals:
            out["cri"] = vals if isinstance(out["cri"], list) else vals[0]

    # Lumen output migliorativo: "3000" -> ">=3000"
    _normalize_numeric_values("lumen_output", ">=")

    # Efficacy migliorativa: "120" -> ">=120"
    _normalize_numeric_values("efficacy_lm_w", ">=")

    # Power max migliorativo (più basso è meglio): "40" -> "<=40"
    _normalize_numeric_values("power_max_w", "<=")

    # Ambient min capability: lower/colder values are better (default <=).
    if "ambient_temp_min_c" in out:
        vals: List[str] = []
        for one in _as_list(out["ambient_temp_min_c"]):
            v = str(one).strip().replace(" ", "").replace(",", ".")
            if not v:
                continue
            if has_range(v):
                vals.append(v)
                continue
            if not has_op(v):
                m = re.search(r"(-?\d+(?:\.\d+)?)", v)
                if m:
                    vals.append(f"<={m.group(1)}")
            else:
                m = re.match(r"^(>=|<=|>|<)(-?\d+(?:\.\d+)?)$", v)
                if m:
                    op, num = m.group(1), m.group(2)
                    if op == ">=":
                        vals.append(f"<={num}")
                    elif op == ">":
                        vals.append(f"<{num}")
                    else:
                        vals.append(f"{op}{num}")
        if vals:
            out["ambient_temp_min_c"] = vals if isinstance(out["ambient_temp_min_c"], list) else vals[0]

    # Ambient max capability (default <=).
    _normalize_numeric_values("ambient_temp_max_c", "<=")

    # Warranty anni: "5 yr" / "5" -> ">=5"
    _normalize_numeric_values("warranty_years", ">=")

    # Lifetime ore: "50000 hr" / "50000" -> ">=50000"
    _normalize_numeric_values("lifetime_hours", ">=")

    # LED rated life (h): default >=
    _normalize_numeric_values("led_rated_life_h", ">=")

    # Lumen maintenance % (Ta 25°): default >=
    _normalize_numeric_values("lumen_maintenance_pct", ">=")


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


def _compact_code(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _infer_interpreted(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    t = str(text or "")
    m = re.search(r"\b(\d{2,4})\s*(?:x|X|by|per)\s*(\d{2,4})\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a <= 300 and b <= 300:
            a, b = a * 10, b * 10
        lo, hi = min(a, b), max(a, b)
        out["size_mm"] = [lo, hi]
        out["size_label"] = f"{lo}x{hi} mm"
    return out


def _text_relevance(row: Dict[str, Any], text: str) -> float:
    q = str(text or "").strip().lower()
    if not q:
        return 0.0
    code = str(row.get("product_code") or "")
    short_code = str(row.get("short_product_code") or "")
    name = str(row.get("product_name") or "").lower()
    hay = " ".join([code.lower(), short_code.lower(), name])
    q_compact = _compact_code(q)
    code_compact = _compact_code(code)
    short_compact = _compact_code(short_code)
    score = 0.0

    if q_compact and (q_compact == code_compact or q_compact == short_compact):
        score += 1.0
    elif q_compact and (q_compact in code_compact or q_compact in short_compact):
        score += 0.75

    tokens = [x for x in re.split(r"\s+", q) if x]
    if tokens:
        token_hits = sum(1 for tok in tokens if tok in hay)
        score += min(0.6, 0.2 * token_hits)

    if q in name:
        score += cfg_float("main.similar_text_boost", 0.35)

    return max(0.0, min(1.5, score))


def _manufacturer_label(x: Any) -> str:
    s = str(x or "").strip()
    return s


def _build_website_url(product_code: str, manufacturer: str) -> str:
    code_q = quote_plus(str(product_code or "").strip())
    return f"https://www.disano.it/it/search/?q={code_q}"


def _build_datasheet_url(product_code: str, manufacturer: str) -> str:
    code = str(product_code or "").strip()
    return f"https://www.disano.it/download/mediafiles/-1_{quote_plus(code)}.pdf/EN_{quote_plus(code)}.pdf"


def _normalize_image_url(raw: str) -> Optional[str]:
    s = str(raw or "").strip().replace("&amp;", "&")
    if not s:
        return None
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = "https://www.disano.it" + s
    elif s.startswith("azprodmedia.blob.core.windows.net"):
        s = "https://" + s
    return s


def _to_disano_next_image(url: str) -> str:
    src = str(url or "").strip()
    if not src:
        return src
    if "www.disano.it/_next/image/?url=" in src:
        out = src
    else:
        enc = quote(src, safe="")
        out = f"https://www.disano.it/_next/image/?url={enc}&w=1920&q=75"
    out = out.replace("&amp;", "&")
    if "&w=" in out:
        out = re.sub(r"&w=\d+", "&w=1920", out)
    else:
        out += "&w=1920"
    if "&q=" in out:
        out = re.sub(r"&q=\d+", "&q=75", out)
    else:
        out += "&q=75"
    return out


def _extract_graphql_image_url(product_code: str) -> Optional[str]:
    code = str(product_code or "").strip()
    if not code:
        return None

    cache_key = f"gql:{code}"
    if cache_key in IMAGE_CACHE:
        return IMAGE_CACHE[cache_key]

    endpoint = "https://www.disano.it/apis/hcl/graphql/"
    # Official Disano GraphQL resolver by part number.
    query = (
        "query GET_PRODUCT_BY_PARTNUMBER($storeId: String!, $langId: String!, $partNumber: String!) { "
        "productViewFindProductByPartNumber(storeId: $storeId, langId: $langId, partNumber: $partNumber) { "
        "catalogEntryView { partNumber thumbnail fullImage } } }"
    )

    # Known working store IDs for Disano APIs.
    store_ids = [x.strip() for x in os.getenv("DISANO_STORE_IDS", str(cfg("main.disano_store_ids_default", "10051,10151"))).split(",") if x.strip()]
    lang_id = os.getenv("DISANO_LANG_ID", str(cfg("main.disano_lang_default", "-4")))

    for sid in store_ids:
        payload = {
            "operationName": "GET_PRODUCT_BY_PARTNUMBER",
            "variables": {"partNumber": code, "storeId": sid, "langId": lang_id},
            "query": query,
        }
        try:
            req = UrlRequest(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            with urlopen(req, timeout=cfg_int("main.http_timeout_gql_sec", 6)) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception:
            continue

        cev = ((data or {}).get("data") or {}).get("productViewFindProductByPartNumber") or {}
        rows = cev.get("catalogEntryView") or []
        if not rows:
            continue
        row0 = rows[0] or {}
        # Prefer full image when available so UI lightbox previews are less pixelated.
        img_raw = _normalize_image_url(row0.get("fullImage") or row0.get("thumbnail") or "")
        img = _to_disano_next_image(img_raw) if img_raw else None
        if img:
            IMAGE_CACHE[cache_key] = img
            return img

    return None


def _row_to_public_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(row or {})
    d.pop("id", None)
    d.pop("imported_at", None)
    return d


def _compact_for_match(s: Any) -> str:
    return re.sub(r"[^0-9a-z]", "", str(s or "").lower())


def _find_product_by_code_any(code: str) -> Optional[Dict[str, Any]]:
    c = str(code or "").strip()
    if not c:
        return None
    compact = _compact_for_match(c)

    # SQLite-first
    if PRODUCT_DB:
        try:
            if not PRODUCT_DB.conn:
                PRODUCT_DB.connect()
            q1 = "SELECT * FROM products WHERE LOWER(TRIM(product_code)) = LOWER(TRIM(?)) LIMIT 1"
            r = PRODUCT_DB.conn.execute(q1, (c,)).fetchone()
            if r:
                return _row_to_public_dict(dict(r))

            q2 = (
                "SELECT * FROM products "
                "WHERE LOWER(REPLACE(REPLACE(REPLACE(TRIM(product_code),'-',''),' ',''),'.','')) = ? "
                "LIMIT 1"
            )
            r = PRODUCT_DB.conn.execute(q2, (compact,)).fetchone()
            if r:
                return _row_to_public_dict(dict(r))
        except Exception:
            pass

    # DataFrame fallback
    if DB is None or DB.empty or "product_code" not in DB.columns:
        return None
    tmp = DB.copy()
    tmp["_code"] = tmp["product_code"].astype(str).str.strip()
    m = tmp[tmp["_code"].str.lower() == c.lower()]
    if m.empty:
        m = tmp[tmp["_code"].apply(_compact_for_match) == compact]
    if m.empty:
        return None
    return _row_to_public_dict(m.iloc[0].to_dict())


def _search_rows_by_text_sqlite(text: str, limit: int = 3000) -> List[Dict[str, Any]]:
    if not PRODUCT_DB:
        return []
    try:
        if not PRODUCT_DB.conn:
            PRODUCT_DB.connect()
    except Exception:
        return []

    q = str(text or "").strip()
    if not q:
        return []
    q_l = q.lower()
    q_compact = _compact_for_match(q)
    if not q_compact:
        return []

    sql = """
        SELECT *
        FROM products
        WHERE
            LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(product_code,'')),'-',''),' ',''),'.','')) = ?
            OR LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(short_product_code,'')),'-',''),' ',''),'.','')) = ?
            OR LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(product_code,'')),'-',''),' ',''),'.','')) LIKE ?
            OR LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(short_product_code,'')),'-',''),' ',''),'.','')) LIKE ?
            OR LOWER(COALESCE(product_name,'')) LIKE ?
        ORDER BY
            CASE
                WHEN LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(product_code,'')),'-',''),' ',''),'.','')) = ? THEN 0
                WHEN LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(short_product_code,'')),'-',''),' ',''),'.','')) = ? THEN 1
                WHEN LOWER(COALESCE(product_name,'')) = ? THEN 2
                WHEN LOWER(COALESCE(product_name,'')) LIKE ? THEN 3
                ELSE 4
            END,
            product_code
        LIMIT ?
    """
    params = (
        q_compact,
        q_compact,
        f"%{q_compact}%",
        f"%{q_compact}%",
        f"%{q_l}%",
        q_compact,
        q_compact,
        q_l,
        f"{q_l}%",
        int(limit),
    )
    try:
        rows = PRODUCT_DB.conn.execute(sql, params).fetchall()
        return [_row_to_public_dict(dict(r)) for r in rows]
    except Exception:
        return []


def _norm_header_name(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _choose_first_column(columns: List[str], wanted: List[str]) -> Optional[str]:
    if not columns:
        return None
    norm_map = {_norm_header_name(c): c for c in columns}
    for w in wanted:
        n = _norm_header_name(w)
        if n in norm_map:
            return norm_map[n]
    for c in columns:
        nc = _norm_header_name(c)
        if any(_norm_header_name(w) in nc for w in wanted):
            return c
    return None


def _load_all_pim_codes_index() -> List[Dict[str, str]]:
    global PIM_CODES_CACHE
    path = str(XLSX_PATH or "").strip()
    if not path or not os.path.exists(path):
        return []
    try:
        mtime = float(os.path.getmtime(path))
    except Exception:
        mtime = 0.0
    if (
        str(PIM_CODES_CACHE.get("path") or "") == path
        and float(PIM_CODES_CACHE.get("mtime") or 0.0) == mtime
        and isinstance(PIM_CODES_CACHE.get("rows"), list)
    ):
        return list(PIM_CODES_CACHE.get("rows") or [])

    rows_out: List[Dict[str, str]] = []
    try:
        raw = pd.read_excel(path, engine="openpyxl")
        raw.columns = [str(c).strip() for c in raw.columns]
        cols = list(raw.columns)
        code_col = _choose_first_column(cols, ["Order code", "product_code", "product code", "code"])
        name_col = _choose_first_column(cols, ["Product name", "<Name>", "name"])
        mfr_col = _choose_first_column(cols, ["Manufacturer", "Brand"])
        if code_col:
            code_s = raw[code_col].astype(str).str.strip()
            name_s = raw[name_col].astype(str).str.strip() if name_col else pd.Series([""] * len(raw), index=raw.index)
            mfr_s = raw[mfr_col].astype(str).str.strip() if mfr_col else pd.Series([""] * len(raw), index=raw.index)
            for i in range(len(raw)):
                code = str(code_s.iat[i] if i < len(code_s) else "").strip()
                if not code or code.lower() == "nan":
                    continue
                name = str(name_s.iat[i] if i < len(name_s) else "").strip()
                mfr = str(mfr_s.iat[i] if i < len(mfr_s) else "").strip()
                rows_out.append(
                    {
                        "product_code": code,
                        "product_name": "" if name.lower() == "nan" else name,
                        "manufacturer": "" if mfr.lower() == "nan" else mfr,
                    }
                )
    except Exception:
        rows_out = []

    dedup: List[Dict[str, str]] = []
    seen: set[str] = set()
    for r in rows_out:
        code = str(r.get("product_code") or "").strip()
        if not code:
            continue
        key = code.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)

    dedup.sort(key=lambda x: str(x.get("product_code") or ""))
    PIM_CODES_CACHE = {"path": path, "mtime": mtime, "rows": dedup}
    return list(dedup)


def _suggest_product_codes(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    lim = max(1, min(int(limit or 25), 100))
    q = str(query or "").strip()
    q_l = q.lower()
    q_compact = _compact_for_match(q)
    out: List[Dict[str, Any]] = []

    # SQLite-first
    if PRODUCT_DB:
        try:
            if not PRODUCT_DB.conn:
                PRODUCT_DB.connect()
            if q:
                sql = """
                    SELECT product_code, product_name, manufacturer
                    FROM products
                    WHERE TRIM(COALESCE(product_code,'')) <> ''
                      AND (
                        LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(product_code,'')),'-',''),' ',''),'.','')) = ?
                        OR LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(short_product_code,'')),'-',''),' ',''),'.','')) = ?
                        OR LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(product_code,'')),'-',''),' ',''),'.','')) LIKE ?
                        OR LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(short_product_code,'')),'-',''),' ',''),'.','')) LIKE ?
                        OR LOWER(COALESCE(product_name,'')) LIKE ?
                      )
                    ORDER BY
                      CASE
                        WHEN LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(product_code,'')),'-',''),' ',''),'.','')) = ? THEN 0
                        WHEN LOWER(REPLACE(REPLACE(REPLACE(TRIM(COALESCE(short_product_code,'')),'-',''),' ',''),'.','')) = ? THEN 1
                        WHEN LOWER(COALESCE(product_code,'')) LIKE ? THEN 2
                        WHEN LOWER(COALESCE(product_name,'')) LIKE ? THEN 3
                        ELSE 4
                      END,
                      product_code
                    LIMIT ?
                """
                params = (
                    q_compact,
                    q_compact,
                    f"{q_compact}%",
                    f"{q_compact}%",
                    f"%{q_l}%",
                    q_compact,
                    q_compact,
                    f"{q_l}%",
                    f"{q_l}%",
                    lim,
                )
            else:
                sql = """
                    SELECT product_code, product_name, manufacturer
                    FROM products
                    WHERE TRIM(COALESCE(product_code,'')) <> ''
                    ORDER BY product_code
                    LIMIT ?
                """
                params = (lim,)
            rows = PRODUCT_DB.conn.execute(sql, params).fetchall()
            out = [dict(r) for r in rows]
        except Exception:
            out = []

    # DataFrame fallback
    if not out and DB is not None and not DB.empty and "product_code" in DB.columns:
        tmp = DB.copy()
        tmp["_code"] = tmp["product_code"].astype(str).str.strip()
        tmp = tmp[tmp["_code"] != ""]
        if q:
            tmp["_code_compact"] = tmp["_code"].apply(_compact_for_match)
            short_col = tmp["short_product_code"].astype(str).str.strip() if "short_product_code" in tmp.columns else ""
            if isinstance(short_col, str):
                tmp["_short_compact"] = ""
            else:
                tmp["_short_compact"] = short_col.apply(_compact_for_match)
            name_col = tmp["product_name"].astype(str) if "product_name" in tmp.columns else ""
            if isinstance(name_col, str):
                name_mask = False
            else:
                name_mask = name_col.str.lower().str.contains(re.escape(q_l), regex=True, na=False)
            mask = (
                (tmp["_code_compact"] == q_compact)
                | (tmp["_short_compact"] == q_compact)
                | (tmp["_code_compact"].str.startswith(q_compact, na=False))
                | (tmp["_short_compact"].str.startswith(q_compact, na=False))
                | name_mask
            )
            tmp = tmp[mask]
        tmp = tmp.sort_values(by=["_code"]).head(lim)
        out = [
            {
                "product_code": str(r.get("product_code") or "").strip(),
                "product_name": str(r.get("product_name") or "").strip(),
                "manufacturer": str(r.get("manufacturer") or "").strip(),
            }
            for r in tmp.to_dict(orient="records")
        ]

    # Include original PIM code list too (contains accessory/control gear rows
    # that are excluded from the main searchable dataset).
    pim_all = _load_all_pim_codes_index()
    if pim_all:
        if q:
            merged_pim: List[Dict[str, Any]] = []
            for r in pim_all:
                code = str(r.get("product_code") or "").strip()
                if not code:
                    continue
                c_comp = _compact_for_match(code)
                name_l = str(r.get("product_name") or "").lower()
                if (
                    c_comp == q_compact
                    or c_comp.startswith(q_compact)
                    or (q_l and q_l in name_l)
                ):
                    merged_pim.append(r)
            out.extend(merged_pim[: lim * 2])
        else:
            out.extend(pim_all[: lim * 2])

    # Dedupe and normalize
    dedup: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for r in out:
        code = str(r.get("product_code") or "").strip()
        if not code:
            continue
        key = code.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(
            {
                "product_code": code,
                "product_name": str(r.get("product_name") or "").strip(),
                "manufacturer": str(r.get("manufacturer") or "").strip(),
            }
        )
    return dedup[:lim]


def _dedupe_rows_by_product_code(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        code = str(r.get("product_code") or "").strip().lower()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(r)
    return out


def _to_num(x: Any) -> Optional[float]:
    m = re.search(r"-?\d+(?:\.\d+)?", str(x or "").replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _alt_similarity(base: Dict[str, Any], cand: Dict[str, Any]) -> float:
    num_defaults = {
        "ip_rating": 1.2,
        "ik_rating": 1.2,
        "power_max_w": 1.8,
        "lumen_output": 2.0,
        "efficacy_lm_w": 0.8,
        "cct_k": 0.9,
        "cri": 0.9,
        "ugr": 0.8,
        "beam_angle_deg": 0.8,
        "warranty_years": 0.6,
        "lumen_maintenance_pct": 0.7,
        "failure_rate_pct": 0.5,
        "diameter": 1.0,
        "luminaire_length": 1.0,
        "luminaire_width": 1.0,
        "luminaire_height": 0.8,
    }
    str_defaults = {
        "product_family": 1.4,
        "manufacturer": 1.1,
        "control_protocol": 1.3,
        "emergency_present": 0.8,
        "housing_color": 0.7,
    }
    num_fields = [(k, cfg_float(f"main.alt.num_weight.{k}", v)) for k, v in num_defaults.items()]
    str_fields = [(k, cfg_float(f"main.alt.str_weight.{k}", v)) for k, v in str_defaults.items()]

    def _num_from_any_keys(row: Dict[str, Any], keys: List[str]) -> Optional[float]:
        for k in keys:
            v = _to_num(row.get(k))
            if v is not None:
                return v
        return None

    def _norm_text(v: Any) -> str:
        return str(v or "").strip().lower()

    def _norm_ctrl(v: Any) -> str:
        s = _norm_text(v)
        if not s:
            return ""
        if "dali" in s:
            return "dali"
        if "power switch" in s:
            return "power_switch"
        if s in {"yes", "si", "sì"} or s.startswith("yes"):
            return "yes"
        if s in {"no", "none"}:
            return "no"
        return s

    score = 0.0
    wsum = 0.0
    major_penalty = 1.0
    family_state = "none"  # one of: none, match, mismatch, missing

    for f, w in num_fields:
        a = _to_num(base.get(f))
        b = _to_num(cand.get(f))
        if a is None and b is None:
            continue
        wsum += w
        if a is None or b is None:
            continue
        denom = max(abs(a), abs(b), 1.0)
        closeness = max(0.0, 1.0 - (abs(a - b) / denom))
        if f in {"power_max_w", "lumen_output"}:
            closeness = closeness ** 1.4
            ratio = min(abs(a), abs(b)) / max(abs(a), abs(b), 1.0)
            if ratio < cfg_float("main.alt.ratio_low_threshold", 0.70):
                major_penalty *= cfg_float("main.alt.ratio_low_penalty", 0.80)
            elif ratio < cfg_float("main.alt.ratio_mid_threshold", 0.85):
                major_penalty *= cfg_float("main.alt.ratio_mid_penalty", 0.90)
        score += closeness * w

    # Lifetime is important for replacement alternatives; use a fallback between common columns.
    life_a = _num_from_any_keys(base, ["led_rated_life_h", "lifetime_hours"])
    life_b = _num_from_any_keys(cand, ["led_rated_life_h", "lifetime_hours"])
    life_w = cfg_float("main.alt.life_weight", 1.6)
    if life_a is not None or life_b is not None:
        wsum += life_w
        if life_a is not None and life_b is not None:
            life_ratio = min(abs(life_a), abs(life_b)) / max(abs(life_a), abs(life_b), 1.0)
            life_closeness = life_ratio ** 1.2
            score += life_closeness * life_w
            if life_ratio < cfg_float("main.alt.life_ratio_threshold", 0.75):
                major_penalty *= cfg_float("main.alt.life_ratio_penalty", 0.90)

    control_mismatch = False
    for f, w in str_fields:
        a_raw = base.get(f)
        b_raw = cand.get(f)
        a = _norm_ctrl(a_raw) if f == "control_protocol" else _norm_text(a_raw)
        b = _norm_ctrl(b_raw) if f == "control_protocol" else _norm_text(b_raw)
        if f == "product_family":
            if a and b:
                family_state = "match" if a == b else "mismatch"
            elif a or b:
                family_state = "missing"
        if not a and not b:
            continue
        wsum += w
        if not a or not b:
            if f == "control_protocol" and (a or b):
                control_mismatch = True
            continue
        if f == "control_protocol":
            v = 1.0 if a == b else 0.0
            if v == 0.0:
                control_mismatch = True
        else:
            v = 1.0 if a == b else (cfg_float("main.similar_text_boost", 0.35) if (a in b or b in a) else 0.0)
        score += v * w

    if control_mismatch:
        major_penalty *= cfg_float("main.alt.control_mismatch_penalty", 0.85)
    if family_state == "mismatch":
        major_penalty *= cfg_float("main.alt.family_mismatch_penalty", 0.45)
    elif family_state == "missing":
        major_penalty *= cfg_float("main.alt.family_missing_penalty", 0.75)

    if wsum <= 0:
        return 0.0
    final_score = (score / wsum) * major_penalty

    # Never return 100% unless key comparison fields are truly identical.
    # This avoids "100%" when, for example, housing_color differs.
    compare_keys = [
        "product_family", "manufacturer", "control_protocol", "emergency_present", "housing_color",
        "ip_rating", "ik_rating", "power_max_w", "lumen_output", "efficacy_lm_w", "cct_k", "cri", "ugr",
        "beam_angle_deg", "warranty_years", "lumen_maintenance_pct", "failure_rate_pct",
        "diameter", "luminaire_length", "luminaire_width", "luminaire_height",
    ]
    has_key_difference = False
    for k in compare_keys:
        a_raw = base.get(k)
        b_raw = cand.get(k)
        a_num = _to_num(a_raw)
        b_num = _to_num(b_raw)
        if a_num is not None or b_num is not None:
            if a_num is None or b_num is None or abs(a_num - b_num) > 1e-9:
                has_key_difference = True
                break
            continue
        a_txt = _norm_ctrl(a_raw) if k == "control_protocol" else _norm_text(a_raw)
        b_txt = _norm_ctrl(b_raw) if k == "control_protocol" else _norm_text(b_raw)
        if a_txt != b_txt:
            has_key_difference = True
            break

    final_score = max(0.0, min(1.0, final_score))
    final_cap = cfg_float("main.alt.max_score_with_diff", 0.999)
    if has_key_difference and final_score >= final_cap:
        final_score = final_cap
    return final_score


def _extract_first_site_image_url(website_url: str, product_code: str = "") -> Optional[str]:
    # Primary: official GraphQL by partNumber.
    gql_img = _extract_graphql_image_url(product_code)
    if gql_img:
        return gql_img

    # Fallback: legacy HTML scraping.
    u = str(website_url or "").strip()
    if not u:
        return None
    if u in IMAGE_CACHE:
        return IMAGE_CACHE[u]
    try:
        with safe_open_url(
            u,
            timeout=cfg_int("main.http_timeout_image_extract_sec", 4),
            allowed_hosts=PUBLIC_FETCH_HOSTS,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    # Exact "morning" behavior requested:
    # take first page image with fixed prefix and use it in results.
    # Example expected:
    # https://www.disano.it/_next/image/?url=https%3A%2F%2Fazprodmedia.blob.core.windows.net%2Fmediafiles%2Fthumb_...&w=1920&q=75
    m = re.search(
        r"(?:https://www\.disano\.it)?/_next/image/\?url=https%3A%2F%2Fazprodmedia\.blob\.core\.windows\.net%2Fmediafiles%2F[^\"'\\s]+",
        html_text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    img = m.group(0)
    img = img.replace("&amp;", "&")
    if not img.startswith("http"):
        img = f"https://www.disano.it{img}"

    # Force stable rendering params
    if "&w=" in img:
        img = re.sub(r"&w=\d+", "&w=1920", img)
    else:
        img += "&w=1920"
    if "&q=" in img:
        img = re.sub(r"&q=\d+", "&q=75", img)
    else:
        img += "&q=75"

    IMAGE_CACHE[u] = img
    return img

def _top_values(df: pd.DataFrame, col: str, limit: int = 30) -> List[FacetValue]:
    if df is None or df.empty or col not in df.columns:
        return []
    s = df[col].dropna().apply(_normalize_facet_text)
    s = s[s != ""]
    if s.empty:
        return []
    counts = s.value_counts()

    if col in ("ip_rating", "ip_visible", "ip_non_visible", "ik_rating", "cct_k"):
        items = [(k, int(v)) for k, v in counts.items()]
        items.sort(key=lambda kv: (_extract_int(str(kv[0])) is None, _extract_int(str(kv[0])) or 10**9))
        items = items[:limit]
    else:
        items = [(k, int(v)) for k, v in counts.head(limit).items()]

    return [{"value": _truncate(str(k), 80), "count": int(v), "raw": str(k)} for k, v in items]

def _top_product_name_short_values(df: pd.DataFrame, limit: int = 30) -> List[FacetValue]:
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

def _product_name_short_from_db_fallback(limit: int = 30) -> List[FacetValue]:
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

def _top_values_from_db_fallback(col: str, limit: int = 30) -> List[FacetValue]:
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

def _product_name_short_from_rows(rows: List[Dict[str, Any]], limit: int = 30) -> List[FacetValue]:
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

def _min_max_numeric(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    if df is None or df.empty or col not in df.columns:
        return {"min": None, "max": None}
    nums = pd.to_numeric(df[col].astype(str).str.extract(r"(-?\d+(?:\.\d+)?)")[0], errors="coerce").dropna()
    if nums.empty:
        return {"min": None, "max": None}
    return {"min": float(nums.min()), "max": float(nums.max())}

def _seed_filters_for_facets(filters: Dict[str, Any]) -> Dict[str, Any]:
    # Keep only broad filters for resilient facet population when strict filters over-constrain.
    if not filters:
        return {}
    seed_keys = {"product_family", "shape", "manufacturer", PRODUCT_NAME_FILTER_KEY}
    out: Dict[str, Any] = {}
    for k, v in (filters or {}).items():
        if k not in seed_keys:
            continue
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if isinstance(v, list) and len(v) == 0:
            continue
        out[k] = v
    return out

def _num_from_text_series(s: pd.Series) -> pd.Series:
    extracted = s.astype(str).str.extract(r"(-?\d+(?:\.\d+)?)")[0]
    return pd.to_numeric(extracted, errors="coerce")

def _df_filtered_subset(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    if df is None or df.empty or not filters:
        return df.copy() if df is not None else pd.DataFrame()

    out = df.copy()

    def _apply_numeric(col: str, expr: Any):
        nonlocal out
        source_col = col
        if col == "ugr" and "ugr_value" in out.columns:
            source_col = "ugr_value"
        elif col not in out.columns:
            return
        default_op = "<=" if col in {"ugr", "ambient_temp_min_c", "ambient_temp_max_c"} else ">="
        rel_tol = DIMENSION_TOLERANCE if col in DIMENSION_KEYS else 0.0
        values = expr if isinstance(expr, list) else [expr]
        got = out[source_col].astype(str).str.extract(r"(-?\d+(?:\.\d+)?)")[0]
        got_num = pd.to_numeric(got, errors="coerce")
        masks = []
        for one in values:
            s = str(one).strip().replace(" ", "")
            m = re.match(r"^(>=|<=|>|<)(-?\d+(?:\.\d+)?)$", s)
            if m:
                op, num = m.group(1), float(m.group(2))
                tol = abs(num) * rel_tol
                if op == ">=": masks.append(got_num >= (num - tol))
                elif op == ">": masks.append(got_num > (num - tol))
                elif op == "<=": masks.append(got_num <= (num + tol))
                elif op == "<": masks.append(got_num < (num + tol))
            else:
                try:
                    num = float(re.search(r"-?\d+(?:\.\d+)?", s).group())
                    tol = abs(num) * rel_tol
                    if default_op == "<=":
                        masks.append(got_num <= (num + tol))
                    else:
                        masks.append(got_num >= (num - tol))
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

    def _apply_product_name_short(val: Any):
        nonlocal out
        if "product_name" not in out.columns:
            return
        values = val if isinstance(val, list) else [val]
        product_name_short = (
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
            masks.append(product_name_short == str(one).strip().lower())
        if masks:
            m0 = masks[0]
            for mm in masks[1:]:
                m0 = m0 | mm
            out = out[m0]

    def _apply_product_name_contains(val: Any):
        nonlocal out
        if "product_name" not in out.columns:
            return
        values = val if isinstance(val, list) else [val]
        masks = []
        for one in values:
            masks.append(out["product_name"].astype(str).str.lower().str.contains(re.escape(str(one).strip().lower()), na=False))
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
    if "ip_visible" in filters:
        _apply_ip_ik("ip_visible", filters["ip_visible"], "IP")
    if "ip_non_visible" in filters:
        _apply_ip_ik("ip_non_visible", filters["ip_non_visible"], "IP")

    if "ik_rating" in filters:
        _apply_ip_ik("ik_rating", filters["ik_rating"], "IK")


    for col in [
        "ip_rating", "ip_visible", "ip_non_visible", "ik_rating", "power_max_w", "power_min_w", "lumen_output",
        "efficacy_lm_w", "cri", "ugr", "beam_angle_deg", "diameter",
        "luminaire_height", "luminaire_width", "luminaire_length",
        "warranty_years", "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct",
        "ambient_temp_min_c", "ambient_temp_max_c",
    ]:
        if col in filters:
            if col == "ugr":
                v = str(filters[col]).strip()
                if v.startswith("<") and not v.startswith("<="):
                    filters[col] = "<=" + v[1:]
            _apply_numeric(col, filters[col])

    for col in ["control_protocol", "interface", "emergency_present", "mounting_type", "shape", "housing_material", "housing_color", "product_family", "manufacturer"]:
        if col in filters:
            _apply_contains(col, filters[col])
    if PRODUCT_NAME_FILTER_KEY in filters:
        _apply_product_name_short(filters[PRODUCT_NAME_FILTER_KEY])
    if "product_name_contains" in filters:
        _apply_product_name_contains(filters["product_name_contains"])

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

    # CRI: treat strict ">" as ">=" in search normalization.
    if "cri" in sql:
        vals = sql["cri"] if isinstance(sql["cri"], list) else [sql["cri"]]
        norm_vals = []
        for one in vals:
            s = str(one).strip().replace(" ", "").replace(",", ".")
            m = re.match(r"^(>=|<=|>|<|=)?(\d+(?:\.\d+)?)$", s)
            if not m:
                norm_vals.append(one)
                continue
            op = m.group(1) or ">="
            if op == ">":
                op = ">="
            norm_vals.append(f"{op}{m.group(2)}")
        sql["cri"] = norm_vals if isinstance(sql["cri"], list) else norm_vals[0]

    # Ambient min capability: colder/lower values satisfy requirement.
    # Normalize to <= semantics so requirement -25C also includes -30C products.
    if "ambient_temp_min_c" in sql:
        vals = sql["ambient_temp_min_c"] if isinstance(sql["ambient_temp_min_c"], list) else [sql["ambient_temp_min_c"]]
        norm_vals = []
        for one in vals:
            s = str(one).strip().replace(" ", "").replace(",", ".")
            m = re.match(r"^(>=|<=|>|<|=)?(-?\d+(?:\.\d+)?)$", s)
            if not m:
                norm_vals.append(one)
                continue
            op = m.group(1) or "<="
            num = m.group(2)
            if op == ">=":
                op = "<="
            elif op == ">":
                op = "<"
            norm_vals.append(f"{op}{num}")
        sql["ambient_temp_min_c"] = norm_vals if isinstance(sql["ambient_temp_min_c"], list) else norm_vals[0]

    return sql

# ------------------------------------------------------------
# Lifecycle
# ------------------------------------------------------------

def initialize_runtime_state() -> None:
    global DB, PRODUCT_DB, ALLOWED_FAMILIES, ALLOWED_FAMILIES_NORM
    global XLSX_PATH, FAMILY_MAP_PATH
    XLSX_PATH = _resolve_pim_xlsx_path()
    print("🚀 Starting Product Finder (Simplified)...")
    print(f"📄 Using PIM XLSX: {XLSX_PATH}")

    try:
        DB = load_products(XLSX_PATH, family_map_path=FAMILY_MAP_PATH, verbose=PIM_VERBOSE)
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

    if USE_PRODUCT_DB and HAS_DATABASE:
        try:
            PRODUCT_DB = ProductDatabase(
                db_path=db_runtime.product_db_path,
                database_url=db_runtime.product_database_url,
            )
            PRODUCT_DB.connect()
            try:
                columns = PRODUCT_DB._table_columns("products")
            except Exception:
                columns = []
            print(f"DB backend={PRODUCT_DB.backend} path={PRODUCT_DB.db_path} postgres_requested={db_runtime.product_postgres_requested}")
            print(f"📋 Existing DB columns: {columns}")

            if columns and 'product_family' not in columns:
                print("⚠️ 'product_family' missing in DB. Recreating database...")
                PRODUCT_DB.close()
                PRODUCT_DB.connect()
                count = PRODUCT_DB.recreate_database(XLSX_PATH, FAMILY_MAP_PATH)
            else:
                count = PRODUCT_DB.init_db(XLSX_PATH, FAMILY_MAP_PATH)
            if PRODUCT_DB:
                try:
                    sample = PRODUCT_DB.debug_sample(1)
                    print("DB SAMPLE KEYS:", list(sample[0].keys()) if sample else "no rows")
                    print("DB SAMPLE ROW:", sample[0] if sample else "no rows")
                except Exception as e:
                    print("DB SAMPLE ERROR:", e)

            db_backend = getattr(PRODUCT_DB, "backend", db_runtime.product_db_backend)
            print(f"Database ready ({db_backend}): {count} products loaded")
        except Exception as e:
            print(f"Product database initialization failed: {e}")
            PRODUCT_DB = None
    else:
        print("ℹ️  Product database is disabled or not available")

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

def initialize_runtime_state() -> None:
    global DB, PRODUCT_DB, ALLOWED_FAMILIES, ALLOWED_FAMILIES_NORM
    global XLSX_PATH, FAMILY_MAP_PATH
    XLSX_PATH = _resolve_pim_xlsx_path()
    FAMILY_MAP_PATH = _resolve_family_map_path()
    logger.info("Starting Product Finder")
    logger.info("Using PIM XLSX: %s", XLSX_PATH)
    logger.info("Using family map XLSX: %s", FAMILY_MAP_PATH)

    try:
        DB = load_products(XLSX_PATH, family_map_path=FAMILY_MAP_PATH, verbose=PIM_VERBOSE)
        logger.info("Loaded %s products into DataFrame", len(DB))
        if "product_family" in DB.columns:
            families = DB["product_family"].dropna().unique()
            logger.info("Found %s unique families in DataFrame", len(families))
            logger.info("DataFrame family sample: %s", list(families)[:10])
        else:
            logger.warning("'product_family' not found in DataFrame")
    except Exception as e:
        logger.exception("Failed to load DataFrame: %s", e)
        DB = pd.DataFrame()

    if USE_PRODUCT_DB and HAS_DATABASE:
        try:
            PRODUCT_DB = ProductDatabase(
                db_path=db_runtime.product_db_path,
                database_url=db_runtime.product_database_url,
                backend=db_runtime.product_db_backend,
            )
            PRODUCT_DB.connect()
            preloaded_df = None if DB.empty else DB
            try:
                columns = PRODUCT_DB._table_columns("products")
            except Exception:
                columns = []
            logger.info(
                "Product DB connection backend=%s path=%s postgres_requested=%s",
                PRODUCT_DB.backend,
                PRODUCT_DB.db_path,
                db_runtime.product_postgres_requested,
            )
            logger.info("Existing product DB columns: %s", columns)

            if columns and "product_family" not in columns:
                logger.warning("'product_family' missing in DB. Recreating database")
                PRODUCT_DB.close()
                PRODUCT_DB.connect()
                count = PRODUCT_DB.recreate_database(XLSX_PATH, FAMILY_MAP_PATH, df=preloaded_df)
            else:
                count = PRODUCT_DB.init_db(XLSX_PATH, FAMILY_MAP_PATH, df=preloaded_df)
            if PRODUCT_DB:
                try:
                    sample = PRODUCT_DB.debug_sample(1)
                    logger.info("Product DB sample keys: %s", list(sample[0].keys()) if sample else "no rows")
                    logger.info("Product DB sample row available: %s", bool(sample))
                except Exception as e:
                    logger.warning("Product DB sample inspection failed: %s", e)

            db_backend = getattr(PRODUCT_DB, "backend", db_runtime.product_db_backend)
            logger.info("Product database ready backend=%s loaded_products=%s", db_backend, count)
        except Exception as e:
            logger.exception("Product database initialization failed: %s", e)
            PRODUCT_DB = None
    else:
        logger.info("Product database is disabled or not available")

    logger.info("Startup complete")
    if PRODUCT_DB:
        try:
            ALLOWED_FAMILIES = PRODUCT_DB.get_distinct_families()
            ALLOWED_FAMILIES_NORM = {str(f).strip().lower() for f in ALLOWED_FAMILIES if str(f).strip()}
            logger.info("Loaded %s distinct families from DB", len(ALLOWED_FAMILIES))
            if len(ALLOWED_FAMILIES) == 0:
                logger.warning("No families found in database")
                sample = PRODUCT_DB.debug_sample(5)
                for i, row in enumerate(sample):
                    logger.warning("Family sample %s: %s", i + 1, row.get("product_family", "MISSING"))
        except Exception as e:
            logger.warning("Failed to load families: %s", e)
            ALLOWED_FAMILIES = []
            ALLOWED_FAMILIES_NORM = set()
    else:
        ALLOWED_FAMILIES = []
        ALLOWED_FAMILIES_NORM = set()

# In main.py, aggiungi:

def recreate_database_impl():
    """Force full recreation of the configured product database."""
    global XLSX_PATH, FAMILY_MAP_PATH
    XLSX_PATH = _resolve_pim_xlsx_path()
    FAMILY_MAP_PATH = _resolve_family_map_path()
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="Product database not available")
    try:
        count = PRODUCT_DB.recreate_database(XLSX_PATH, FAMILY_MAP_PATH)
        initialize_runtime_state()
        return {
            "success": True, 
            "message": f"Database recreated with {count} products", 
            "count": count,
            "xlsx_path": XLSX_PATH,
            "db_path": getattr(PRODUCT_DB, "db_path", None),
            "release_diff": PRODUCT_DB.get_latest_release_diff() if PRODUCT_DB else {},
            "catalog_health": catalog_health_impl(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recreation failed: {str(e)}")

def close_runtime_state() -> None:
    global PRODUCT_DB
    if PRODUCT_DB:
        try:
            PRODUCT_DB.close()
            print("✅ Database connection closed")
        except Exception:
            pass
        finally:
            PRODUCT_DB = None
def debug_families_impl():
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
                    LIMIT ?
                """, (cfg_int("main.debug_families_limit", 50),))
                families = [{"family": r[0], "count": r[1]} for r in cur.fetchall()]
                result["families_in_db"] = families
                result["total_products"] = PRODUCT_DB.get_stats()["total_products"]
            except Exception as e:
                result["error"] = str(e)
        
        return result


def debug_pim_source_impl():
    db_path = getattr(PRODUCT_DB, "db_path", None) if PRODUCT_DB else None
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    pim_candidates = []
    for p in sorted(glob.glob(os.path.join(data_dir, "PIM_*.xlsx"))):
        try:
            pim_candidates.append({
                "name": os.path.basename(p),
                "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p))),
                "size": os.path.getsize(p),
            })
        except Exception:
            pim_candidates.append({"name": os.path.basename(p)})
    return {
        "xlsx_path": XLSX_PATH,
        "xlsx_exists": os.path.exists(XLSX_PATH),
        "db_path": db_path,
        "db_exists": bool(db_path and os.path.exists(db_path)),
        "pim_candidates": pim_candidates,
    }

# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------

def health_impl():
    return {
        "status": "ok",
        "uptime_sec": round(max(0.0, time.time() - APP_STARTED_AT), 1),
        "xlsx_path": XLSX_PATH,
        "dataframe_loaded": DB is not None and not DB.empty,
        "dataframe_rows": int(len(DB)) if DB is not None else 0,
        "database_available": HAS_DATABASE,
        "database_enabled": USE_SQLITE,
        "database_active": PRODUCT_DB is not None,
        "database_backend": getattr(PRODUCT_DB, "backend", db_runtime.product_db_backend),
        "product_db_enabled": USE_PRODUCT_DB,
        "product_db_active": PRODUCT_DB is not None,
        "product_db_backend": db_runtime.product_db_backend,
        "product_postgres_requested": db_runtime.product_postgres_requested,
    }


def catalog_health_impl() -> Dict[str, Any]:
    if DB is None or DB.empty:
        return {
            "status": "empty",
            "summary": {
                "rows": 0,
                "unique_families": 0,
                "unique_manufacturers": 0,
                "priced_rows": 0,
                "duplicate_product_codes": 0,
                "legacy_road_lighting_rows": 0,
            },
            "field_coverage": [],
            "top_families": [],
            "issues": [],
        }

    df = DB.copy()

    def _clean_series(col: str):
        if col not in df.columns:
            return pd.Series([""] * len(df), index=df.index, dtype="object")
        return df[col].fillna("").astype(str).str.strip()

    def _non_empty_count(col: str) -> int:
        return int(_clean_series(col).replace({"nan": "", "None": ""}).ne("").sum())

    rows = int(len(df))
    product_codes = _clean_series("product_code")
    family_series = _clean_series("product_family")
    manufacturer_series = _clean_series("manufacturer")
    price_series = pd.to_numeric(df["price"], errors="coerce") if "price" in df.columns else pd.Series([None] * len(df), index=df.index)
    cct_num = pd.to_numeric(_clean_series("cct_k").str.extract(r"(\d+)")[0], errors="coerce") if "cct_k" in df.columns else pd.Series([None] * len(df), index=df.index)
    power_num = pd.to_numeric(_clean_series("power_max_w").str.extract(r"(-?\d+(?:\.\d+)?)")[0], errors="coerce") if "power_max_w" in df.columns else pd.Series([None] * len(df), index=df.index)
    lumen_num = pd.to_numeric(_clean_series("lumen_output").str.extract(r"(-?\d+(?:\.\d+)?)")[0], errors="coerce") if "lumen_output" in df.columns else pd.Series([None] * len(df), index=df.index)
    efficacy_num = pd.to_numeric(_clean_series("efficacy_lm_w").str.extract(r"(-?\d+(?:\.\d+)?)")[0], errors="coerce") if "efficacy_lm_w" in df.columns else pd.Series([None] * len(df), index=df.index)
    warranty_num = pd.to_numeric(_clean_series("warranty_years").str.extract(r"(-?\d+(?:\.\d+)?)")[0], errors="coerce") if "warranty_years" in df.columns else pd.Series([None] * len(df), index=df.index)
    ip_raw = _clean_series("ip_rating").str.upper().str.replace(" ", "", regex=False) if "ip_rating" in df.columns else pd.Series([""] * len(df), index=df.index)
    ik_raw = _clean_series("ik_rating").str.upper().str.replace(" ", "", regex=False) if "ik_rating" in df.columns else pd.Series([""] * len(df), index=df.index)

    duplicate_mask = product_codes.ne("") & product_codes.duplicated(keep=False)
    duplicate_codes = sorted({code for code in product_codes[duplicate_mask].tolist() if code})[:25]

    key_fields = [
        "product_family",
        "manufacturer",
        "product_name",
        "ip_rating",
        "ik_rating",
        "cct_k",
        "power_max_w",
        "lumen_output",
        "price",
    ]
    field_coverage = []
    for field in key_fields:
        if field == "price":
            non_empty = int(price_series.notna().sum())
        else:
            non_empty = _non_empty_count(field)
        pct = round((non_empty / max(rows, 1)) * 100.0, 1)
        field_coverage.append({"field": field, "filled": non_empty, "missing": rows - non_empty, "pct": pct})

    fam_counts = (
        family_series[family_series.ne("")]
        .value_counts()
        .head(15)
        .to_dict()
    )
    top_families = [{"family": str(k), "count": int(v)} for k, v in fam_counts.items()]

    issues: List[Dict[str, Any]] = []
    if int(duplicate_mask.sum()) > 0:
        issues.append({
            "key": "duplicate_product_codes",
            "severity": "warn",
            "count": int(duplicate_mask.sum()),
            "message": f"Duplicate product codes found: {len(duplicate_codes)} unique duplicates in the loaded catalog.",
            "examples": duplicate_codes,
        })
    legacy_count = int(family_series.str.lower().eq("road lighting").sum())
    if legacy_count > 0:
        issues.append({
            "key": "legacy_family_alias",
            "severity": "warn",
            "count": legacy_count,
            "message": "Legacy family value 'road lighting' is still present and should be normalized to 'Street lighting'.",
            "examples": ["road lighting"],
        })
    if "price" in df.columns:
        missing_price_codes = product_codes[price_series.isna() & product_codes.ne("")].head(20).tolist()
        if missing_price_codes:
            issues.append({
                "key": "missing_price",
                "severity": "info",
                "count": int(price_series.isna().sum()),
                "message": "Some products have no merged price.",
                "examples": missing_price_codes,
            })
    missing_family_codes = product_codes[family_series.eq("") & product_codes.ne("")].head(20).tolist()
    if missing_family_codes:
        issues.append({
            "key": "missing_family",
            "severity": "error",
            "count": int(family_series.eq("").sum()),
            "message": "Some products have no family after import mapping.",
            "examples": missing_family_codes,
        })
    invalid_ip_mask = ip_raw.ne("") & ~ip_raw.str.match(r"^(>=|<=|>|<)?IP[0-9X]{2}$", na=False)
    if int(invalid_ip_mask.sum()) > 0:
        issues.append({
            "key": "invalid_ip_format",
            "severity": "warn",
            "count": int(invalid_ip_mask.sum()),
            "message": "Some IP values use a format the search engine may not parse reliably.",
            "examples": product_codes[invalid_ip_mask].head(20).tolist(),
        })
    invalid_ik_mask = ik_raw.ne("") & ~ik_raw.str.match(r"^(>=|<=|>|<)?IK\d{1,2}$", na=False)
    if int(invalid_ik_mask.sum()) > 0:
        issues.append({
            "key": "invalid_ik_format",
            "severity": "warn",
            "count": int(invalid_ik_mask.sum()),
            "message": "Some IK values use a format the search engine may not parse reliably.",
            "examples": product_codes[invalid_ik_mask].head(20).tolist(),
        })
    invalid_cct_mask = cct_num.notna() & ~cct_num.isin([2200, 2700, 3000, 3500, 4000, 5000, 5700, 6500])
    if int(invalid_cct_mask.sum()) > 0:
        issues.append({
            "key": "unexpected_cct_values",
            "severity": "info",
            "count": int(invalid_cct_mask.sum()),
            "message": "Some CCT values are unusual and may deserve a catalog review.",
            "examples": product_codes[invalid_cct_mask].head(20).tolist(),
        })
    invalid_power_mask = power_num.notna() & (power_num <= 0)
    if int(invalid_power_mask.sum()) > 0:
        issues.append({
            "key": "non_positive_power",
            "severity": "warn",
            "count": int(invalid_power_mask.sum()),
            "message": "Some products have zero or negative power values.",
            "examples": product_codes[invalid_power_mask].head(20).tolist(),
        })
    invalid_lumen_mask = lumen_num.notna() & (lumen_num <= 0)
    if int(invalid_lumen_mask.sum()) > 0:
        issues.append({
            "key": "non_positive_lumen",
            "severity": "warn",
            "count": int(invalid_lumen_mask.sum()),
            "message": "Some products have zero or negative lumen values.",
            "examples": product_codes[invalid_lumen_mask].head(20).tolist(),
        })
    invalid_efficacy_mask = efficacy_num.notna() & (efficacy_num <= 0)
    if int(invalid_efficacy_mask.sum()) > 0:
        issues.append({
            "key": "non_positive_efficacy",
            "severity": "warn",
            "count": int(invalid_efficacy_mask.sum()),
            "message": "Some products have zero or negative efficacy values.",
            "examples": product_codes[invalid_efficacy_mask].head(20).tolist(),
        })
    invalid_warranty_mask = warranty_num.notna() & (warranty_num < 0)
    if int(invalid_warranty_mask.sum()) > 0:
        issues.append({
            "key": "negative_warranty",
            "severity": "warn",
            "count": int(invalid_warranty_mask.sum()),
            "message": "Some products have negative warranty values.",
            "examples": product_codes[invalid_warranty_mask].head(20).tolist(),
        })

    return {
        "status": "ok",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "rows": rows,
            "unique_families": int(family_series[family_series.ne("")].nunique()),
            "unique_manufacturers": int(manufacturer_series[manufacturer_series.ne("")].nunique()),
            "priced_rows": int(price_series.notna().sum()),
            "duplicate_product_codes": int(duplicate_mask.sum()),
            "legacy_road_lighting_rows": legacy_count,
        },
        "field_coverage": field_coverage,
        "top_families": top_families,
        "issues": issues,
    }


def access_matrix_impl() -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for item in ACCESS_MATRIX:
        key = str(item.get("access") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "counts": counts,
        "items": ACCESS_MATRIX,
    }


def codes_suggest_impl(q: str, limit: int):
    items = _suggest_product_codes(q, limit=limit)
    return {"q": q, "count": len(items), "items": items}


@app.get("/preview-image")
def preview_image(
    request: FastAPIRequest,
    product_code: str = Query("", description="Order code"),
    manufacturer: str = Query("", description="Manufacturer"),
    website_url: str = Query("", description="Website URL"),
):
    preview_limit, preview_window = security.preview_limit()
    security.enforce_rate_limit(request, bucket="preview-image", limit=preview_limit, window_sec=preview_window)
    code = str(product_code or "").strip()
    mfg = str(manufacturer or "").strip()
    url = str(website_url or "").strip() or _build_website_url(code, mfg)
    img = _extract_first_site_image_url(url, product_code=code)
    if img:
        try:
            with safe_open_url(
                img,
                timeout=cfg_int("main.http_timeout_image_extract_sec", 4),
                allowed_hosts=PUBLIC_FETCH_HOSTS,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "image/jpeg")
            return Response(content=data, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            pass

    # Fallback static image without redirect (200 OK).
    logo = os.path.join(FRONTEND_DIR, "logo-disano.webp" if "fosnova" in mfg.lower() else "logo-disano.png")
    try:
        with open(logo, "rb") as f:
            data = f.read()
        media = "image/webp" if logo.endswith(".webp") else "image/png"
        return Response(content=data, media_type=media, headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        return Response(content=b"", media_type="application/octet-stream", status_code=204)


@app.get("/full-image")
def full_image(
    request: FastAPIRequest,
    product_code: str = Query("", description="Order code"),
    manufacturer: str = Query("", description="Manufacturer"),
    website_url: str = Query("", description="Website URL"),
):
    preview_limit, preview_window = security.preview_limit()
    security.enforce_rate_limit(request, bucket="full-image", limit=preview_limit, window_sec=preview_window)
    code = str(product_code or "").strip()
    mfg = str(manufacturer or "").strip()
    url = str(website_url or "").strip() or _build_website_url(code, mfg)

    # Prefer explicit GraphQL full image for better popup quality.
    img = _extract_graphql_image_url(code)
    if not img:
        img = _extract_first_site_image_url(url, product_code=code)
    if img:
        try:
            with safe_open_url(
                img,
                timeout=cfg_int("main.http_timeout_gql_sec", 6),
                allowed_hosts=PUBLIC_FETCH_HOSTS,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "image/jpeg")
            return Response(content=data, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            pass

    # Final fallback: reuse preview endpoint behavior (still 200/204 and cached).
    return preview_image(request=request, product_code=code, manufacturer=mfg, website_url=url)


@app.post("/compare-codes")
def compare_codes(req: CompareCodesRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    resp = handle_compare_codes(
        req,
        compare_products_fn=compare_products,
        compare_products_request_factory=lambda codes: CompareProductsRequest(codes=codes),
    )
    _record_analytics_event(
        request,
        event_type="compare_codes",
        user=current_user,
        page="tools",
        path="/compare-codes",
        metadata={"code_a": str(req.code_a or ""), "code_b": str(req.code_b or "")},
    )
    return resp


_COMPARE_FIELD_PRIORITY = [
    "product_code", "product_name", "manufacturer", "product_family",
    "ip_rating", "ip_visible", "ip_non_visible", "ik_rating",
    "cct_k", "cri", "ugr",
    "power_max_w", "power_min_w", "lumen_output", "efficacy_lm_w",
    "beam_angle_deg", "beam_type", "asymmetry",
    "control_protocol", "interface", "emergency_present",
    "shape", "housing_color", "housing_material", "mounting_type",
    "diameter", "luminaire_length", "luminaire_width", "luminaire_height",
    "ambient_temp_min_c", "ambient_temp_max_c",
    "warranty_years", "lifetime_hours", "led_rated_life_h",
    "lumen_maintenance_pct", "failure_rate_pct", "price",
]

_COMPARE_FIELD_EXCLUDE = {
    "id",
    "imported_at",
}


def _cmp_norm_value(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    n = _to_num(s)
    if n is not None:
        return str(round(float(n), 6))
    return s.lower()


def _humanize_compare_field(key: str) -> str:
    raw = str(key or "").strip()
    if not raw:
        return ""
    up = raw.upper()
    if up in {"IP", "IK", "CRI", "UGR", "CCT"}:
        return up
    parts = raw.replace("__", "_").split("_")
    return " ".join([p.upper() if p.lower() in {"ip", "ik", "cri", "ugr", "cct"} else p.capitalize() for p in parts if p])


def _collect_compare_fields(
    rows: List[Optional[Dict[str, Any]]],
    include_empty: bool = True,
    reference_only: bool = False,
) -> List[str]:
    present: set[str] = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        for k in r.keys():
            kk = str(k or "").strip()
            if not kk or kk in _COMPARE_FIELD_EXCLUDE:
                continue
            present.add(kk)
    if reference_only:
        ref = rows[0] if rows else None
        ref_keys: set[str] = set()
        if isinstance(ref, dict):
            for k in ref.keys():
                kk = str(k or "").strip()
                if kk and kk not in _COMPARE_FIELD_EXCLUDE:
                    ref_keys.add(kk)
        present = {k for k in present if k in ref_keys}
    if not present:
        return []

    ordered: List[str] = []
    for k in _COMPARE_FIELD_PRIORITY:
        if k in present:
            ordered.append(k)
    for k in sorted(present):
        if k not in ordered:
            ordered.append(k)

    if include_empty:
        return ordered

    out: List[str] = []
    for f in ordered:
        vals = [(r.get(f) if isinstance(r, dict) else None) for r in rows]
        norm_vals = [_cmp_norm_value(v) for v in vals]
        if any(x != "" for x in norm_vals):
            out.append(f)
    return out


@app.post("/compare-products")
def compare_products(req: CompareProductsRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    resp = handle_compare_products(
        req,
        find_product_by_code_any=_find_product_by_code_any,
        manufacturer_label=_manufacturer_label,
        build_website_url=_build_website_url,
        build_datasheet_url=_build_datasheet_url,
        collect_compare_fields=_collect_compare_fields,
        cmp_norm_value=_cmp_norm_value,
        quote_plus=quote_plus,
    )
    _record_analytics_event(
        request,
        event_type="compare_products",
        user=current_user,
        page="tools",
        path="/compare-products",
        metadata={"code_count": len(req.codes or []), "codes": [str(x or "") for x in (req.codes or [])[:10]]},
    )
    return resp


@app.post("/compare-spec-products")
def compare_spec_products(req: CompareSpecProductsRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    resp = handle_compare_spec_products(
        req,
        sanitize_filters=_sanitize_filters,
        normalize_ui_filters=_normalize_ui_filters,
        find_product_by_code_any=_find_product_by_code_any,
        manufacturer_label=_manufacturer_label,
        build_website_url=_build_website_url,
        build_datasheet_url=_build_datasheet_url,
        collect_compare_fields=_collect_compare_fields,
        cmp_norm_value=_cmp_norm_value,
        to_num=_to_num,
        quote_plus=quote_plus,
        dimension_tolerance=DIMENSION_TOLERANCE,
        dimension_keys=DIMENSION_KEYS,
    )
    _record_analytics_event(
        request,
        event_type="compare_spec_products",
        user=current_user,
        page="tools",
        path="/compare-spec-products",
        filters=dict(req.ideal_spec or {}),
        metadata={"code_count": len(req.codes or []), "codes": [str(x or "") for x in (req.codes or [])[:10]]},
    )
    return resp


@app.post("/alternatives-from-spec")
def alternatives_from_spec(req: IdealSpecAlternativesRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    resp = handle_alternatives_from_spec(
        req,
        sanitize_filters=_sanitize_filters,
        normalize_ui_filters=_normalize_ui_filters,
        cfg_int=cfg_int,
        map_filters_to_sql=map_filters_to_sql,
        product_db=PRODUCT_DB,
        db_dataframe=DB,
        row_to_public_dict=_row_to_public_dict,
        score_product=score_product,
        manufacturer_label=_manufacturer_label,
        build_website_url=_build_website_url,
        build_datasheet_url=_build_datasheet_url,
        quote_plus=quote_plus,
        to_num=_to_num,
    )
    _record_analytics_event(
        request,
        event_type="alternatives_from_spec",
        user=current_user,
        page="tools",
        path="/alternatives-from-spec",
        filters=dict(req.ideal_spec or {}),
        metadata={"limit": int(req.limit or 0), "min_score": float(req.min_score or 0) if req.min_score is not None else None},
    )
    return resp


@app.post("/compare/export-pdf")
def export_compare_pdf(req: CompareExportPdfRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    resp = handle_export_compare_pdf(
        req,
        compare_products_fn=compare_products,
        compare_products_request_factory=lambda codes: CompareProductsRequest(codes=codes),
        compare_spec_products_fn=compare_spec_products,
        compare_spec_products_request_factory=lambda ideal_spec, codes: CompareSpecProductsRequest(ideal_spec=ideal_spec, codes=codes),
        sanitize_filters=_sanitize_filters,
        normalize_ui_filters=_normalize_ui_filters,
        find_product_by_code_any=_find_product_by_code_any,
        collect_compare_fields=_collect_compare_fields,
        cmp_norm_value=_cmp_norm_value,
        humanize_compare_field=_humanize_compare_field,
        extract_graphql_image_url=_extract_graphql_image_url,
        extract_first_site_image_url=_extract_first_site_image_url,
        build_website_url=_build_website_url,
        preview_image_fn=preview_image,
        safe_open_url=safe_open_url,
        cfg_int=cfg_int,
        cfg_float=cfg_float,
        public_fetch_hosts=PUBLIC_FETCH_HOSTS,
        frontend_dir=FRONTEND_DIR,
        html_module=html,
        os_module=os,
        re_module=re,
        streaming_response_cls=StreamingResponse,
    )
    _record_analytics_event(
        request,
        event_type="compare_export_pdf",
        user=current_user,
        page="tools",
        path="/compare/export-pdf",
        metadata={"code_count": len(req.codes or []), "has_ideal_spec": bool(req.ideal_spec)},
    )
    return resp

@app.post("/alternatives")
def alternatives(req: AlternativesRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    resp = handle_alternatives(
        req,
        find_product_by_code_any=_find_product_by_code_any,
        cfg_int=cfg_int,
        product_db=PRODUCT_DB,
        db_dataframe=DB,
        row_to_public_dict=_row_to_public_dict,
        alt_similarity=_alt_similarity,
        manufacturer_label=_manufacturer_label,
        build_website_url=_build_website_url,
        build_datasheet_url=_build_datasheet_url,
        quote_plus=quote_plus,
    )
    _record_analytics_event(
        request,
        event_type="alternatives",
        user=current_user,
        page="tools",
        path="/alternatives",
        product_code=str(req.code or ""),
        metadata={"limit": int(req.limit or 0), "min_score": float(req.min_score or 0) if req.min_score is not None else None},
    )
    return resp

def _select_exact_and_similar(
    exact_pool: List[Dict[str, Any]],
    similar_pool: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
    text_query: str,
    hard_filters: Dict[str, Any],
    soft_filters: Dict[str, Any],
    limit: int,
    include_similar: bool,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return select_exact_and_similar(
        exact_pool=exact_pool,
        similar_pool=similar_pool,
        rows=rows,
        text_query=text_query,
        hard_filters=hard_filters,
        soft_filters=soft_filters,
        limit=limit,
        include_similar=include_similar,
        text_relevance_fn=_text_relevance,
    )


@app.post("/quote/export-pdf")
def export_quote_pdf(req: QuotePdfRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    resp = handle_export_quote_pdf(
        req,
        frontend_dir=FRONTEND_DIR,
        html_module=html,
        os_module=os,
        streaming_response_cls=StreamingResponse,
    )
    _record_analytics_event(
        request,
        event_type="quote_export_pdf",
        user=current_user,
        page="quote",
        path="/quote/export-pdf",
        query_text=str(req.project or ""),
        metadata={"company": str(req.company or ""), "item_count": len(req.items or [])},
    )
    return resp


@app.post("/quote/datasheets-zip")
def export_quote_datasheets_zip(req: QuoteDatasheetsZipRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    resp = handle_export_quote_datasheets_zip(
        req,
        build_datasheet_url=_build_datasheet_url,
        safe_open_url=safe_open_url,
        cfg_int=cfg_int,
        public_fetch_hosts=PUBLIC_FETCH_HOSTS,
        re_module=re,
        zipfile_module=zipfile,
        streaming_response_cls=StreamingResponse,
    )
    _record_analytics_event(
        request,
        event_type="quote_datasheets_zip",
        user=current_user,
        page="quote",
        path="/quote/datasheets-zip",
        metadata={"item_count": len(req.items or [])},
    )
    return resp


@app.post("/parse-pdf")
async def parse_pdf(request: FastAPIRequest, file: UploadFile = File(...)):
    limit, window = security.debug_pdf_limit()
    security.enforce_rate_limit(request, bucket="parse-pdf", limit=limit, window_sec=window)
    return await debug_parse_pdf_impl(file)


@app.post("/parse-image")
async def parse_image(request: FastAPIRequest, file: UploadFile = File(...)):
    limit, window = security.debug_image_limit()
    security.enforce_rate_limit(request, bucket="parse-image", limit=limit, window_sec=window)
    return await debug_parse_image_impl(file)

@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    if request is not None and not current_user:
        limit, window = security.public_search_limit()
        security.enforce_rate_limit(request, bucket="public-search", limit=limit, window_sec=window)
    resp = handle_search(
        req,
        local_text_to_filters=local_text_to_filters,
        sanitize_filters=_sanitize_filters,
        normalize_ui_filters=_normalize_ui_filters,
        llm_intent_to_filters=llm_intent_to_filters,
        llm_intent_to_filters_with_meta=llm_intent_to_filters_with_meta,
        allowed_families=ALLOWED_FAMILIES,
        infer_interpreted=_infer_interpreted,
        map_filters_to_sql=map_filters_to_sql,
        cfg_list=cfg_list,
        cfg_int=cfg_int,
        cfg_float=cfg_float,
        score_product=score_product,
        product_db=PRODUCT_DB,
        db_runtime_backend=db_runtime.product_db_backend,
        db_dataframe=DB,
        search_rows_by_text_db=_search_rows_by_text_sqlite,
        dedupe_rows_by_product_code=_dedupe_rows_by_product_code,
        text_relevance=_text_relevance,
        select_exact_and_similar=select_exact_and_similar,
        manufacturer_label=_manufacturer_label,
        build_website_url=_build_website_url,
        build_datasheet_url=_build_datasheet_url,
        clean_value=_clean,
        logger=logger,
        quote_plus=quote_plus,
        include_price=bool(current_user),
        max_limit=100,
    )
    _record_analytics_event(
        request,
        event_type="search",
        user=current_user,
        page="finder",
        path="/search",
        query_text=str(req.text or ""),
        filters=dict(req.filters or {}),
        metadata={
            "exact_count": len(getattr(resp, "exact", []) or []),
            "similar_count": len(getattr(resp, "similar", []) or []),
            "result_limit": min(max(1, int(req.limit or 20)), 100),
            "empty_search": bool((getattr(resp, "interpreted", None) or {}).get("empty_search")),
            "requested_family": next(
                (
                    str(item.get("value") or "").strip()
                    for item in ((getattr(resp, "interpreted", None) or {}).get("understood_filter_items") or [])
                    if str(item.get("key") or "").strip() == "product_family" and str(item.get("value") or "").strip()
                ),
                "",
            ),
            "has_exact": bool(len(getattr(resp, "exact", []) or []) > 0),
            "has_any_result": bool(len(getattr(resp, "exact", []) or []) + len(getattr(resp, "similar", []) or []) > 0),
        },
    )
    return resp


@app.post("/facets", response_model=FacetsResponse)
def facets(req: SearchRequest, request: FastAPIRequest = None):
    current_user = _get_optional_current_user(request)
    if request is not None and not current_user:
        limit, window = security.public_facets_limit()
        security.enforce_rate_limit(request, bucket="public-facets", limit=limit, window_sec=window)
    resp = handle_facets(
        req,
        local_text_to_filters=local_text_to_filters,
        sanitize_filters=_sanitize_filters,
        normalize_ui_filters=_normalize_ui_filters,
        llm_intent_to_filters=llm_intent_to_filters,
        allowed_families=ALLOWED_FAMILIES,
        allowed_families_norm=ALLOWED_FAMILIES_NORM,
        map_filters_to_sql=map_filters_to_sql,
        facets_cache_key=_facets_cache_key,
        facets_cache_get=_facets_cache_get,
        facets_cache_set=_facets_cache_set,
        cfg_int=cfg_int,
        product_db=PRODUCT_DB,
        db_dataframe=DB,
        product_name_short_from_rows=_product_name_short_from_rows,
        df_filtered_subset=_df_filtered_subset,
        seed_filters_for_facets=_seed_filters_for_facets,
        top_values=_top_values,
        top_product_name_short_values=_top_product_name_short_values,
        top_values_from_db_fallback=_top_values_from_db_fallback,
        product_name_short_from_db_fallback=_product_name_short_from_db_fallback,
        families_from_db_fallback=_families_from_db_fallback,
        min_max_numeric=_min_max_numeric,
        num_from_text_series=_num_from_text_series,
    )
    _record_analytics_event(
        request,
        event_type="facets_load",
        user=current_user,
        page="finder",
        path="/facets",
        query_text=str(req.text or ""),
        filters=dict(req.filters or {}),
    )
    return resp

@app.get("/database/stats")
def database_stats():
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="Product database not available")
    try:
        return PRODUCT_DB.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/admin/catalog-health")
def admin_catalog_health(_staff_user: UserPublic = Depends(require_staff_dep)):
    return catalog_health_impl()


@app.get("/admin/access-matrix")
def admin_access_matrix(_admin_user: UserPublic = Depends(require_admin_dep)):
    return access_matrix_impl()


@app.get("/admin/catalog-release-diff")
def admin_catalog_release_diff(_lead_user: UserPublic = Depends(require_leadership_dep)):
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="Product database not available")
    return PRODUCT_DB.get_latest_release_diff()


@app.get("/admin/catalog-release-diff/export")
def admin_catalog_release_diff_export(_lead_user: UserPublic = Depends(require_leadership_dep)):
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="Product database not available")
    csv_text = PRODUCT_DB.export_latest_release_diff_csv()
    diff = PRODUCT_DB.get_latest_release_diff()
    summary = diff.get("summary") or {}
    source_name = str(summary.get("source_filename") or "catalog-release")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.splitext(source_name)[0]).strip("-") or "catalog-release"
    filename = f"{safe_name}-diff.csv"
    return StreamingResponse(
        iter([csv_text.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

def refresh_database_impl():
    global FAMILY_MAP_PATH
    if not PRODUCT_DB:
        raise HTTPException(status_code=503, detail="Product database not available")
    try:
        FAMILY_MAP_PATH = _resolve_family_map_path()
        count = PRODUCT_DB.init_db(XLSX_PATH, FAMILY_MAP_PATH)
        initialize_runtime_state()
        return {
            "success": True,
            "message": f"Database refreshed with {count} products",
            "count": count,
            "xlsx_path": XLSX_PATH,
            "db_path": getattr(PRODUCT_DB, "db_path", None),
            "release_diff": PRODUCT_DB.get_latest_release_diff() if PRODUCT_DB else {},
            "catalog_health": catalog_health_impl(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")

def debug_parse_impl(q: str = ""):
    parsed = local_text_to_filters(q or "") or {}
    parsed = _sanitize_filters(parsed)
    return {"q": q, "local": parsed, "sql": map_filters_to_sql(parsed)}

async def debug_parse_pdf_impl(file: UploadFile):
    name = str(getattr(file, "filename", "") or "")
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")
    try:
        raw = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {e}")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty")
    max_pdf_bytes = cfg_int("main.pdf_parse_max_upload_bytes", 10 * 1024 * 1024)
    if len(raw) > max_pdf_bytes:
        raise HTTPException(status_code=413, detail=f"PDF too large (max {max_pdf_bytes // (1024 * 1024)}MB)")
    if not looks_like_pdf(raw):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF")

    text = ""
    reader = None
    parse_errors: List[str] = []
    image_parse_warnings: List[str] = []
    try:
        from io import BytesIO
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            try:
                from PyPDF2 import PdfReader  # type: ignore
            except Exception as import_exc:
                raise HTTPException(status_code=503, detail=f"PDF parser dependency missing: {import_exc}")
        reader = PdfReader(BytesIO(raw))
        chunks: List[str] = []
        max_pages = cfg_int("main.pdf_parse_max_pages", 40)
        max_chars = cfg_int("main.pdf_parse_max_chars", 250000)
        for i, page in enumerate(reader.pages[:max_pages]):
            try:
                chunk = page.extract_text() or ""
                chunks.append(chunk)
                if sum(len(c) for c in chunks) >= max_chars:
                    break
            except Exception as pe:
                parse_errors.append(f"page {i+1}: {pe}")
        text = "\n".join(chunks).strip()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"PDF parser not available/failed: {e}")
    finally:
        try:
            await file.close()
        except Exception:
            pass

    # Light cleanup for tender PDFs with excessive line breaks/spaces.
    text_clean = re.sub(r"[ \t]+", " ", text or "")
    text_clean = re.sub(r"\n{2,}", "\n", text_clean).strip()
    compare_reference_image = ""
    ocr_text_clean = ""
    ocr_warnings: List[str] = []

    # OCR fallback for scanned PDFs: render pages and extract text only when
    # the embedded text layer is missing or too thin to be useful.
    if len(text_clean) < cfg_int("main.pdf_ocr_min_text_chars", 80):
        try:
            from io import BytesIO
            import fitz  # type: ignore
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore

            ocr_chunks: List[str] = []
            ocr_pages = cfg_int("main.pdf_ocr_max_pages", 5)
            zoom = cfg_float("main.pdf_ocr_render_zoom", 2.0)
            lang = str(os.getenv("PDF_OCR_LANG", "eng+ita")).strip() or "eng+ita"
            with fitz.open(stream=raw, filetype="pdf") as ocr_doc:
                for pi, page in enumerate(ocr_doc[:ocr_pages]):
                    try:
                        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                        png_bytes = pix.tobytes("png")
                        if (not compare_reference_image) and len(png_bytes) <= cfg_int("main.pdf_image_preview_max_bytes", 700 * 1024):
                            compare_reference_image = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
                        page_text = pytesseract.image_to_string(Image.open(BytesIO(png_bytes)), lang=lang) or ""
                        page_text = re.sub(r"[ \t]+", " ", page_text)
                        page_text = re.sub(r"\n{2,}", "\n", page_text).strip()
                        if page_text:
                            ocr_chunks.append(page_text)
                    except Exception as ocr_page_exc:
                        ocr_warnings.append(f"ocr page {pi+1}: {ocr_page_exc}")
            ocr_text_clean = "\n".join(ocr_chunks).strip()
        except Exception as ocr_exc:
            ocr_warnings.append(f"ocr unavailable: {ocr_exc}")

    effective_text = text_clean if len(text_clean) >= len(ocr_text_clean) else ocr_text_clean
    parsed_text = local_text_to_filters(effective_text) if effective_text else {}

    # Optional image-based inference from embedded PDF images (useful for scanned PDFs).
    parsed_image: Dict[str, Any] = {}
    image_filters_all: List[Dict[str, Any]] = []
    if reader is not None:
        max_img_pages = cfg_int("main.pdf_image_parse_max_pages", 20)
        max_images = cfg_int("main.pdf_image_parse_max_images", 6)
        max_image_bytes = cfg_int("main.pdf_image_parse_max_image_bytes", 5 * 1024 * 1024)
        max_preview_bytes = cfg_int("main.pdf_image_preview_max_bytes", 700 * 1024)
        seen = 0
        for pi, page in enumerate(list(getattr(reader, "pages", []))[:max_img_pages]):
            if seen >= max_images:
                break
            page_images = list(getattr(page, "images", []) or [])
            if not page_images:
                continue
            for ii, img in enumerate(page_images):
                if seen >= max_images:
                    break
                try:
                    data = getattr(img, "data", None)
                    if not data:
                        image_parse_warnings.append(f"page {pi+1} image {ii+1}: no binary data")
                        continue
                    if len(data) > max_image_bytes:
                        image_parse_warnings.append(f"page {pi+1} image {ii+1}: skipped (too large)")
                        continue
                    ext = str(
                        getattr(img, "image_extension", "")
                        or getattr(img, "extension", "")
                        or ""
                    ).strip().lower().lstrip(".")
                    mime = {
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "png": "image/png",
                        "webp": "image/webp",
                    }.get(ext, "image/jpeg")
                    if (not compare_reference_image) and len(data) <= max_preview_bytes:
                        try:
                            b64 = base64.b64encode(data).decode("ascii")
                            compare_reference_image = f"data:{mime};base64,{b64}"
                        except Exception as pe:
                            image_parse_warnings.append(f"page {pi+1} image {ii+1}: preview encode failed ({pe})")
                    vision_one = llm_image_to_inference(
                        image_bytes=data,
                        mime_type=mime,
                        allowed_families=ALLOWED_FAMILIES,
                    ) or {}
                    one = dict(vision_one.get("filters") or {})
                    if not one and vision_one.get("notes"):
                        image_parse_warnings.append(f"page {pi+1} image {ii+1}: {vision_one.get('notes')}")
                    if one:
                        image_filters_all.append(one)
                    seen += 1
                except Exception as ie:
                    image_parse_warnings.append(f"page {pi+1} image {ii+1}: {ie}")

    if image_filters_all:
        # Majority vote per field across analyzed images.
        votes: Dict[str, Counter] = {}
        for d in image_filters_all:
            for k, v in d.items():
                kk = str(k or "").strip()
                vv = str(v or "").strip()
                if not kk or not vv:
                    continue
                if kk not in votes:
                    votes[kk] = Counter()
                votes[kk][vv] += 1
        parsed_image = {k: c.most_common(1)[0][0] for k, c in votes.items() if c}

    parsed: Dict[str, Any] = {}
    if isinstance(parsed_text, dict):
        parsed.update(parsed_text)
    # Keep text-derived values as priority; fill only missing keys from image inference.
    for k, v in (parsed_image or {}).items():
        if k not in parsed and v is not None and str(v).strip() != "":
            parsed[k] = v

    if not parsed:
        raise HTTPException(
            status_code=422,
            detail="Could not extract requirements from PDF text or embedded images"
        )

    parsed = _sanitize_filters(parsed)
    return {
        "filename": name,
        "chars": len(effective_text),
        "text_preview": effective_text[:cfg_int("main.pdf_preview_chars", 4000)],
        "local": parsed,
        "sql": map_filters_to_sql(parsed),
        "local_text": _sanitize_filters(parsed_text or {}),
        "local_image": _sanitize_filters(parsed_image or {}),
        "images_analyzed": len(image_filters_all),
        "ocr_used": bool(ocr_text_clean),
        "ocr_chars": len(ocr_text_clean),
        "compare_reference_image": compare_reference_image,
        "parse_warnings": (parse_errors + image_parse_warnings + ocr_warnings)[:20],
    }


async def debug_parse_image_impl(file: UploadFile):
    name = str(getattr(file, "filename", "") or "")
    ctype = str(getattr(file, "content_type", "") or "").lower()
    ext = os.path.splitext(name)[1].lower()
    allowed_ext = {".jpg", ".jpeg", ".png", ".webp"}
    allowed_ctype = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if (ext and ext not in allowed_ext) and (ctype and ctype not in allowed_ctype):
        raise HTTPException(status_code=400, detail="Please upload an image file (JPG, PNG, WEBP)")
    try:
        raw = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {e}")
    finally:
        try:
            await file.close()
        except Exception:
            pass
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    max_bytes = cfg_int("main.image_parse_max_bytes", 8 * 1024 * 1024)
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Image too large (max {max_bytes // (1024 * 1024)}MB)")
    if not looks_like_supported_image(raw):
        raise HTTPException(status_code=400, detail="Uploaded file is not a supported image")

    vision = llm_image_to_inference(
        image_bytes=raw,
        mime_type=(ctype or "image/jpeg"),
        allowed_families=ALLOWED_FAMILIES,
    ) or {}
    parsed = dict(vision.get("filters") or {})
    parsed = _sanitize_filters(parsed)
    vision_status = str(vision.get("status") or "ok")
    vision_notes = str(vision.get("notes") or "").strip()
    if not parsed and vision_status == "disabled":
        raise HTTPException(status_code=503, detail=vision_notes or "AI image inference is not configured on backend")
    if not parsed and vision_status == "error":
        raise HTTPException(status_code=503, detail=vision_notes or "AI image inference is temporarily unavailable")
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not infer requirements from image")
    return {
        "filename": name,
        "content_type": ctype or "image/jpeg",
        "bytes": len(raw),
        "local": parsed,
        "sql": map_filters_to_sql(parsed),
        "vision": {
            "confidence": str(vision.get("confidence") or "medium"),
            "notes": str(vision.get("notes") or ""),
            "model": str(vision.get("model") or ""),
        },
    }

def debug_nonnull_sample_impl(
    col: str,
    limit: int = 10,
):
    if not PRODUCT_DB:
        return {"error": "product database not available"}

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

app.include_router(
    create_public_router(
        home_impl=home_impl,
        frontend_home_impl=home_impl,
        health_impl=health_impl,
        codes_suggest_impl=codes_suggest_impl,
    )
)

app.include_router(
    create_debug_router(
        security=security,
        clear_facets_cache_impl=clear_facets_cache_impl,
        recreate_database_impl=recreate_database_impl,
        debug_families_impl=debug_families_impl,
        debug_pim_source_impl=debug_pim_source_impl,
        refresh_database_impl=refresh_database_impl,
        debug_parse_impl=debug_parse_impl,
        debug_parse_pdf_impl=debug_parse_pdf_impl,
        debug_parse_image_impl=debug_parse_image_impl,
        debug_nonnull_sample_impl=debug_nonnull_sample_impl,
    )
)

app.include_router(create_auth_router(auth_service))

if __name__ == "__main__":
    print("\n✅ Server ready. Run with: uvicorn app.main:app --reload")
