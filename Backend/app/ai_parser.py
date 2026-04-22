import re
from typing import Any, Dict, Optional

# ============================================================
# FAMILY SYNONYMS (canonical -> variations)
# Keep this aligned with your facets families values.
# ============================================================
FAMILY_SYNONYMS: Dict[str, list[str]] = {
    "street lighting": [
        "road", "street", "stradale", "illuminazione stradale",
        "illuminazione pubblica", "public lighting", "roadway", "roadway lighting",
        "streetlight", "streetlights",
        "road light", "road lighting", "street light", "street lighting",
        "streetlamp", "street lamp", "road luminaire", "street luminaire",
    ],
    "waterproof": [
        "waterproof", "water proof", "watertight", "weatherproof",
        "weather proof", "water resistant", "stagna", "stagno",
        "vapor tight", "vapour tight", "bulkhead",
    ],
    "floodlight": ["floodlight", "floodlights", "flood light", "flood", "projector", "projector light", "proiettore", "proiettori", "faro", "fari"],
    "post top": ["post top", "post-top", "pole top", "lantern", "lanterna", "testa palo"],
    "bollard": ["bollard", "paletto", "paletto led", "garden bollard", "pathway bollard"],
    "highbay": ["highbay", "high-bay", "high bay", "ufo", "warehouse", "industrial", "capannone", "campana"],
    "wall": ["wall", "wall mounted", "parete", "wallpack", "wall pack", "applique"],
    "ceiling/wall": ["ceiling/wall", "ceiling wall", "ceiling", "soffitto", "plafoniera"],
    "strip": ["strip", "led strip", "light strip", "tape light", "led tape", "flex strip"],
    "linear": ["linear", "lineare", "linear light", "linea", "batten"],
    "downlight": ["downlight", "down light", "incasso", "incassato", "recessed downlight"],
    "uplight": [
        "uplight", "uplighter", "up light",
        "in-ground", "in ground", "inground",
        "ground recessed", "ground-recessed",
        "buried", "buried light", "in-ground recessed", "recessed uplight",
    ],
    "spike": ["spike", "picchetto", "garden spike"],
    "panels": ["panel", "panel light", "panel led", "panels", "pannello", "pannello led", "pannelli"],
    "emergency": ["emergency", "emergenza", "exit", "exit sign", "battery", "batteria", "autonomy", "autonomia", "backup", "back-up"],
}

_FAMILY_TOKEN_STOPWORDS = {
    "light", "lighting", "luminaire", "lamp", "garden", "pathway",
    "ceiling", "wall", "proof", "tight",
    "recessed", "recess",
}

