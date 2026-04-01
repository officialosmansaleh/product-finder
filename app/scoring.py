import math
import re
from typing import Any, Dict, List, Tuple

# ------------------------------------------------------------
# Scoring config
# ------------------------------------------------------------
FIELD_WEIGHTS: Dict[str, float] = {
    # key "importance" for soft filters
    "cct_k": 1.0,
    "power_max_w": 1.2,
    "lumen_output": 1.5,
    "efficacy_lm_w": 1.3,
    "warranty_years": 0.7,
    "lifetime_hours": 0.8,
    "led_rated_life_h": 0.8,
    "lumen_maintenance_pct": 0.7,
    "beam_angle_deg": 0.8,
    "diameter": 0.9,
    "luminaire_height": 0.9,
    "luminaire_width": 1.1,
    "luminaire_length": 1.1,
    "luminaire_size_min": 1.2,
    "luminaire_size_max": 1.2,
    "ugr": 0.6,
    "cri": 0.8,
    "asymmetry": 0.6,
}

MISSING_PENALTY = 0.50      # missing soft field
DEVIATION_PENALTY = 1.00    # mismatch soft field

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _norm_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and math.isnan(x):
        return ""
    return str(x).strip()

def _num_from_any(x: Any) -> float | None:
    s = _norm_str(x).lower()
    if not s:
        return None
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None

def _parse_ip(x: Any) -> int | None:
    """
    Accept: 65.0, "65", "IP65", "IPX8" -> 8, "IP08" -> 8
    Strategy: treat X as 0, then take 2 digits after IP if present.
    """
    if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x)):
        try:
            return int(float(x))
        except Exception:
            return None

    s = _norm_str(x).lower().replace(" ", "")
    if not s:
        return None

    s = s.replace("ipx", "ip0")  # IPX8 -> IP08
    m = re.search(r"ip(\d{2})", s)
    if m:
        return int(m.group(1))

    # raw numeric like "65.0"
    m = re.search(r"^(\d{2})(?:\.0+)?$", s)
    if m:
        return int(m.group(1))

    return None

def _parse_ik(x: Any) -> int | None:
    if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x)):
        try:
            return int(float(x))
        except Exception:
            return None

    s = _norm_str(x).lower().replace(" ", "")
    if not s:
        return None

    m = re.search(r"ik(\d{1,2})", s)
    if m:
        return int(m.group(1))

    m = re.search(r"^(\d{1,2})(?:\.0+)?$", s)
    if m:
        return int(m.group(1))

    return None

def _parse_cmp_expr(expr: Any) -> tuple[str, float] | None:
    """
    Parse expressions like:
      ">=40", "<= 60", "30-40", "40"
    Return (op, value) where op in {"range","<=",">=", "<",">","="}
    For "range" value is encoded as (lo,hi) in a tuple via float packing? We'll return None and handle separately.
    """
    s = _norm_str(expr).replace(" ", "")
    if not s:
        return None

    # range
    if "-" in s and not s.startswith("-"):
        parts = s.split("-", 1)
        try:
            lo = float(parts[0]); hi = float(parts[1])
            if lo > hi:
                lo, hi = hi, lo
            return ("range", (lo, hi))  # type: ignore
        except Exception:
            pass

    m = re.match(r"^(>=|<=|>|<|=)?(-?\d+(?:\.\d+)?)$", s)
    if m:
        op = m.group(1) or "="
        return (op, float(m.group(2)))

    return None

def _match_numeric(got: Any, wanted: Any) -> tuple[bool, str]:
    g = _num_from_any(got)
    if g is None:
        return (False, f"missing numeric (got='{got}')")

    # wanted could be range/cmp/number
    parsed = _parse_cmp_expr(wanted)
    if not parsed:
        # if can't parse wanted, fallback to string contains
        return (_norm_str(wanted).lower() in _norm_str(got).lower(), f"numeric str mismatch: wanted='{wanted}' got='{got}'")

    op, val = parsed
    if op == "range":
        lo, hi = val  # type: ignore
        ok = (g >= lo) and (g <= hi)
        return (ok, f"wanted {lo}-{hi}, got {g}")
    if op == ">=":
        return (g >= val, f"wanted >= {val}, got {g}")
    if op == "<=":
        return (g <= val, f"wanted <= {val}, got {g}")
    if op == ">":
        return (g > val, f"wanted > {val}, got {g}")
    if op == "<":
        return (g < val, f"wanted < {val}, got {g}")
    # "="
    return (g == val, f"wanted = {val}, got {g}")

def _match_ip(got: Any, wanted: Any) -> tuple[bool, str]:
    g = _parse_ip(got)
    if g is None:
        return (False, f"ip missing (got='{got}')")

    w_s = _norm_str(wanted).upper().replace(" ", "")
    w_s = w_s.replace("IPX", "IP0")
    # accept ">=IP54" or "IP54" (treated as minimum)
    m = re.search(r"(>=|<=|>|<)?IP(\d{2})", w_s)
    if not m:
        return (False, f"ip wanted unparsable: '{wanted}'")
    op = m.group(1) or ">="  # default MINIMUM
    w = int(m.group(2))

    if op == ">=":
        return (g >= w, f"wanted >=IP{w:02d}, got IP{g:02d}")
    if op == "<=":
        return (g <= w, f"wanted <=IP{w:02d}, got IP{g:02d}")
    if op == ">":
        return (g > w, f"wanted >IP{w:02d}, got IP{g:02d}")
    if op == "<":
        return (g < w, f"wanted <IP{w:02d}, got IP{g:02d}")
    return (g == w, f"wanted IP{w:02d}, got IP{g:02d}")

