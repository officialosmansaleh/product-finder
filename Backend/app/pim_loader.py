# app/pim_loader.py
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import pandas as pd
import os


def _extract_first_number(x):
    if x is None:
        return None
    s = str(x)
    m = re.search(r"(-?\d+(?:\.\d+)?)", s.replace(",", "."))
    return float(m.group(1)) if m else None

def _extract_hours(x):
    # "50000 hr" -> 50000
    return _extract_first_number(x)


def _extract_ugr_match(x):
    if x is None:
        return (None, None)
    s = str(x).strip().lower()
    if not s:
        return (None, None)
    s = s.replace("≤", "<=").replace("≥", ">=")
    s = s.replace("&lt;", "<").replace("&gt;", ">")
    s = re.sub(r"<\s*lt\s*/?\s*>", "<", s, flags=re.IGNORECASE)
    s = re.sub(r"<\s*gt\s*/?\s*>", ">", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", "", s)
    # Only trust numbers explicitly attached to the UGR marker.
    m = re.search(r"(?<![a-z0-9])ugr(?:[:;])?(<=|>=|<|>|=)?(\d{1,2})(?!\d)", s)
    if not m:
        return (None, None)
    op = m.group(1)
    value = int(m.group(2))
    return (op, value)


def _extract_ugr_value(x):
    _, value = _extract_ugr_match(x)
    return value

def _extract_ugr_op(x):
    op, _ = _extract_ugr_match(x)
    return op

def _extract_ik_value(x):
    import re
    s = "" if x is None else str(x).upper()
    m = re.search(r"IK\s*(\d{1,2})", s)
    if not m:
        m = re.search(r"(\d{1,2})", s)
    return float(m.group(1)) if m else None


def _compact_code(x) -> str:
    s = "" if x is None else str(x).strip()
    return re.sub(r"[^0-9A-Za-z]", "", s).lower()


def _load_price_map(price_xlsx_path: str, verbose: bool = True) -> pd.DataFrame:
    if not price_xlsx_path or not os.path.exists(price_xlsx_path):
        return pd.DataFrame(columns=["product_code", "price", "compact_code"])
    try:
        px = pd.read_excel(price_xlsx_path, engine="openpyxl")
    except Exception as e:
        if verbose:
            print(f"⚠️ Price list load failed: {e}")
        return pd.DataFrame(columns=["product_code", "price", "compact_code"])

    cols_norm = {str(c).strip().lower(): c for c in px.columns}
    oc_col = cols_norm.get("order code")
    pr_col = cols_norm.get("price")
    if not oc_col or not pr_col:
        if verbose:
            print("⚠️ Price list missing required columns: 'Order code' and 'PRICE'")
        return pd.DataFrame(columns=["product_code", "price", "compact_code"])

    out = pd.DataFrame()
    out["product_code"] = px[oc_col].astype(str).str.strip()
    out["price"] = pd.to_numeric(px[pr_col], errors="coerce")
    out = out.dropna(subset=["price"])
    out = out[out["product_code"] != ""]
    out["compact_code"] = out["product_code"].apply(_compact_code)
    out = out.drop_duplicates(subset=["compact_code"], keep="first").reset_index(drop=True)
    return out




# -----------------------------
# Header matching (auto COLUMN_MAP)
# -----------------------------

def _norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^\w]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokens(s: str) -> set:
    return set(_norm(s).split())


def _pick_first_matching_column(headers: List[str], include_any: List[str], require_all: List[str] | None = None) -> str | None:
    require_all = require_all or []
    for h in headers:
        n = _norm(h)
        if not n:
            continue
        if any(tok in n for tok in include_any) and all(tok in n for tok in require_all):
            return h
    return None


@dataclass(frozen=True)
class CanonicalSpec:
    key: str
    synonyms: List[str]


def _score(spec: CanonicalSpec, header: str) -> int:
    ht = _tokens(header)
    best = -999

    for syn in spec.synonyms:
        st = _tokens(syn)

        overlap = len(st & ht)
        missing = len(st - ht)
        extra = len(ht - st)

        score = overlap * 10 - missing * 6 - extra

        if _norm(syn) == _norm(header):
            score += 40

        best = max(best, score)

    return best