def _norm_text(s: str) -> str:
    s = (s or "").lower()
    # keep / + - for things like lm/W and ranges 30-40
    s = re.sub(r"[^a-z0-9\s/+\-<>.=]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _norm_words(s: str) -> list[str]:
    return [w for w in _norm_text(s).replace("/", " ").split(" ") if w]


def _normalize_unit_aliases(text: str) -> str:
    t = _norm_text(text)
    # Normalize common lumen/lm variants and typos
    t = re.sub(r"(?:(?<=\d)|\b)(?:lm|lumen|lumens|lumn|lumns|lumnes|lummen|lummens)\b", "lm", t)
    # Normalize common watt/w variants and typos
    t = re.sub(r"(?:(?<=\d)|\b)(?:w|watt|watts|wat|wats|waat|waats)\b", "w", t)
    # Normalize efficacy phrasing: "lumens per watt", "lm per w", etc.
    t = re.sub(r"\blm\s*(?:/|per|pr)\s*w\b", "lm/w", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _parse_loose_int_token(raw: str) -> Optional[int]:
    s = str(raw or "").strip().lower()
    if not s:
        return None
    s = s.replace(" ", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)k", s)
    if m:
        return int(round(float(m.group(1)) * 1000))
    if re.fullmatch(r"\d{1,3}(?:['.,]\d{3})+", s):
        return int(re.sub(r"['.,]", "", s))
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None


def _parse_shape(text: str) -> Optional[str]:
    t = _norm_text(text)
    aliases = [
        ("round", ["round", "circular", "circle", "rotondo", "rotonda", "circolare", "tondo"]),
        ("square", ["square", "quadrato", "quadrata"]),
        ("rectangular", ["rectangular", "rectangle", "rettangolare"]),
    ]
    for shape, words in aliases:
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", t):
                return shape
    if re.search(r"\b(?:rectangul|retangular|rettangolar)\w*\b", t):
        return "rectangular"
    if re.search(r"\b(?:squar|sqare)\w*\b", t):
        return "square"
    if re.search(r"\b(?:roun|circl)\w*\b", t):
        return "round"
    return None


def _tok_base(tok: str) -> str:
    t = (tok or "").strip().lower()
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith("es"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s"):
        return t[:-1]
    return t


def _is_close_token(a: str, b: str) -> bool:
    a = _tok_base(a)
    b = _tok_base(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4:
        return False
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    i = j = mism = 0
    while i < len(s) and j < len(l):
        if s[i] == l[j]:
            i += 1
            j += 1
        else:
            mism += 1
            if mism > 1:
                return False
            j += 1
    return True

def _infer_family(text: str) -> Optional[str]:
    t = _norm_text(text)
    if not t:
        return None
    # Ground-recessed wording is a strong uplight cue and should override generic "recessed".
    if re.search(r"\b(?:in[\s-]?ground|inground|ground[\s-]?recess(?:ed)?|buried)\b", t):
        return "uplight"

    q_tokens = [_tok_base(w) for w in _norm_words(t)]
    q_token_set = set(q_tokens)
    candidates: list[tuple[int, str]] = []
    for fam, syns in FAMILY_SYNONYMS.items():
        fam_best = 0
        for s in syns:
            s2 = _norm_text(s)
            if s2 and s2 in t:
                fam_best = max(fam_best, 1000 + len(s2))
                continue
            syn_tokens = [_tok_base(w) for w in _norm_words(s)]
            syn_tokens = [w for w in syn_tokens if w and w not in _FAMILY_TOKEN_STOPWORDS]
            overlap = [w for w in syn_tokens if w in q_token_set]
            if overlap:
                fam_best = max(fam_best, 100 + len(max(overlap, key=len)))
                continue
            fuzzy = [
                st for st in syn_tokens
                if any(_is_close_token(qt, st) for qt in q_tokens)
            ]
            if fuzzy:
                fam_best = max(fam_best, 80 + len(max(fuzzy, key=len)))
        if fam_best:
            candidates.append((fam_best, fam))

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
    t = _normalize_unit_aliases(text)

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
    t = _normalize_unit_aliases(text)
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


def _parse_lifetime_hours(text: str) -> Optional[str]:
    raw = str(text or "").lower()
    m = re.search(
        r"\b(\d{1,3}(?:['.,]\d{3})+|\d+(?:\.\d+)?k|\d{4,7})\s*(?:h|hr|hrs|hour|hours)\b",
        raw
    )
    if not m:
        return None
    hours = _parse_loose_int_token(m.group(1))
    if not hours:
        return None
    return f">={hours}"


def _parse_lumen_maintenance_lb(text: str) -> Optional[str]:
    t = _norm_text(text)
    m = re.search(r"\bl\s*(\d{2,3})\s*b\s*(\d{1,2})\b", t)
    if not m:
        return None
    return f">={int(m.group(1))}"

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

    lmaint = _parse_lumen_maintenance_lb(text)
    if lmaint:
        soft["lumen_maintenance_pct"] = lmaint

    life = _parse_lifetime_hours(text)
    if life:
        soft["lifetime_hours"] = life

    shp = _parse_shape(text)
    if shp:
        soft["shape"] = shp

    return {"hard_filters": hard, "soft_filters": soft}
