import re
from typing import Dict, Any, Optional

# --------------------------------------------
# Simple Family synonyms (local fallback)
# Keep keys aligned with "product_family" expected values.
# --------------------------------------------
FAMILY_SYNONYMS = {
    "road lighting": [
        "road lighting", "road light", "street lighting", "street light",
        "streetlamp", "street lamp", "road luminaire", "street luminaire",
    ],
    "waterproof": [
        "waterproof", "water proof", "watertight", "weatherproof",
        "vapor tight", "vapour tight", "bulkhead",
    ],
    "floodlight": ["floodlight", "flood light", "projector", "proiettore"],
    "post top": ["post top", "post-top", "lantern", "lanterna"],
    "bollard": ["bollard", "paletto", "garden bollard", "pathway bollard"],
    "highbay": ["highbay", "high bay", "ufo", "warehouse", "capannone"],
    "wall": ["wall", "parete", "wallpack", "wall pack", "applique"],
    "ceiling/wall": ["ceiling/wall", "ceiling wall", "plafoniera"],
    "linear": ["linear", "lineare", "strip", "batten"],
    "downlight": ["downlight", "incasso", "recessed"],
    "uplight": ["uplight", "uplighter", "up light"],
    "spike": ["spike", "picchetto", "garden spike"],
    "panels": ["panel", "panels", "pannello", "pannelli"],
    "emergency": ["emergency", "emergenza", "exit", "safety"],
}

_SIZE_CONTEXT_HINTS = (
    "panel", "panels", "pannello", "pannelli", "incasso", "recessed",
    "ceiling tile", "modulare", "modular", "troffer",
)

def _to_mm(v: str, unit: Optional[str], text: str) -> Optional[float]:
    try:
        num = float(str(v).replace(",", "."))
    except Exception:
        return None

    u = (unit or "").strip().lower()
    if u in ("mm", "millimeter", "millimeters", "millimetre", "millimetres", "millimetri", "millimetro"):
        return num
    if u in ("cm", "centimeter", "centimeters", "centimetre", "centimetres", "centimetri", "centimetro"):
        return num * 10.0
    if u in ("m", "meter", "meters", "metre", "metres", "metro", "metri"):
        return num * 1000.0

    # No explicit unit: domain heuristic
    # In lighting tenders, "60x60" almost always means cm panel module => 600x600 mm.
    t = (text or "").lower()
    panelish = any(h in t for h in _SIZE_CONTEXT_HINTS)
    if num <= 200:
        return num * 10.0 if panelish or num <= 120 else num
    if num <= 3000:
        return num
    return None