def build_column_map(
    headers: List[str],
    specs: List[CanonicalSpec],
    min_score: int = 12,
) -> Tuple[Dict[str, str], Dict[str, List[Tuple[str, int]]]]:
    col_map: Dict[str, str] = {}
    rankings: Dict[str, List[Tuple[str, int]]] = {}

    for spec in specs:
        scored = [(h, _score(spec, h)) for h in headers]
        scored.sort(key=lambda x: x[1], reverse=True)
        rankings[spec.key] = scored[:5]

        if scored and scored[0][1] >= min_score:
            col_map[spec.key] = scored[0][0]

    return col_map, rankings


# -----------------------------
# Canonical PIM schema
# -----------------------------

CANON_SPECS: List[CanonicalSpec] = [
    CanonicalSpec(
        "product_code",
        ["Order code"],
    ),
    CanonicalSpec("short_product_code", ["Short product code", "short code", "codice breve", "short_product_code"]),

    CanonicalSpec(
        "product_name",
        ["<Name>", "Product name", "name", "description", "descrizione"],
    ),
    CanonicalSpec("manufacturer", ["Manufacturer", "Brand", "Produttore"]),
    # Family
      CanonicalSpec("etim_search_key", [
        "Etim Search Key", 
        "ETIM Search Key", 
        "Etim search key",
        "etim search key",  # Add lowercase version
        "etim_search_key",  # Add underscore version
        "etim",             # Add shorthand
        "search key",       # Add partial match
    ]),
    # Quality
    CanonicalSpec("warranty_years", ["warranty", "warranty years", "garanzia"]),
    CanonicalSpec("certifications", ["regulations","certifications", "certification", "certificazioni"]),
    CanonicalSpec("surge_protection_kv", ["surge protection", "surge kv", "surge (kv)", "sovratensione"]),
    CanonicalSpec("lifetime_hours", ["lifetime hours", "lifetime", "rated life", "led rated life"]),
    CanonicalSpec("led_rated_life_h", ["LED Rated Life - (h)", "LED Rated Life (h)", "LED Rated Life"]),
    CanonicalSpec("failure_rate_pct", ["Failure rate (Ta=25Â°C) (B)", "Failure rate"]),
    CanonicalSpec(
        "lumen_maintenance_pct",
        [
            "Lumen maintenance Ta 25Â° (L)",
            "Lumen maintenance Ta 25° (L)",
            "Lumen maintenance Ta 25 (L)",
            "Lumen maintenance Ta25 (L)",
            "Lumen maintenance %",
            "Lumen maintenance",
        ],
    ),



    # Electrical
    CanonicalSpec("power_min_w", ["total system power", "lamp power", "power", "w", "potenza"]),
    CanonicalSpec("power_max_w", ["total system power", "lamp power", "power", "w", "potenza"]),
    CanonicalSpec("voltage_range", ["voltage range", "voltage", "tensione", "vac"]),
    CanonicalSpec("power_factor", ["power factor", "pf", "fattore di potenza"]),
    CanonicalSpec("efficiency", ["efficiency", "efficienza"]),
    CanonicalSpec("control_protocol", ["controllability", "control", "dimming", "protocol"]),
    CanonicalSpec("interface", ["interface", "cp"]),
    CanonicalSpec("emergency_present", ["emergency power supply", "emergency", "emergenza", "em kit", "kit emergenza"]),
    CanonicalSpec("emergency_duration_min", ["emergency duration", "duration", "durata emergenza", "min"]),
    CanonicalSpec(
        "ambient_temp_min_c",
        [
            "minimum ambient temperature",
            "min ambient temperature",
            "ambient temperature min",
            "operating temperature min",
            "minimum operating temperature",
            "ta min",
            "ta minimum",
            "temp min",
            "temperatura minima",
            "temperatura ambiente minima",
        ],
    ),
    CanonicalSpec(
        "ambient_temp_max_c",
        [
            "maximum ambient temperature",
            "max ambient temperature",
            "ambient temperature max",
            "operating temperature max",
            "maximum operating temperature",
            "ta max",
            "ta maximum",
            "temp max",
            "temperatura massima",
            "temperatura ambiente massima",
        ],
    ),

    # Mechanical
    # IP handling:
    # - ip_rating: single-IP products (IP total / general IP)
    # - ip_visible: visible side (IP v.l.)
    # - ip_non_visible: non-visible/lower side (IP v.a.)
    CanonicalSpec("ip_rating", ["ip total", "ip (total)", "ip totale", "total ip", "ip rating", "ip degree", "grado ip"]),
    CanonicalSpec("ip_visible", ["ip v l", "ip v.l.", "ip vl", "ip visible", "visible ip"]),
    CanonicalSpec("ip_non_visible", ["ip v a", "ip v.a.", "ip va", "ip non visible", "non visible ip", "rear ip", "back ip"]),
    CanonicalSpec("ik_rating", ["ik rating", "ik", "grado ik"]),
    CanonicalSpec("mounting_type", ["mounting", "installation", "installazione", "montaggio"]),
    CanonicalSpec("housing_material", ["housing material", "material", "materiale", "corpo"]),
    CanonicalSpec("shape", ["shape", "forma"]),
    CanonicalSpec("housing_color",    ["Colour - Housing", "Color - Housing", "Housing color", "colore", "finitura"]),
    CanonicalSpec("protection_class", ["protection class", "classe di protezione", "class"]),
    CanonicalSpec("luminaire_height", ["Luminaire height", "height", "H", "altezza"]),
    CanonicalSpec("luminaire_width",  ["Luminaire Width", "luminaire width", "width", "W", "larghezza"]),
    CanonicalSpec("luminaire_length", ["Luminaire length", "luminaire length", "length", "L", "lunghezza"]),
    CanonicalSpec("diameter",         ["Diameter", "Ã˜", "diametro"]),

    # Lighting
    CanonicalSpec("lumen_output", ["luminous flux", "lumen", "lm", "flusso", "flusso luminoso"]),
    CanonicalSpec("efficacy_lm_w", ["luminous efficacy", "efficacy", "lm/w", "lm w", "efficienza lm/w"]),
    CanonicalSpec("beam_angle_deg", ["beam angle", "angolo fascio", "angle", "degrees", "deg"]),
    CanonicalSpec("beam_type", ["beam", "distribution", "ottica", "distribuzione"]),
    CanonicalSpec("asymmetry", ["asymmetry", "asymmetric", "asimmetria", "asimmetrico"]),
    CanonicalSpec("cct_k", ["color temperature", "cct", "kelvin", "k", "temperatura colore"]),
    CanonicalSpec("cri", ["color rendering", "cri", "ra", "resa cromatica"]),
    CanonicalSpec("ugr", ["ugr", "glare", "abbagliamento"]),
    CanonicalSpec("sdcm", ["sdcm", "macadam"]),



   
]

