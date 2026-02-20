import re
from typing import Dict, Any, Optional

# ============================================================
# FAMILY SYNONYMS (canonical -> variations)
# ============================================================

FAMILY_SYNONYMS = {
    "road lighting": [
        "road light", "road lighting", "street light", "street lighting",
        "road luminaire", "street luminaire",
    ],
    "waterproof": [
        "waterproof", "water proof", "watertight", "weatherproof",
        "vapor tight", "vapour tight",
    ],
    "floodlight": ["floodlight", "flood light", "projector"],
    "post top": ["post top", "post-top", "lantern"],
    "bollard": ["bollard", "garden bollard", "pathway bollard"],
    "highbay": ["highbay", "high bay", "ufo", "warehouse"],
    "wall": ["wall", "wallpack", "wall pack", "applique"],
    "ceiling/wall": ["ceiling/wall", "ceiling wall", "plafoniera"],
    "linear": ["linear", "strip", "batten"],
    "downlight": ["downlight", "recessed"],
    "uplight": ["uplight", "uplighter", "up light"],
    "spike": ["spike", "garden spike"],
    "panels": ["panel", "panels"],
    "emergency": ["emergency", "exit", "safety"],
}

# ============================================================
# TEXT NORMALIZATION
# ============================================================

def _norm_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s/+-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ============================================================
# FAMILY INFERENCE
# ============================================================

def infer_family_from_text(text: str) -> Optional[str]:
    t = _norm_text(text)
    if not t:
        return None

    candidates = []

    for fam, syns in FAMILY_SYNONYMS.items():
        for s in syns:
            s2 = _norm_text(s)
            if s2 and s2 in t:
                candidates.append((len(s2), fam))

    if not candidates:
        return None

    # longest match wins
    candidates.sort(reverse=True)
    return candidates[0][1]

# ============================================================
# MAIN LOCAL PARSER
# ============================================================

def local_text_to_filters(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    t = _norm_text(text)

    if not t:
        return out

    # --------------------------------------------------------
    # 1️⃣ FAMILY detection
    # --------------------------------------------------------

    fam = infer_family_from_text(t)
    if fam:
        out["product_family"] = fam


    lm_match = re.search(r"(\d{3,6})\s*lm", t)
    if lm_match:
        val = float(lm_match.group(1))
        out["lumen_output"] = f"{val*0.8}-{val*1.2}"
    # --------------------------------------------------------
    # 2️⃣ IP detection (hard filter) - STRICT: only IP + 2 digits
    # supports: IP65, ip66, >=IP65
    # ignores: IP8, IP5, IPX8, etc.
    # --------------------------------------------------------

    ip_match = re.search(r"(>=)?\s*ip\s*([0-9xX])([0-9xX])\b", t)
    if ip_match:
        d1 = ip_match.group(2).upper()
        d2 = ip_match.group(3).upper()

        ip_value = f"IP{d1}{d2}"

        if ip_match.group(1):
            out["ip_rating"] = f">={ip_value}"
        else:
            out["ip_rating"] = ip_value

    # --------------------------------------------------------
    # 3️⃣ CCT detection (soft filter)
    # supports: 4000K, 3000 K
    # --------------------------------------------------------

    cct_match = re.search(r"(\d{4})\s*k", t)
    if cct_match:
        out["cct_k"] = f"{cct_match.group(1)} K"

    # --------------------------------------------------------
    # 4️⃣ POWER detection (soft filter)
    # supports:
    #   40W
    #   around 40W
    #   30-40W
    #   >=40W
    # --------------------------------------------------------

    # range 30-40W
    range_match = re.search(r"(\d+)\s*-\s*(\d+)\s*w", t)
    if range_match:
        a = float(range_match.group(1))
        b = float(range_match.group(2))
        lo, hi = sorted([a, b])
        out["power_max_w"] = f"{lo}-{hi}"

    # >=40W or >40W
    elif re.search(r"(>=|>)\s*(\d+)\s*w", t):
        m = re.search(r"(>=|>)\s*(\d+)\s*w", t)
        out["power_max_w"] = f">={m.group(2)}"

    # <=40W or <40W
    elif re.search(r"(<=|<)\s*(\d+)\s*w", t):
        m = re.search(r"(<=|<)\s*(\d+)\s*w", t)
        out["power_max_w"] = f"<={m.group(2)}"

    # around 40W
    elif re.search(r"around\s+(\d+)\s*w", t):
        m = re.search(r"around\s+(\d+)\s*w", t)
        val = float(m.group(1))
        lo = max(0, val - 8)
        hi = val + 8
        out["power_max_w"] = f"{lo}-{hi}"

    # simple 40W
    elif re.search(r"(\d+)\s*w", t):
        m = re.search(r"(\d+)\s*w", t)
        val = float(m.group(1))
        lo = max(0, val - 5)
        hi = val + 5
        out["power_max_w"] = f"{lo}-{hi}"

    return out
# ============================================================
# PUBLIC AI ENTRYPOINT (used by main.py)
# ============================================================

def text_to_filters(text: str) -> Dict[str, Any]:
    """
    Main AI parser entrypoint expected by main.py.
    Returns structure compatible with:
    {
        "hard_filters": {...},
        "soft_filters": {...}
    }
    """

    parsed = local_text_to_filters(text)

    hard = {}
    soft = {}

    # Hard filters
    if "ip_rating" in parsed:
        hard["ip_rating"] = parsed["ip_rating"]

    if "product_family" in parsed:
        hard["product_family"] = parsed["product_family"]



    # Everything else → soft
    for k, v in parsed.items():
        if k not in hard:
            soft[k] = v

    return {
        "hard_filters": hard,
        "soft_filters": soft,
    }
