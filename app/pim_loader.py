# app/pim_loader.py
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple
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


def _extract_ugr_value(x):
    if x is None:
        return None
    s = str(x).lower().replace(" ", "")
    # examples: "ugr<19,according...", "ugr<=22", "ugr16"
    m = re.search(r"ugr(<=|>=|<|>)?(\d{1,2})", s)
    if m:
        return int(m.group(2))
    m = re.search(r"(\d{1,2})", s)
    return int(m.group(1)) if m else None

def _extract_ugr_op(x):
    if x is None:
        return None
    s = str(x).lower().replace(" ", "")
    m = re.search(r"ugr(<=|>=|<|>)", s)
    return m.group(1) if m else None

def _extract_ik_value(x):
    import re
    s = "" if x is None else str(x).upper()
    m = re.search(r"IK\s*(\d{1,2})", s)
    if not m:
        m = re.search(r"(\d{1,2})", s)
    return float(m.group(1)) if m else None




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
    CanonicalSpec("manufacturer", ["Manufacturer", "Manufacturer name", "Brand", "Marca"]),
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
    CanonicalSpec("emergency_present", ["emergency power supply", "emergency", "emergenza", "em kit", "kit emergenza"]),
    CanonicalSpec("emergency_duration_min", ["emergency duration", "duration", "durata emergenza", "min"]),

    # Mechanical
    CanonicalSpec("ip_rating", ["ip (total)", "ip total", "ip rating", "ip degree", "ip", "grado ip"]),
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

def _normalize_order_code(x) -> str:
    s = "" if x is None else str(x)
    s = s.strip().upper().replace(" ", "")
    if s.lower() in ("", "nan", "none"):
        return ""
    return s

def _load_price_map(path: str, verbose: bool = True) -> Dict[str, float]:
    if not path or not os.path.exists(path):
        if verbose:
            print(f"ℹ️ Price list not found: {path}")
        return {}

    try:
        xls = pd.ExcelFile(path, engine="openpyxl")
    except Exception as e:
        print(f"⚠️ Failed to open price list '{path}': {e}")
        return {}

    out: Dict[str, float] = {}
    code_candidates = {"order code", "order_code", "ordercode", "codice ordine"}
    price_candidates = {"price", "prezzo", "list price", "unit price"}

    for sheet in xls.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
        except Exception:
            continue
        if df is None or df.empty:
            continue

        raw_cols = [str(c).strip() for c in df.columns]
        norm_to_raw = {_norm(c): c for c in raw_cols}
        code_col = None
        price_col = None

        for cand in code_candidates:
            c = norm_to_raw.get(_norm(cand))
            if c:
                code_col = c
                break
        for cand in price_candidates:
            c = norm_to_raw.get(_norm(cand))
            if c:
                price_col = c
                break

        if not code_col or not price_col:
            continue

        for _, row in df[[code_col, price_col]].iterrows():
            code = _normalize_order_code(row.get(code_col))
            if not code:
                continue
            num = _extract_first_number(row.get(price_col))
            if num is None:
                continue
            out[code] = float(num)

    if verbose:
        print(f"💶 Loaded {len(out)} prices from: {path}")
    return out

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

    fm["Family"] = fm["family"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

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
def load_products(xlsx_path: str, *, min_score: int = 12, verbose: bool = True) -> pd.DataFrame:
    """Main function to load products from Excel"""
    df = pd.read_excel(xlsx_path, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    column_map, rankings = build_column_map(df.columns.tolist(), CANON_SPECS, min_score=min_score)

    # Prefer explicit manufacturer headers to avoid fuzzy mis-mapping to boolean columns.
    norm_to_raw = {_norm(c): c for c in df.columns}
    for k in ("manufacturer", "manufacturer name", "brand", "marca"):
        raw = norm_to_raw.get(_norm(k))
        if raw:
            column_map["manufacturer"] = raw
            break

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

    # Base cleanup
    out["product_code"] = out["product_code"].astype(str).fillna("").str.strip()
    out["product_name"] = out["product_name"].astype(str).fillna("").str.strip()

    # Remove rows without code
    out = out[out["product_code"] != ""].reset_index(drop=True)

    # Defensive cleanup for manufacturer: avoid boolean-like wrong mappings.
    if "manufacturer" in out.columns:
        s = out["manufacturer"].astype(str).str.strip()
        low = s.str.lower()
        non_empty = low[(low != "") & (low != "nan") & (low != "none")]
        bool_like = {"yes", "no", "true", "false", "0", "1"}
        if not non_empty.empty and non_empty.isin(bool_like).mean() > 0.8:
            out["manufacturer"] = None

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
    FAMILY_MAP_PATH = os.getenv(
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
    out['product_family'] = out['product_family'].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
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

    # orientation-agnostic dimensions (short/long side)
    if "luminaire_length" in out.columns and "luminaire_width" in out.columns:
        lnum = out["luminaire_length"].apply(_extract_first_number)
        wnum = out["luminaire_width"].apply(_extract_first_number)
        out["luminaire_size_min"] = pd.concat([lnum, wnum], axis=1).min(axis=1, skipna=True)
        out["luminaire_size_max"] = pd.concat([lnum, wnum], axis=1).max(axis=1, skipna=True)

    # ---- Merge prices by order code (hidden field for sorting) ----
    price_list_path = os.getenv(
        "PRICE_LIST_XLSX",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "Price list.xlsx")),
    )
    price_map = _load_price_map(price_list_path, verbose=verbose)
    if price_map:
        key = out["product_code"].apply(_normalize_order_code)
        out["price_value"] = key.map(price_map)
        out["price"] = out["price_value"]
    else:
        out["price_value"] = None
        out["price"] = None

    return out

