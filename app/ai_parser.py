import re
from typing import Any, Dict, Optional

# ============================================================
# FAMILY SYNONYMS (canonical -> variations)
# Keep this aligned with your facets families values.
# ============================================================
FAMILY_SYNONYMS: Dict[str, list[str]] = {
    "road lighting": [
        "road light", "road lighting", "street light", "street lighting",
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

def _norm_text(s: str) -> str:
    s = (s or "").lower()
    # keep / + - for things like lm/W and ranges 30-40
    s = re.sub(r"[^a-z0-9\s/+\-<>.=]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _infer_family(text: str) -> Optional[str]:
    t = _norm_text(text)
    if not t:
        return None

    candidates: list[tuple[int, str]] = []
    for fam, syns in FAMILY_SYNONYMS.items():
        for s in syns:
            s2 = _norm_text(s)
            if s2 and s2 in t:
                candidates.append((len(s2), fam))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]

def _two_digits(n: str) -> str:
    n = str(n).strip()
    return n if len(n) == 2 else n.zfill(2)

def _parse_ip_expr(text: str) -> Optional[str]:
    """
    Accept:
      IP65, ip 65
      >=IP65, >= ip65
      IPX5, IPx8 (X treated as 0 => IP05, IP08)
    Returns normalized filter string like ">=IP54"
    """
    t = _norm_text(text).replace(" ", "")

    # comparator
    m = re.search(r"(>=|<=|>|<)ip([0-9xX]{2})\b", t)
    if m:
        op = m.group(1)
        d = m.group(2).upper().replace("X", "0")
        if not re.fullmatch(r"\d{2}", d):
            return None
        d = _two_digits(d)
        # For IP we mainly use >= semantics; keep other ops if present
        return f"{op}IP{d}"

    # plain ip
    m = re.search(r"\bip([0-9xX]{2})\b", t)
    if m:
        d = m.group(1).upper().replace("X", "0")
        if not re.fullmatch(r"\d{2}", d):
            return None
        d = _two_digits(d)
        # IMPORTANT: requested IP should accept better IP (e.g. IP54 accepts IP65)
        return f">=IP{d}"

    return None

def _parse_ik_expr(text: str) -> Optional[str]:
    """
    Accept:
      IK08, IK8
      >=IK08, >= IK8
    Returns normalized filter string like ">=IK08"
    """
    t = _norm_text(text).replace(" ", "")

    m = re.search(r"(>=|<=|>|<)ik(\d{1,2})\b", t)
    if m:
        op = m.group(1)
        d = _two_digits(m.group(2))
        return f"{op}IK{d}"

    m = re.search(r"\bik(\d{1,2})\b", t)
    if m:
        d = _two_digits(m.group(1))
        # requested IK should accept better IK
        return f">=IK{d}"

    return None

def _parse_cct(text: str) -> Optional[str]:
    t = _norm_text(text)
    m = re.search(r"\b(\d{3,5})\s*k\b", t)
    if m:
        return f"{int(m.group(1))} K"
    return None

def _parse_range_or_cmp(text: str, unit_regex: str, allow_decimals: bool = True) -> Optional[str]:
    """
    Parses values like:
      30-40 W, >=40W, 5000 lm, around 40W
    Returns string:
      "30-40", ">=40", "32.0-48.0", "40"
    """
    t = _norm_text(text)

    # range
    num = r"\d+(?:\.\d+)?" if allow_decimals else r"\d+"
    m = re.search(rf"\b({num})\s*-\s*({num})\s*{unit_regex}\b", t)
    if m:
        a = float(m.group(1)); b = float(m.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        if lo.is_integer() and hi.is_integer():
            return f"{int(lo)}-{int(hi)}"
        return f"{lo}-{hi}"

    # comparator
    m = re.search(rf"\b(>=|<=|>|<)\s*({num})\s*{unit_regex}\b", t)
    if m:
        op, v = m.group(1), m.group(2)
        return f"{op}{v}"

    # around/approx
    m = re.search(rf"\b(around|circa|approx|approximately)\s*({num})\s*{unit_regex}\b", t)
    if m:
        v = float(m.group(2))
        # power: +/-20%, lumen: +/-20%, efficacy: +/-10% (handled by caller if needed)
        lo = v * 0.8
        hi = v * 1.2
        # keep .1
        return f"{round(lo,1)}-{round(hi,1)}"

    # plain number
    m = re.search(rf"\b({num})\s*{unit_regex}\b", t)
    if m:
        return m.group(1)

    return None

def _parse_efficacy(text: str) -> Optional[str]:
    t = _norm_text(text)
    # try strict "lm/w"
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*lm\s*/\s*w\b", t)
    if m:
        return m.group(1)
    # comparator
    m = re.search(r"\b(>=|<=|>|<)\s*(\d+(?:\.\d+)?)\s*lm\s*/\s*w\b", t)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    # around
    m = re.search(r"\b(around|circa|approx|approximately)\s*(\d+(?:\.\d+)?)\s*lm\s*/\s*w\b", t)
    if m:
        v = float(m.group(2))
        lo = round(v * 0.9, 1)
        hi = round(v * 1.1, 1)
        return f"{lo}-{hi}"
    return None

def text_to_filters(text: str) -> Dict[str, Any]:
    """
    Returns:
      {"hard_filters": {...}, "soft_filters": {...}}
    Hard: ip_rating, ik_rating, product_family
    Soft: cct_k, power_max_w, lumen_output, efficacy_lm_w
    """
    hard: Dict[str, Any] = {}
    soft: Dict[str, Any] = {}

    if not text:
        return {"hard_filters": hard, "soft_filters": soft}

    fam = _infer_family(text)
    if fam:
        hard["product_family"] = fam

    ip = _parse_ip_expr(text)
    if ip:
        hard["ip_rating"] = ip

    ik = _parse_ik_expr(text)
    if ik:
        hard["ik_rating"] = ik

    cct = _parse_cct(text)
    if cct:
        soft["cct_k"] = cct

    # power in W
    pwr = _parse_range_or_cmp(text, unit_regex=r"w", allow_decimals=True)
    if pwr:
        # normalize ranges to "lo-hi" floats if needed
        if "-" in str(pwr) and not any(op in str(pwr) for op in (">=", "<=", ">", "<")):
            a, b = str(pwr).split("-", 1)
            lo = float(a); hi = float(b)
            soft["power_max_w"] = f"{lo}-{hi}"
        else:
            soft["power_max_w"] = str(pwr)

    # lumens
    lm = _parse_range_or_cmp(text, unit_regex=r"lm", allow_decimals=False)
    if lm:
        soft["lumen_output"] = str(lm)

    eff = _parse_efficacy(text)
    if eff:
        soft["efficacy_lm_w"] = str(eff)

    return {"hard_filters": hard, "soft_filters": soft}
