from typing import Any, Dict, List, Tuple
from typing import Optional
import math
import re



# Weights: higher = more important in ranking
FIELD_WEIGHTS: Dict[str, float] = {
    "ip_rating": 2.0,
    "control_protocol": 1.6,
    "power_max_w": 1.4,
    "power_min_w": 1.2,
    "lumen_output": 1.4,
    "cct_k": 1.2,
    "beam_angle_deg": 1.0,
    "beam_type": 0.8,
    "asymmetry": 0.8,
    "cri": 1.0,
    "ugr": 1.0,
    "emergency_present": 1.2,
}

# Penalties are now weighted; these are per-weight-unit penalties
MISSING_PENALTY = 0.60
DEVIATION_PENALTY = 1.00




def _parse_ip_pair(val: str) -> Optional[Tuple[int, int]]:
    """
    Accepts: 'IP65', '65', '65.0', 'IPX5', 'IP5X', '>=IPX8'
    Returns (solid, water) with X treated as 0.
    """
    s = str(val).upper().strip()
    s = s.replace(" ", "")
    s = s.replace("X", "0")

    # pick first occurrence of two chars after optional IP
    m = re.search(r"IP?([0-9])([0-9])", s)
    if not m:
        # also support plain like "65.0"
        m2 = re.search(r"([0-9])([0-9])", s)
        if not m2:
            return None
        return int(m2.group(1)), int(m2.group(2))

    return int(m.group(1)), int(m.group(2))


def _parse_ik_int(val: str) -> Optional[int]:
    """
    Accepts: 'IK08', 'IK8', '08', '8'
    Returns integer (8).
    """
    s = str(val).upper().strip().replace(" ", "")
    m = re.search(r"IK?(\d{1,2})", s)
    if not m:
        return None
    return int(m.group(1))


def _is_nan(x: Any) -> bool:
    return isinstance(x, float) and math.isnan(x)


def _norm_str(x: Any) -> str:
    if x is None or _is_nan(x):
        return ""
    return str(x).strip().lower()


def _parse_int(x: Any) -> int | None:
    s = _norm_str(x)
    if not s:
        return None
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None


def _parse_float(x: Any) -> float | None:
    s = _norm_str(x)
    if not s:
        return None
    m = re.search(r"\d+(?:\.\d+)?", s.replace(",", "."))
    return float(m.group()) if m else None



def _parse_numeric_condition(wanted: str) -> tuple[str, float | None, float | None]:
    """
    Supports:
      - ">=5000", "<=40", ">20", "<30"
      - "30-40"
      - "4000"
    Returns: (mode, a, b)
      mode in {"ge","le","gt","lt","range","eq","invalid"}
    """
    w = _norm_str(wanted).replace(" ", "")
    if not w:
        return ("invalid", None, None)

    # range "30-40"
    if "-" in w:
        parts = w.split("-", 1)
        a = _parse_float(parts[0])
        b = _parse_float(parts[1])
        if a is None or b is None:
            return ("invalid", None, None)
        lo, hi = (a, b) if a <= b else (b, a)
        return ("range", lo, hi)

    # >=, <=, >, <
    m = re.match(r"^(>=|<=|>|<)(\d+(?:\.\d+)?)$", w)
    if m:
        op = m.group(1)
        val = float(m.group(2))
        return ({
            ">=": "ge",
            "<=": "le",
            ">": "gt",
            "<": "lt",
        }[op], val, None)

    # plain number -> eq
    val = _parse_float(w)
    if val is None:
        return ("invalid", None, None)
    return ("eq", val, None)


def _match_numeric(key: str, got: Any, wanted: Any) -> tuple[bool, str]:
    g = _parse_float(got)
    if g is None:
        return (False, f"{key} non leggibile: '{got}'")

    mode, a, b = _parse_numeric_condition(str(wanted))
    if mode == "invalid" or a is None:
        # fallback: string containment
        gs = _norm_str(got)
        ws = _norm_str(wanted)
        if ws in gs or gs == ws:
            return (True, "")
        return (False, f"{key}: richiesto '{wanted}', trovato '{got}'")

    if mode == "eq":
        return (g == a, f"{key} mismatch: want {a}, got {g}")
    if mode == "ge":
        return (g >= a, f"{key} mismatch: want >={a}, got {g}")
    if mode == "gt":
        return (g > a, f"{key} mismatch: want >{a}, got {g}")
    if mode == "le":
        return (g <= a, f"{key} mismatch: want <={a}, got {g}")
    if mode == "lt":
        return (g < a, f"{key} mismatch: want <{a}, got {g}")
    if mode == "range":
        assert b is not None
        return (a <= g <= b, f"{key} mismatch: want {a}-{b}, got {g}")

    return (False, f"{key} mismatch")


