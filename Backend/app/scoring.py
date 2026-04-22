import math
import os
import re
from typing import Any, Dict, List, Tuple
from app.runtime_config import cfg_float, cfg_list
from app.schema import ALLOWED_FILTER_KEYS

DIMENSION_TOLERANCE = cfg_float("scoring.dimension_tolerance", 0.05)
DIMENSION_KEYS = set(cfg_list("main.dimension_keys", [
    "diameter",
    "luminaire_length",
    "luminaire_width",
    "luminaire_height",
]))


def _cfg_score_float(env_name: str, cfg_key: str, default: float) -> float:
    raw = str(os.getenv(env_name, "")).strip()
    if raw:
        try:
            return float(raw)
        except Exception:
            pass
    return cfg_float(cfg_key, default)


def _field_weights() -> Dict[str, float]:
    defaults = {
        "cct_k": _cfg_score_float("SCORING_WEIGHT_CCT_K", "scoring.weight.cct_k", 1.0),
        "power_max_w": _cfg_score_float("SCORING_WEIGHT_POWER_MAX_W", "scoring.weight.power_max_w", 1.2),
        "lumen_output": _cfg_score_float("SCORING_WEIGHT_LUMEN_OUTPUT", "scoring.weight.lumen_output", 1.5),
        "efficacy_lm_w": _cfg_score_float("SCORING_WEIGHT_EFFICACY_LM_W", "scoring.weight.efficacy_lm_w", 1.3),
        "warranty_years": _cfg_score_float("SCORING_WEIGHT_WARRANTY_YEARS", "scoring.weight.warranty_years", 0.7),
        "lifetime_hours": _cfg_score_float("SCORING_WEIGHT_LIFETIME_HOURS", "scoring.weight.lifetime_hours", 0.8),
        "led_rated_life_h": _cfg_score_float("SCORING_WEIGHT_LED_RATED_LIFE_H", "scoring.weight.led_rated_life_h", 0.8),
        "lumen_maintenance_pct": _cfg_score_float("SCORING_WEIGHT_LUMEN_MAINTENANCE_PCT", "scoring.weight.lumen_maintenance_pct", 0.7),
        "beam_angle_deg": _cfg_score_float("SCORING_WEIGHT_BEAM_ANGLE_DEG", "scoring.weight.beam_angle_deg", 0.8),
        "ugr": _cfg_score_float("SCORING_WEIGHT_UGR", "scoring.weight.ugr", 0.6),
        "cri": _cfg_score_float("SCORING_WEIGHT_CRI", "scoring.weight.cri", 0.8),
        "asymmetry": _cfg_score_float("SCORING_WEIGHT_ASYMMETRY", "scoring.weight.asymmetry", 0.6),
        "product_family": _cfg_score_float("SCORING_WEIGHT_PRODUCT_FAMILY", "scoring.weight.product_family", 4.0),
    }
    field_weights: Dict[str, float] = {}
    for key in ALLOWED_FILTER_KEYS:
        default_weight = float(defaults.get(key, 1.0))
        field_weights[key] = _cfg_score_float(
            f"SCORING_WEIGHT_{key.upper()}",
            f"scoring.weight.{key}",
            default_weight,
        )
    return field_weights


def _missing_penalty() -> float:
    return _cfg_score_float("SCORING_MISSING_PENALTY", "scoring.missing_penalty", 0.50)


def _deviation_penalty() -> float:
    return _cfg_score_float("SCORING_DEVIATION_PENALTY", "scoring.deviation_penalty", 1.00)


def _family_missing_multiplier() -> float:
    return _cfg_score_float("SCORING_FAMILY_MISSING_MULTIPLIER", "scoring.family_missing_multiplier", 2.0)


def _family_mismatch_multiplier() -> float:
    return _cfg_score_float("SCORING_FAMILY_MISMATCH_MULTIPLIER", "scoring.family_mismatch_multiplier", 3.0)

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


def _norm_shape_value(x: Any) -> str:
    s = _norm_str(x).lower()
    if not s:
        return ""
    if any(tok in s for tok in ("rectangular", "rectangle", "rettangolar", "rectangul", "retangular")):
        return "rectangular"
    if any(tok in s for tok in ("square", "quadrat", "carr", "cuadrad", "kwadrat")):
        return "square"
    if any(tok in s for tok in ("round", "circular", "circle", "rotond", "circl")):
        return "round"
    return s

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