def _norm_key(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", ""):
        return ""
    return s

def _first_word(name: str) -> str:
    s = _norm_key(name).lower()
    return s.split()[0] if s else ""


FAMILY_NAME_ALIASES = {
    "road lighting": "Street lighting",
}


def _normalize_family_name(value) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return ""
    text = re.sub(r"\s+", " ", text)
    alias = FAMILY_NAME_ALIASES.get(text.lower())
    if alias:
        return alias
    return text


def _normalize_ip_value(value) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    if not text or text in {"NAN", "NONE"}:
        return ""
    text = text.replace("IPX", "IP0")
    m = re.search(r"(>=|<=|>|<)?IP([0-9X]{2})", text)
    if m:
        op = m.group(1) or ""
        code = m.group(2).replace("X", "0")
        return f"{op}IP{code}"
    m = re.search(r"([0-9]{2})", text)
    if m:
        return f"IP{m.group(1)}"
    return str(value or "").strip()


def _normalize_ik_value(value) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    if not text or text in {"NAN", "NONE"}:
        return ""
    m = re.search(r"(>=|<=|>|<)?IK(\d{1,2})", text)
    if m:
        op = m.group(1) or ""
        return f"{op}IK{str(int(m.group(2))).zfill(2)}"
    m = re.search(r"(\d{1,2})", text)
    if m:
        return f"IK{str(int(m.group(1))).zfill(2)}"
    return str(value or "").strip()


def _normalize_cct_value(value) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return ""
    m = re.search(r"(\d{3,5})", text.replace(" ", ""))
    if not m:
        return text
    return f"{int(m.group(1))}K"


def _normalize_numeric_measure(value, unit: str = "") -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return ""
    num = _extract_first_number(text)
    if num is None:
        return text
    if abs(float(num) - round(float(num))) <= 1e-9:
        num_text = str(int(round(float(num))))
    else:
        num_text = f"{float(num):.2f}".rstrip("0").rstrip(".")
    return f"{num_text} {unit}".strip()

def load_family_map(path: str) -> dict:
    """Load family mapping from Excel file"""
    print(f"ðŸ“‚ Loading family map from: {path}")
    print(f"   File exists: {os.path.exists(path)}")
    fm = pd.read_excel(path, engine="openpyxl")
    fm.columns = [str(c).strip() for c in fm.columns]

    print(f"   Columns found: {list(fm.columns)}")

    # Your file uses: Product name | family | Short product code
    if "family" not in fm.columns or "Short product code" not in fm.columns:
        raise ValueError("family_map.xlsx must contain columns: 'family' and 'Short product code'")

    fm["FamilyKey"] = fm["Short product code"].apply(_norm_key)
    # If Short code missing, fallback to first word of Product name
    missing = fm["FamilyKey"] == ""
    fm.loc[missing, "FamilyKey"] = fm.loc[missing, "Product name"].apply(_first_word)

    fm["Family"] = fm["family"].apply(_normalize_family_name)

    fm = fm[(fm["FamilyKey"] != "") & (fm["Family"] != "")]
    print(f"   Loaded {len(fm)} mappings")
    # Keep family text exactly as in file (first occurrence wins, case-insensitive key).
    out = {}
    for _, r in fm.iterrows():
        k = str(r["FamilyKey"]).strip().lower()
        v = str(r["Family"]).strip()
        if k and v and k not in out:
            out[k] = v
    return out

# -----------------------------
# Loader
# -----------------------------

# 
def load_products(
    xlsx_path: str,
    family_map_path: str | None = None,
    *,
    min_score: int = 12,
    verbose: bool = True,
) -> pd.DataFrame:
    """Main function to load products from Excel"""
    df = pd.read_excel(xlsx_path, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    column_map, rankings = build_column_map(df.columns.tolist(), CANON_SPECS, min_score=min_score)

    if verbose:
        print("\n=== COLUMN MAP (auto-detected) ===")
        for spec in CANON_SPECS:
            if spec.key in column_map:
                print(f"{spec.key:22s} -> {column_map[spec.key]}")
            else:
                print(f"{spec.key:22s} -> (MISSING) candidates={rankings.get(spec.key)}")

    out = pd.DataFrame()
    for spec in CANON_SPECS:
        src = column_map.get(spec.key)
        out[spec.key] = df[src] if src else None

    # Fallback/merge for products that expose separate IP values by side:
    # Priority for canonical ip_rating:
    # 1) IP total (single-IP product)
    # 2) IP visible side (IP v.l.)
    # 3) IP non-visible side (IP v.a.)
    headers = df.columns.tolist()
    headers_norm_map = {_norm(h): h for h in headers}
    ip_total_col = _pick_first_matching_column(
        headers,
        include_any=["ip"],
        require_all=["total"],
    )
    ip_visible_col = headers_norm_map.get("ip v l")  # IP v.l. -> visible side
    ip_non_visible_col = headers_norm_map.get("ip v a")  # IP v.a. -> non-visible/lower side

    if not ip_visible_col:
        ip_visible_col = _pick_first_matching_column(headers, include_any=["ip"], require_all=["visible"])
    if not ip_non_visible_col:
        ip_non_visible_col = _pick_first_matching_column(headers, include_any=["ip"], require_all=["non", "visible"])
    if not ip_non_visible_col:
        ip_non_visible_col = _pick_first_matching_column(headers, include_any=["ip"], require_all=["rear"])
    if not ip_non_visible_col:
        ip_non_visible_col = _pick_first_matching_column(headers, include_any=["ip"], require_all=["back"])
    if not ip_total_col:
        ip_total_col = headers_norm_map.get("ip total")

    if "ip_rating" in out.columns:
        # Build canonical ip_rating deterministically from side-specific sources:
        # 1) IP total (single-IP products)
        # 2) IP visible side (IP v.l.)
        # 3) IP non-visible side (IP v.a.)
        # Finally, keep previously mapped generic ip_rating only if still missing.
        ip_canonical = pd.Series([""] * len(out), index=out.index, dtype="string")

        if ip_total_col and ip_total_col in df.columns:
            src = df[ip_total_col].astype(str).replace("nan", "").fillna("")
            miss = ip_canonical.astype(str).str.strip().eq("")
            ip_canonical.loc[miss] = src.loc[miss]
        if ip_visible_col and ip_visible_col in df.columns:
            src = df[ip_visible_col].astype(str).replace("nan", "").fillna("")
            miss = ip_canonical.astype(str).str.strip().eq("")
            ip_canonical.loc[miss] = src.loc[miss]
        if ip_non_visible_col and ip_non_visible_col in df.columns:
            src = df[ip_non_visible_col].astype(str).replace("nan", "").fillna("")
            miss = ip_canonical.astype(str).str.strip().eq("")
            ip_canonical.loc[miss] = src.loc[miss]

        # Fallback to whatever was mapped as generic ip_rating if still empty.
        ip_existing = out["ip_rating"].astype(str).replace("nan", "").fillna("")
        miss = ip_canonical.astype(str).str.strip().eq("")
        ip_canonical.loc[miss] = ip_existing.loc[miss]
        out["ip_rating"] = ip_canonical
        if verbose and (ip_total_col or ip_visible_col or ip_non_visible_col):
            print(
                "IP columns mapping:"
                f" total={ip_total_col!r}, visible={ip_visible_col!r}, non_visible={ip_non_visible_col!r}"
            )

    # Base cleanup
    out["product_code"] = out["product_code"].astype(str).fillna("").str.strip()
    out["product_name"] = out["product_name"].astype(str).fillna("").str.strip()

    # Remove rows without code
    out = out[out["product_code"] != ""].reset_index(drop=True)

    def _num(s: pd.Series) -> pd.Series:
        x = s.astype(str).str.extract(r"(-?\d+(?:\.\d+)?)")[0]
        return pd.to_numeric(x, errors="coerce")
    
    # ---- Convert % columns
    if "failure_rate_pct" in out.columns:
        out["failure_rate_pct"] = _num(out["failure_rate_pct"])

    if "lumen_maintenance_pct" in out.columns:
        out["lumen_maintenance_pct"] = _num(out["lumen_maintenance_pct"])

    # ---- Compute lumen_output if possible (optional) ----
    if "efficacy_lm_w" in out.columns and "power_max_w" in out.columns:
        eff = _num(out["efficacy_lm_w"])      # "96 lm/W" -> 96
        pwr = _num(out["power_max_w"])        # "15 W" -> 15
        out["lumen_output"] = eff * pwr       # lm

    # ---- Apply family mapping from Excel table (ALWAYS) ----
    FAMILY_MAP_PATH = str(family_map_path or "").strip() or os.getenv(
        "FAMILY_MAP_XLSX",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "family_map.xlsx"))
    )
    if verbose:
        print(f"ðŸ§­ Using family map: {FAMILY_MAP_PATH} (exists={os.path.exists(FAMILY_MAP_PATH)})")

    try:
        fam_map = load_family_map(FAMILY_MAP_PATH)
        if verbose:
            print(f"ðŸ·ï¸ family_map loaded OK: {len(fam_map)} keys")
    except Exception as e:
        fam_map = {}
        print(f"âŒ family_map load FAILED: {e}")
        import traceback
        traceback.print_exc()

    # ---- CREA product_family SOLO DAL MAPPING ----
    # Rule: short_product_code, otherwise first word of product_name.
    out['family_key'] = out['short_product_code'].astype(str).str.lower().str.strip()
    
    # Applica il mapping
    out['product_family'] = out['family_key'].map(fam_map)
    
    # If missing, fallback to first word of product_name
    missing_mask = out['product_family'].isna()
    if missing_mask.any():
        out.loc[missing_mask, 'family_key'] = out.loc[missing_mask, 'product_name'].apply(_first_word)
        out.loc[missing_mask, 'product_family'] = out.loc[missing_mask, 'family_key'].map(fam_map)
    
    # Keep only rows with mapped family. This removes accessories/control gear
    # and any unmapped lines from families/facets/search.
    before_rows = len(out)
    out = out[out['product_family'].notna()].copy()
    out['product_family'] = out['product_family'].apply(_normalize_family_name)
    dropped_unmapped = before_rows - len(out)
    if verbose and dropped_unmapped:
        print(f"ðŸ§¹ Dropped {dropped_unmapped} rows with unmapped family (strict map-only mode)")

    # ---- Exclude non-luminaire lines (accessories, drivers, control gear, etc.) ----
    def _norm_text(x) -> str:
        s = "" if x is None else str(x)
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        return s.lower().strip()

    exclude_keywords = [
        "accessor",      # accessory, accessories
        "driver",        # led driver
        "alimentator",   # alimentatore
        "control gear",
        "gear tray",
        "converter",
        "trasformat",    # trasformatore
        "battery pack",
        "spare part",
        "ricambio",
        "kit emergency",
        "emergency kit",
    ]

    fam_txt = out["product_family"].apply(_norm_text) if "product_family" in out.columns else pd.Series("", index=out.index)
    name_txt = out["product_name"].apply(_norm_text) if "product_name" in out.columns else pd.Series("", index=out.index)
    etim_txt = out["etim_search_key"].apply(_norm_text) if "etim_search_key" in out.columns else pd.Series("", index=out.index)

    excl_mask = pd.Series(False, index=out.index)
    for kw in exclude_keywords:
        excl_mask = (
            excl_mask
            | fam_txt.str.contains(re.escape(kw), na=False)
            | name_txt.str.contains(re.escape(kw), na=False)
            | etim_txt.str.contains(re.escape(kw), na=False)
        )

    removed_count = int(excl_mask.sum())
    if removed_count:
        out = out.loc[~excl_mask].reset_index(drop=True)
        if verbose:
            print(f"ðŸ§¹ Excluded {removed_count} accessory/driver rows from dataset")
    
    # Rimuovi la colonna temporanea
    out = out.drop(columns=['family_key'])
    
    if verbose:
        unique_families = out['product_family'].unique()
        print(f"ðŸ·ï¸ Created product_family with {len(unique_families)} unique values")
        print(f"   Sample families: {list(unique_families)[:10]}")

    if verbose:
        print("\n=== FIELD COVERAGE (non-null %) ===")
        for c in [
            "ip_rating",
            "ik_rating",
            "power_max_w",
            "lumen_output",
            "cct_k",
            "beam_angle_deg",
            "control_protocol",
            "emergency_present",
            "product_family",  # Aggiunto
        ]:
            if c in out.columns:
                pct = 100.0 * (out[c].notna().sum() / max(len(out), 1))
                print(f"{c:20s}: {pct:6.1f}%")

    if "ip_rating" in out.columns:
        out["ip_rating"] = out["ip_rating"].apply(_normalize_ip_value)
    if "ip_visible" in out.columns:
        out["ip_visible"] = out["ip_visible"].apply(_normalize_ip_value)
    if "ip_non_visible" in out.columns:
        out["ip_non_visible"] = out["ip_non_visible"].apply(_normalize_ip_value)
    if "ik_rating" in out.columns:
        out["ik_rating"] = out["ik_rating"].apply(_normalize_ik_value)
    if "cct_k" in out.columns:
        out["cct_k"] = out["cct_k"].apply(_normalize_cct_value)
    for numeric_col, unit in [
        ("power_max_w", "W"),
        ("power_min_w", "W"),
        ("lumen_output", "lm"),
        ("efficacy_lm_w", "lm/W"),
        ("warranty_years", "yr"),
    ]:
        if numeric_col in out.columns:
            out[numeric_col] = out[numeric_col].apply(lambda v, _unit=unit: _normalize_numeric_measure(v, _unit))
    
    # ---- UGR numeric extraction (for clean filtering in SQLite) ----
    if "ugr" in out.columns:
        out["ugr_value"] = out["ugr"].apply(_extract_ugr_value)
        out["ugr_op"] = out["ugr"].apply(_extract_ugr_op)

    if "ik_rating" in out.columns:
        out["ik_value"] = out["ik_rating"].apply(_extract_ik_value)

    # ---- Numeric helper columns for SQLite filtering ----
    # efficacy: "127 lm/W" -> 127
    if "efficacy_lm_w" in out.columns:
        out["efficacy_value"] = out["efficacy_lm_w"].apply(_extract_first_number)

    # lumen_output: could be string/float -> numeric
    if "lumen_output" in out.columns:
        out["lumen_output_value"] = out["lumen_output"].apply(_extract_first_number)

    # power: "33 W" -> 33
    if "power_max_w" in out.columns:
        out["power_max_value"] = out["power_max_w"].apply(_extract_first_number)
    if "power_min_w" in out.columns:
        out["power_min_value"] = out["power_min_w"].apply(_extract_first_number)

    # lifetime: "50000 hr" -> 50000
    if "lifetime_hours" in out.columns:
        out["lifetime_h_value"] = out["lifetime_hours"].apply(_extract_hours)
    if "led_rated_life_h" in out.columns:
        out["led_rated_life_value"] = out["led_rated_life_h"].apply(_extract_hours)

    # warranty: "5 yr" -> 5
    if "warranty_years" in out.columns:
        out["warranty_y_value"] = out["warranty_years"].apply(_extract_first_number)

    # ---- Computed shape (for SQLite filtering/sorting/use in UI) ----
    # Priority:
    # 1) diameter > 0 -> round
    # 2) diameter == 0 OR diameter missing, with length/width available:
    #    - length == width -> square
    #    - length != width -> rectangular
    # Only overwrite missing/blank shapes from source.
    if "shape" not in out.columns:
        out["shape"] = None
    if {"diameter", "luminaire_length", "luminaire_width"}.intersection(set(out.columns)):
        dia_num = out["diameter"].apply(_extract_first_number) if "diameter" in out.columns else pd.Series([None] * len(out), index=out.index)
        len_num = out["luminaire_length"].apply(_extract_first_number) if "luminaire_length" in out.columns else pd.Series([None] * len(out), index=out.index)
        wid_num = out["luminaire_width"].apply(_extract_first_number) if "luminaire_width" in out.columns else pd.Series([None] * len(out), index=out.index)

        def _computed_shape(row) -> Optional[str]:
            d = row["__dia"]
            l = row["__len"]
            w = row["__wid"]
            if d is not None and not pd.isna(d) and float(d) > 0.0:
                return "round"
            if l is None or w is None or pd.isna(l) or pd.isna(w):
                return None
            # In source data, non-round products often have diameter blank instead of 0.
            return "square" if abs(float(l) - float(w)) <= 1e-9 else "rectangular"

        tmp_shape = pd.DataFrame({"__dia": dia_num, "__len": len_num, "__wid": wid_num}, index=out.index)
        computed_shape = tmp_shape.apply(_computed_shape, axis=1)
        shape_blank = out["shape"].isna() | out["shape"].astype(str).str.strip().eq("") | out["shape"].astype(str).str.lower().eq("nan")
        out.loc[shape_blank, "shape"] = computed_shape[shape_blank]

    # ---- Price merge (Order code -> PRICE) ----
    PRICE_LIST_PATH = os.getenv(
        "PRICE_LIST_XLSX",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "Price list.xlsx")),
    )
    price_df = _load_price_map(PRICE_LIST_PATH, verbose=verbose)
    if not price_df.empty:
        out["compact_code"] = out["product_code"].apply(_compact_code)
        out = out.merge(price_df[["compact_code", "price"]], on="compact_code", how="left")
        out = out.drop(columns=["compact_code"])
        if verbose:
            matched = int(out["price"].notna().sum())
            print(f"💶 Price merge: matched {matched}/{len(out)} products from {PRICE_LIST_PATH}")
    else:
        out["price"] = None
        if verbose:
            print(f"⚠️ Price merge skipped: no valid rows in {PRICE_LIST_PATH}")

    return out