def _match_value(key: str, got: Any, wanted: Any) -> tuple[bool, str]:
    got_s = _norm_str(got)
    want_s = _norm_str(wanted)

    # --- string exact match (case-insensitive) ---
    # --- string exact match (case-insensitive) ---
    # IMPORTANT: do NOT use this for numeric-ish fields like IP/IK/CCT
    if key not in ("ip_rating", "ik_rating", "cct_k", "power_min_w", "power_max_w", "lumen_output", "beam_angle_deg", "cri", "ugr"):
        if isinstance(wanted, str) and isinstance(got, str):
            g = got.strip().lower()
            w = wanted.strip().lower()
            return (g == w), f"{key}: expected '{wanted}', got '{got}'"


    # CCT (exact integer)
    if key == "cct_k":
        g = _parse_int(got_s)
        w = _parse_int(want_s)
        if g is None or w is None:
            return (want_s in got_s or got_s == want_s, f"cct_k mismatch: want {wanted}, got {got}")
        return (g == w, f"cct_k mismatch: want {w}, got {g}")

    # --- IP rating ---
    if key == "ip_rating":
        # got: must be parseable (usually "65.0" from DB/SQLite)
        gp = _parse_ip_pair(got_s)
        if gp is None:
            return False, f"ip_rating non leggibile: '{got}'"
        got_solid, got_water = gp

        # wanted supports ">=IP65" or "IPX5" etc.
        wtxt = str(wanted).upper().strip().replace(" ", "")
        is_ge = wtxt.startswith(">=")
        if is_ge:
            wtxt = wtxt[2:].strip()

        wp = _parse_ip_pair(wtxt)
        if wp is None:
            return False, f"ip_rating filtro non valido: '{wanted}'"
        want_solid, want_water = wp

        # Treat wanted as MINIMUM requirement (both digits)
        ok = (got_solid >= want_solid) and (got_water >= want_water)
        if ok:
            return True, ""
        return False, f"ip_rating mismatch: want >=IP{want_solid}{want_water}, got IP{got_solid}{got_water}"



    
    if key == "ik_rating":
        g = _parse_ik_int(got_s)
        if g is None:
            return False, f"ik_rating non leggibile: '{got}'"

        wtxt = str(wanted).upper().strip().replace(" ", "")
        is_ge = wtxt.startswith(">=")
        if is_ge:
            wtxt = wtxt[2:].strip()

        w = _parse_ik_int(wtxt)
        if w is None:
            return False, f"ik_rating filtro non valido: '{wanted}'"

        # Treat wanted as MINIMUM requirement
        ok = g >= w
        if ok:
            return True, ""
        return False, f"ik_rating mismatch: want >=IK{w:02d}, got IK{g:02d}"

    

    # Numeric fields: accept >=, <=, ranges, exact
    if key in ("power_min_w", "power_max_w", "lumen_output", "beam_angle_deg", "cri", "ugr"):
        return _match_numeric(key, got, wanted)

    # Boolean-ish emergency_present
    if key == "emergency_present":
        # treat "yes/true/1" as true, "no/false/0" as false
        true_set = {"yes", "true", "1", "si", "sì"}
        false_set = {"no", "false", "0"}
        g = _norm_str(got)
        w = _norm_str(wanted)
        if w in true_set:
            return (g in true_set, f"emergency_present mismatch: want true, got '{got}'")
        if w in false_set:
            return (g in false_set, f"emergency_present mismatch: want false, got '{got}'")
        # fallback containment
        return (w in g or g == w, f"emergency_present mismatch: want '{wanted}', got '{got}'")

    # Fallback string match
    if want_s in got_s or got_s == want_s:
        return (True, "")
    return (False, f"{key}: richiesto '{wanted}', trovato '{got}'")


def score_product(
    prod: Dict[str, Any],
    hard_filters: Dict[str, Any],
    soft_filters: Dict[str, Any],
) -> Tuple[float, Dict[str, Any], List[str], List[str]]:

    matched: Dict[str, Any] = {}
    deviations: List[str] = []
    missing: List[str] = []

  


    # --- 1) Hard filters ---
    for k, wanted in (hard_filters or {}).items():
        got = prod.get(k)

        if _norm_str(got) == "":
            missing.append(k)
            deviations.append(f"hard missing: {k}")
            return 0.0, matched, deviations, missing

        ok, why = _match_value(k, got, wanted)
        if not ok:
            deviations.append(f"hard mismatch: {why}")
            return 0.0, matched, deviations, missing

        matched[k] = got

    # --- 2) Soft filters ---
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

        ok, why = _match_value(k, got, wanted)
        if ok:
            matched[k] = got
        else:
            penalty += w * DEVIATION_PENALTY
            deviations.append(why)

    if total_weight <= 0:
        return 1.0, matched, deviations, missing

    score = 1.0 - (penalty / total_weight)
    score = max(0.0, min(1.0, score))
    return score, matched, deviations, missing