def _parse_size_filters(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not text:
        return out

    t = str(text).lower()
    # Accept: 60x60, 60 x 60, 60 per 60, 60 by 60, 600mm x 600mm, 60cm x 60cm
    m = re.search(
        r"\b(\d+(?:[.,]\d+)?)\s*"
        r"(mm|cm|m|millimetri|millimeters|millimetres|centimetri|centimeters|centimetres|metri|meters|metres)?\s*"
        r"(?:x|×|\*|by|per)\s*"
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(mm|cm|m|millimetri|millimeters|millimetres|centimetri|centimeters|centimetres|metri|meters|metres)?\b",
        t,
    )
    if not m:
        return out

    a, ua, b, ub = m.group(1), m.group(2), m.group(3), m.group(4)
    # If only one side has unit, apply same unit to both.
    u1 = ua or ub
    u2 = ub or ua
    mm1 = _to_mm(a, u1, t)
    mm2 = _to_mm(b, u2, t)
    if not mm1 or not mm2:
        return out

    # Tolerance band to handle minor catalog variants.
    tol1 = max(10, int(round(mm1 * 0.02)))
    tol2 = max(10, int(round(mm2 * 0.02)))
    lo1, hi1 = int(round(mm1 - tol1)), int(round(mm1 + tol1))
    lo2, hi2 = int(round(mm2 - tol2)), int(round(mm2 + tol2))

    # Orientation-agnostic pair: compare shortest/longest side.
    side1 = f"{min(lo1, hi1)}-{max(lo1, hi1)}"
    side2 = f"{min(lo2, hi2)}-{max(lo2, hi2)}"
    a = float(mm1)
    b = float(mm2)
    if a <= b:
        out["luminaire_size_min"] = side1
        out["luminaire_size_max"] = side2
    else:
        out["luminaire_size_min"] = side2
        out["luminaire_size_max"] = side1
    return out

def _infer_family(text: str) -> Optional[str]:
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None

    best = None
    best_len = 0
    for fam, syns in FAMILY_SYNONYMS.items():
        for s in syns:
            s2 = (s or "").lower().strip()
            if s2 and s2 in t and len(s2) > best_len:
                best = fam
                best_len = len(s2)
    return best


def local_text_to_filters(text: str) -> Dict[str, Any]:
    t = (text or "").lower()
    filters: Dict[str, Any] = {}


    t = re.sub(r"\b(bigger than|greater than|more than|over)\b", ">", t)
    t = re.sub(r"\b(less than|under|below)\b", "<", t)
    t = re.sub(r"\bat least\b", ">=", t)
    t = re.sub(r"\bat most\b", "<=", t)

    # -------------------------
    # Family
    # -------------------------
    fam = _infer_family(text)
    if fam:
        filters["product_family"] = fam

    # -------------------------
    # Dimensions from natural language (IT/EN)
    # Examples: "60x60", "60 per 60", "600mm x 600mm", "60 by 60 cm"
    # -------------------------
    filters.update(_parse_size_filters(text))
    if ("luminaire_size_min" in filters or "luminaire_size_max" in filters):
        t_size = (text or "").lower()
        if any(k in t_size for k in ("panel", "pannello", "pannelli", "troffer", "modulare", "modular")):
            filters["product_family"] = "panels"

    # -------------------------
    # IP rating
    # Accept: IP65, ip 65, IPX5 (X -> 0), >=IP65, > IP54 ...
    # Normalize to ">=IP65" or keep comparator if present
    # -------------------------
    tt = t.replace(" ", "")
    # comparator (>= <= > <)
    m = re.search(r"(>=|<=|>|<)ip([0-9x]{2})\b", tt)
    if m:
        op = m.group(1)
        d = m.group(2).upper().replace("X", "0")
        if re.fullmatch(r"\d{2}", d):
            filters["ip_rating"] = f"{op}IP{d}"
    else:
        # plain
        m = re.search(r"ip([0-9x]{2})", tt)
        if m:
            d = m.group(1).upper().replace("X", "0")
            if re.fullmatch(r"\d{2}", d):
                filters["ip_rating"] = f">=IP{d}"

    # -------------------------
    # IK rating
    # Accept: IK08, IK8, >=IK10, > IK09
    # Normalize to ">=IK08" (minimum if no comparator)
    # -------------------------
    m = re.search(r"(>=|<=|>|<)?\s*ik\s*([0-9]{1,2})\b", t)
    if m:
        op = m.group(1) or ">="
        d = m.group(2).zfill(2)
        filters["ik_rating"] = f"{op}IK{d}"

    # -------------------------
    # Outdoor context defaults
    # Business rule: "outdoor" implies high IP and high IK
    # (unless user already specified explicit IP/IK values)
    # -------------------------
    if any(w in t for w in ["outdoor", "esterno", "external", "outside"]):
        filters.setdefault("ip_rating", ">=IP65")
        filters.setdefault("ik_rating", ">=IK08")

    # -------------------------
    # CCT (Kelvin): 4000K, 3000 K
    # -------------------------
    m = re.search(r"\b(\d{3,5})\s*k\b", t)
    if m:
        filters["cct_k"] = m.group(1)

    # -------------------------
    # DALI (control protocol)
    # Business rule: "DALI requested" => controllability YES
    # Keep both values to support mixed datasets (some rows store "dali", others "yes").
    # -------------------------
    if "dali" in t:
        filters["control_protocol"] = ["dali", "yes"]

    # -------------------------
    # Emergency present
    # -------------------------
    if any(w in t for w in ["emergency", "emergenza", "exit", "safety", "kit emergenza", "em kit"]):
        filters["emergency_present"] = "yes"

    # -------------------------
    # -------------------------
    # CRI (Ra)
    # Regola "migliorativo": più alto = migliore
    # - "CRI 80" => ">=80"
    # - "CRI >= 90" => ">=90"
    # - "Ra 80" => ">=80"
    # - "Ra > 80" => ">80"
    # -------------------------

    # 1) CRI con operatore (es: CRI>=80)
    m = re.search(r"\bcri\s*(>=|<=|>|<)\s*(\d{2})\b", t)
    if m:
        filters["cri"] = f"{m.group(1)}{m.group(2)}"
    else:
        # 2) CRI senza operatore (es: CRI 80) => default >=
        m = re.search(r"\bcri\s*(\d{2})\b", t)
        if m:
            filters["cri"] = f">={m.group(1)}"
        else:
            # 3) RA con operatore
            m = re.search(r"\bra\s*(>=|<=|>|<)\s*(\d{2})\b", t)
            if m:
                filters["cri"] = f"{m.group(1)}{m.group(2)}"
            else:
                # 4) RA senza operatore (Ra 80) => default >=
                m = re.search(r"\bra\s*(\d{2})\b", t)
                if m:
                    filters["cri"] = f">={m.group(1)}"


    # -------------------------
    # UGR
    # Regola "migliorativo": più basso = migliore
    # - "UGR 19" => "<=19"
    # - "UGR<19" => "<=19"
    # - "UGR<=22" resta "<=22"
    # -------------------------

    # 1) UGR con operatore
    m = re.search(r"\bugr\s*(<=|>=|<|>)\s*(\d+(?:\.\d+)?)\b", t)
    if m:
        op = m.group(1)
        num = m.group(2)

        # se l'utente scrive "<" lo trattiamo come "<=" (classe UGR)
        if op == "<":
            op = "<="
        filters["ugr"] = f"{op}{num}"
    else:
        # 2) UGR senza operatore (ugr 19) => default <=
        m = re.search(r"\bugr\s*(\d+(?:\.\d+)?)\b", t)
        if m:
            filters["ugr"] = f"<={m.group(1)}"




    # -------------------------
    # Power: 10-30W or 30W or >=40W
    # Normalize into power_min_w / power_max_w where possible
    # -------------------------
    m = re.search(r"\b(\d{1,4})\s*-\s*(\d{1,4})\s*w\b", t)
    if m:
        filters["power_min_w"] = m.group(1)
        filters["power_max_w"] = m.group(2)
    else:
        m = re.search(r"\b(>=|<=|>|<)\s*(\d{1,4})\s*w\b", t)
        if m:
            # treat as power_max_w expression (your DB search supports >= / <= etc.)
            filters["power_max_w"] = f"{m.group(1)}{m.group(2)}"
        else:
            m = re.search(r"\b(\d{1,4})\s*w\b", t)
            if m:
                filters["power_max_w"] = f">={m.group(1)}"

    # -------------------------
    # Lumen: 5000lm, >=5000 lm, 8000 lm
    # -------------------------
    # -------------------------
    # Lumen: 5000lm, >=5000 lm, >5000 lm, 8000 lm
    # -------------------------
    # -------------------------
    # Lumen: 5000lm, >=5000 lm, >5000 lm, 8000 lm
    # IMPORTANT: avoid catching "lm/w" (efficacy)
    # -------------------------
        m = re.search(r"(>=|<=|>|<)\s*(\d{3,6})\s*lm\b(?!\s*/\s*w)", t)
        if m:
            filters["lumen_output"] = f"{m.group(1)}{m.group(2)}"
        else:
            m = re.search(r"(\d{3,6})\s*lm\b(?!\s*/\s*w)", t)
            if m:
                filters["lumen_output"] = f">={m.group(1)}"



        # -------------------------
    # Efficacy: 120 lm/W, >=120 lm/w, > 120 lm per w
    # -------------------------
    # -------------------------
    # Efficacy: 120 lm/W, >=120 lm/w, >120lm/w
    # -------------------------
    # -------------------------
    # Efficacy: 120 lm/W, >=120 lm/w, >120lm/w
    # -------------------------
    m = re.search(r"(>=|<=|>|<)\s*(\d+(?:\.\d+)?)\s*lm\s*/\s*w\b", t)
    if m:
        filters["efficacy_lm_w"] = f"{m.group(1)}{m.group(2)}"
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*lm\s*/\s*w\b", t)
        if m:
            filters["efficacy_lm_w"] = f">={m.group(1)}"



    # -------------------------
    # Beam angle: 20° or 20deg
    # -------------------------
    m = re.search(r"\b(\d{1,3})\s*(?:°|deg)\b", t)
    if m:
        filters["beam_angle_deg"] = m.group(1)

    # -------------------------
    # Asymmetry
    # -------------------------
    if any(w in t for w in ["asymmetric", "asymmetry", "asimmetrico", "asimmetrica", "asimmetria"]):
        filters["asymmetry"] = "asymmetric"

    return filters