def _match_ik(got: Any, wanted: Any) -> tuple[bool, str]:
    g = _parse_ik(got)
    if g is None:
        return (False, f"ik missing (got='{got}')")

    w_s = _norm_str(wanted).upper().replace(" ", "")
    m = re.search(r"(>=|<=|>|<)?IK(\d{1,2})", w_s)
    if not m:
        return (False, f"ik wanted unparsable: '{wanted}'")
    op = m.group(1) or ">="  # default MINIMUM
    w = int(m.group(2))

    if op == ">=":
        return (g >= w, f"wanted >=IK{w:02d}, got IK{g:02d}")
    if op == "<=":
        return (g <= w, f"wanted <=IK{w:02d}, got IK{g:02d}")
    if op == ">":
        return (g > w, f"wanted >IK{w:02d}, got IK{g:02d}")
    if op == "<":
        return (g < w, f"wanted <IK{w:02d}, got IK{g:02d}")
    return (g == w, f"wanted IK{w:02d}, got IK{g:02d}")

def _match_value(key: str, got: Any, wanted: Any) -> tuple[bool, str]:
    k = (key or "").strip()

    if k == "ip_rating":
        return _match_ip(got, wanted)
    if k == "ik_rating":
        return _match_ik(got, wanted)

    # numeric fields
    if k in {
        "power_max_w", "power_min_w", "lumen_output", "efficacy_lm_w",
        "beam_angle_deg", "cri", "ugr",
        "warranty_years", "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct",
        "diameter", "luminaire_height", "luminaire_width", "luminaire_length",
        "luminaire_size_min", "luminaire_size_max",
    }:
        return _match_numeric(got, wanted)

    # cct: compare numeric part
    if k == "cct_k":
        g = _num_from_any(got)
        w = _num_from_any(wanted)
        if g is None or w is None:
            return (False, f"cct missing/unparsable wanted='{wanted}' got='{got}'")
        return (int(g) == int(w), f"wanted {int(w)}K got {int(g)}K")

    # strings: case-insensitive contains/equality
    g_s = _norm_str(got).lower()
    w_s = _norm_str(wanted).lower()
    if not g_s:
        return (False, f"missing '{k}'")
    if not w_s:
        return (True, f"{k} no constraint")
    if g_s == w_s:
        return (True, f"{k} exact")
    if w_s in g_s:
        return (True, f"{k} contains")
    return (False, f"{k} mismatch: wanted='{wanted}' got='{got}'")

def _match_with_multivalue(key: str, got: Any, wanted: Any) -> tuple[bool, str]:
    if isinstance(wanted, list):
        reasons: List[str] = []
        for one in wanted:
            ok, why = _match_value(key, got, one)
            if ok:
                return (True, why)
            reasons.append(why)
        if not reasons:
            return (False, f"{key} no values")
        return (False, " | ".join(reasons[:3]))
    return _match_value(key, got, wanted)

# ------------------------------------------------------------
# Main scoring
# ------------------------------------------------------------
def score_product(
    prod: Dict[str, Any],
    hard_filters: Dict[str, Any],
    soft_filters: Dict[str, Any],
) -> Tuple[float, Dict[str, Any], List[str], List[str]]:
    matched: Dict[str, Any] = {}
    deviations: List[str] = []
    missing: List[str] = []

    # 1) Hard: must pass
    for k, wanted in (hard_filters or {}).items():
        got = prod.get(k)

        if _norm_str(got) == "":
            missing.append(k)
            deviations.append(f"hard missing: {k}")
            return 0.0, matched, deviations, missing

        ok, why = _match_with_multivalue(k, got, wanted)
        if not ok:
            deviations.append(f"hard mismatch: {why}")
            return 0.0, matched, deviations, missing

        matched[k] = got

    # 2) Soft: weighted penalties
    total_weight = 0.0
    penalty = 0.0

    for k, wanted in (soft_filters or {}).items():
        w = float(FIELD_WEIGHTS.get(k, 1.0))
        total_weight += w

        got = prod.get(k)
        if _norm_str(got) == "":
            penalty += w * MISSING_PENALTY
            missing.append(k)
            continue

        ok, why = _match_with_multivalue(k, got, wanted)
        if ok:
            matched[k] = got
        else:
            penalty += w * DEVIATION_PENALTY
            deviations.append(why)

    # If no soft filters, hard-only match is perfect
    if total_weight <= 0:
        return 1.0, matched, deviations, missing

    score = 1.0 - (penalty / total_weight)
    score = max(0.0, min(1.0, score))
    return score, matched, deviations, missing