def _match_numeric(got: Any, wanted: Any, rel_tol: float = 0.0) -> tuple[bool, str]:
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
        tol_lo = abs(lo) * rel_tol
        tol_hi = abs(hi) * rel_tol
        lo_adj = lo - tol_lo
        hi_adj = hi + tol_hi
        ok = (g >= lo_adj) and (g <= hi_adj)
        return (ok, f"wanted {lo}-{hi} (tol {rel_tol:.0%}), got {g}")
    tol = abs(val) * rel_tol
    if op == ">=":
        return (g >= (val - tol), f"wanted >= {val} (tol {rel_tol:.0%}), got {g}")
    if op == "<=":
        return (g <= (val + tol), f"wanted <= {val} (tol {rel_tol:.0%}), got {g}")
    if op == ">":
        return (g > (val - tol), f"wanted > {val} (tol {rel_tol:.0%}), got {g}")
    if op == "<":
        return (g < (val + tol), f"wanted < {val} (tol {rel_tol:.0%}), got {g}")
    # "="
    eq_tol = max(tol, 1e-9)
    return (abs(g - val) <= eq_tol, f"wanted = {val} (+/-{eq_tol}), got {g}")

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

    if k == "product_name_contains":
        g_s = _norm_str(got).lower()
        w_s = _norm_str(wanted).lower()
        if not g_s:
            return (False, "missing 'product_name'")
        if not w_s:
            return (True, "product_name no constraint")
        if w_s in g_s:
            return (True, "product_name contains")
        return (False, f"product_name mismatch: wanted contains '{wanted}' got='{got}'")

    if k in {"ip_rating", "ip_visible", "ip_non_visible"}:
        return _match_ip(got, wanted)
    if k == "ik_rating":
        return _match_ik(got, wanted)

    # numeric fields
    if k in {
        "power_max_w", "power_min_w", "lumen_output", "efficacy_lm_w",
        "beam_angle_deg", "cri", "ugr",
        "warranty_years", "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct",
        "diameter", "luminaire_length", "luminaire_width", "luminaire_height",
        "ambient_temp_min_c", "ambient_temp_max_c",
    }:
        if k == "ambient_temp_min_c":
            s = _norm_str(wanted).replace(" ", "")
            m = re.match(r"^(>=|>|<=|<|=)?(-?\d+(?:\.\d+)?)$", s)
            if m:
                op = m.group(1) or "<="
                num = m.group(2)
                # Min ambient capability: lower/colder values are better.
                if op == ">=":
                    wanted = f"<={num}"
                elif op == ">":
                    wanted = f"<{num}"
                elif op == "=":
                    wanted = f"<={num}"
        tol = DIMENSION_TOLERANCE if k in DIMENSION_KEYS else 0.0
        return _match_numeric(got, wanted, rel_tol=tol)

    # cct: compare numeric part
    if k == "cct_k":
        g = _num_from_any(got)
        w = _num_from_any(wanted)
        if g is None or w is None:
            return (False, f"cct missing/unparsable wanted='{wanted}' got='{got}'")
        return (int(g) == int(w), f"wanted {int(w)}K got {int(g)}K")

    if k == "control_protocol":
        g_s = _norm_str(got).lower()
        w_s = _norm_str(wanted).lower()
        if not g_s:
            return (False, f"missing '{k}'")
        if not w_s:
            return (True, f"{k} no constraint")
        if w_s == "dali":
            w_s = "yes"
        if g_s == "dali":
            g_s = "yes"
        if g_s == w_s or w_s in g_s:
            return (True, f"{k} match")
        return (False, f"{k} mismatch: wanted='{wanted}' got='{got}'")

    if k == "shape":
        g_s = _norm_shape_value(got)
        w_s = _norm_shape_value(wanted)
        if not g_s:
            return (False, f"missing '{k}'")
        if not w_s:
            return (True, f"{k} no constraint")
        if g_s == w_s:
            return (True, f"{k} canonical match")
        return (False, f"{k} mismatch: wanted '{wanted}', got '{got}'")

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
    field_weights = _field_weights()
    missing_penalty = _missing_penalty()
    deviation_penalty = _deviation_penalty()
    family_missing_mult = _family_missing_multiplier()
    family_mismatch_mult = _family_mismatch_multiplier()
    matched: Dict[str, Any] = {}
    deviations: List[str] = []
    missing: List[str] = []

    # 1) Hard: must pass
    for k, wanted in (hard_filters or {}).items():
        got = prod.get("product_name") if k == "product_name_contains" else prod.get(k)

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
        w = float(field_weights.get(k, 1.0))
        total_weight += w

        got = prod.get("product_name") if k == "product_name_contains" else prod.get(k)
        if _norm_str(got) == "":
            miss_mult = family_missing_mult if k == "product_family" else 1.0
            penalty += w * missing_penalty * miss_mult
            missing.append(k)
            continue

        ok, why = _match_with_multivalue(k, got, wanted)
        if ok:
            matched[k] = got
        else:
            dev_mult = family_mismatch_mult if k == "product_family" else 1.0
            penalty += w * deviation_penalty * dev_mult
            deviations.append(f"{k}: {why}")

    # If no soft filters, hard-only match is perfect
    if total_weight <= 0:
        return 1.0, matched, deviations, missing

    score = 1.0 - (penalty / total_weight)
    score = max(0.0, min(1.0, score))
    return score, matched, deviations, missing
