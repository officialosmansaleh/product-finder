import re
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from app.ai_service import infer_image_filters, infer_text_filters
from app.schema import ALLOWED_FILTER_KEYS

FAMILY_ALIASES = {
    "road lighting": "street lighting",
    "road": "street lighting",
    "roadway lighting": "street lighting",
}


class IntentFilters(BaseModel):
    product_family: Optional[str] = Field(None, description="e.g. highbay, street lighting, waterproof, floodlight, wall, linear, downlight, panels")
    ip_rating: Optional[str] = Field(None, description="e.g. >=IP65, >=IP66")
    ip_visible: Optional[str] = Field(None, description="IP visible side (IP v.l.), e.g. >=IP65")
    ip_non_visible: Optional[str] = Field(None, description="IP non-visible side (IP v.a.), e.g. >=IP20")
    ik_rating: Optional[str] = Field(None, description="e.g. >=IK08")
    asymmetry: Optional[str] = Field(None, description="e.g. asymmetric, asimmetrico, yes")
    shape: Optional[str] = Field(None, description="round, square, rectangular, linear")
    housing_color: Optional[str] = Field(None, description="white, black, grey, anthracite, etc.")
    ugr: Optional[str] = Field(None, description="e.g. <=19, <=22")
    cri: Optional[str] = Field(None, description="e.g. >=80, >=90")
    efficacy_lm_w: Optional[str] = Field(None, description="e.g. >=130, >=140")
    cct_k: Optional[str] = Field(None, description="e.g. 4000, 3000")
    power_min_w: Optional[str] = Field(None, description="minimum power, e.g. >=20")
    power_max_w: Optional[str] = Field(None, description="maximum/nominal power, e.g. <=40 or 20-40")
    beam_angle_deg: Optional[str] = Field(None, description="beam angle in degrees, e.g. 60, >=90")
    beam_type: Optional[str] = Field(None, description="narrow, medium, wide, flood, spot")
    control_protocol: Optional[str] = Field(None, description="generic control capability when interface is not specified")
    interface: Optional[str] = Field(None, description="e.g. dali, dmx, 1-10v, zhaga")
    emergency_present: Optional[str] = Field(None, description="yes/no")
    lifetime_hours: Optional[str] = Field(None, description="e.g. >=50000")
    led_rated_life_h: Optional[str] = Field(None, description="e.g. >=100000")
    warranty_years: Optional[str] = Field(None, description="e.g. >=5")
    lumen_maintenance_pct: Optional[str] = Field(None, description="L value from L80/L90, e.g. >=80")
    luminaire_height: Optional[str] = Field(None, description="height dimension in mm, e.g. <=80")
    luminaire_width: Optional[str] = Field(None, description="width dimension in mm, e.g. 100-200")
    luminaire_length: Optional[str] = Field(None, description="length dimension in mm, e.g. >=1200")
    diameter: Optional[str] = Field(None, description="diameter in mm, e.g. <=180")
    ambient_temp_min_c: Optional[str] = Field(None, description="minimum operating temperature capability, e.g. <=-20")
    ambient_temp_max_c: Optional[str] = Field(None, description="maximum operating temperature capability, e.g. >=40")
    confidence: Literal["low", "medium", "high"] = "medium"
    notes: Optional[str] = None


class ImageIntentFilters(BaseModel):
    product_family: Optional[str] = Field(None, description="Best matching fixture family from catalog vocabulary")
    shape: Optional[str] = Field(None, description="round, square, linear, rectangular, etc.")
    asymmetry: Optional[str] = Field(None, description="asymmetric when clearly visible")
    housing_color: Optional[str] = Field(None, description="white, black, grey, etc. only if obvious")
    confidence: Literal["low", "medium", "high"] = "medium"
    notes: Optional[str] = None


def _text_system_prompt(allowed_families: Optional[list[str]]) -> str:
    allowed_txt = ""
    if allowed_families:
        allowed_txt = (
            "Allowed product_family values (choose ONLY from these): "
            + ", ".join(allowed_families[:200])
            + ". "
        )
    return (
        "You convert a lighting application request into filters. "
        "The user query may be in English, Italian, French, Spanish, Portuguese, Russian, Arabic, Polish, Czech, Croatian, or Slovenian. "
        "Understand multilingual lighting terms and normalize them to the schema fields. "
        "Return only fields in the schema and leave uncertain fields null. "
        "IMPORTANT: Do NOT output lumen_output. "
        "Use only explicit user requirements; do not infer performance specs from product family alone. "
        "IMPORTANT: map DALI, DMX, 1-10V dimmer, and Zhaga/antenna requests to 'interface' (not 'control_protocol'). "
        "Normalize yes/no values to English. Normalize shape to round, square, rectangular, or linear. "
        + allowed_txt
        + "Use operators like >=, <= when appropriate (e.g. >=IP65, <=19 for UGR). "
        "Better/higher fields use >= by default: IP, IK, CRI, efficacy, lifetime, warranty, lumen maintenance. "
        "Lower-is-better fields use <= by default: UGR, power_max_w, ambient temperature limits, height/width/length/diameter when the user asks for compact/max dimensions. "
        "If unsure, leave fields null."
    )


def _image_system_prompt(allowed_families: Optional[list[str]]) -> str:
    allowed_txt = ""
    if allowed_families:
        allowed_txt = (
            "Allowed product_family values (choose ONLY from these): "
            + ", ".join(allowed_families[:200])
            + ". "
        )
    return (
        "You analyze a lighting-fixture photo and infer coarse search filters. "
        "Return only fields defined by the schema. "
        "Do not invent technical values like lumen/IP/IK unless visually undeniable (normally leave null). "
        + allowed_txt
        + "Prefer conservative output; if uncertain, leave fields null."
    )


def _drop_empty_and_unknown(filters: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in (filters or {}).items():
        if key not in ALLOWED_FILTER_KEYS:
            continue
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        out[key] = value
    return out


def _family_lookup(allowed_families: Optional[list[str]]) -> dict[str, str]:
    return {
        re.sub(r"[^a-z0-9]+", " ", str(family or "").strip().lower()).strip(): str(family).strip()
        for family in (allowed_families or [])
        if str(family or "").strip()
    }


def _normalize_family(value: Any, allowed_families: Optional[list[str]]) -> Any:
    if value in (None, "", []):
        return value
    if isinstance(value, list):
        normalized = [_normalize_family(item, allowed_families) for item in value]
        return [item for item in normalized if item not in (None, "", [])]
    if not allowed_families:
        return value
    lookup = _family_lookup(allowed_families)
    raw = FAMILY_ALIASES.get(str(value or "").strip().lower(), str(value or ""))
    key = re.sub(r"[^a-z0-9]+", " ", raw.strip().lower()).strip()
    if key in lookup:
        return lookup[key]
    for normalized, original in lookup.items():
        if key and normalized and (key in normalized or normalized in key):
            return original
    return None


def _normalize_rating(value: Any, prefix: str, digits: int) -> Any:
    if value in (None, "", []):
        return value
    if isinstance(value, list):
        vals = [_normalize_rating(item, prefix, digits) for item in value]
        return [item for item in vals if item not in (None, "", [])]
    text = str(value or "").strip().upper().replace(" ", "").replace(f"{prefix}X", f"{prefix}0")
    m = re.search(r"(>=|<=|>|<|=)?(?:%s)?(\d{1,%d})" % (prefix, digits), text)
    if not m:
        return None
    op = m.group(1) or ">="
    if op == "=":
        op = ">="
    return f"{op}{prefix}{m.group(2).zfill(digits)}"


def _normalize_numeric(value: Any, default_op: str, *, allow_thousands: bool = False) -> Any:
    if value in (None, "", []):
        return value
    if isinstance(value, list):
        vals = [_normalize_numeric(item, default_op, allow_thousands=allow_thousands) for item in value]
        return [item for item in vals if item not in (None, "", [])]
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace(" ", "").replace(",", ".")
    range_match = re.search(r"(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)", compact)
    if range_match:
        return f"{range_match.group(1)}-{range_match.group(2)}"
    op = ""
    for candidate in (">=", "<=", ">", "<", "="):
        if compact.startswith(candidate):
            op = candidate
            compact = compact[len(candidate):]
            break
    if op == "=":
        op = default_op
    if allow_thousands:
        num_match = re.search(r"(-?\d[\d.' ]*)", raw)
        if not num_match:
            return None
        num = re.sub(r"[\s'.]", "", num_match.group(1))
    else:
        num_match = re.search(r"(-?\d+(?:[.,]\d+)?)", raw)
        if not num_match:
            return None
        num = num_match.group(1).replace(",", ".")
    return f"{op or default_op}{num}"


def _normalize_yes_no(value: Any) -> Any:
    if value in (None, "", []):
        return value
    text = str(value or "").strip().lower()
    if text in {"yes", "y", "true", "1", "si", "sì", "oui", "ja"}:
        return "yes"
    if text in {"no", "n", "false", "0", "non"}:
        return "no"
    return value


def _normalize_shape(value: Any) -> Any:
    if value in (None, "", []):
        return value
    text = str(value or "").strip().lower()
    if text in {"round", "circular", "circle", "rotondo", "rotonda"}:
        return "round"
    if text in {"square", "quadrato", "quadrata"}:
        return "square"
    if text in {"rectangular", "rectangle", "rettangolare"}:
        return "rectangular"
    if text in {"linear", "lineare"}:
        return "linear"
    return value


def _normalize_llm_filters(filters: Dict[str, Any], allowed_families: Optional[list[str]]) -> Dict[str, Any]:
    out = _drop_empty_and_unknown(filters)
    if "product_family" in out:
        out["product_family"] = _normalize_family(out.get("product_family"), allowed_families)
    for key in ("ip_rating", "ip_visible", "ip_non_visible"):
        if key in out:
            out[key] = _normalize_rating(out.get(key), "IP", 2)
    if "ik_rating" in out:
        out["ik_rating"] = _normalize_rating(out.get("ik_rating"), "IK", 2)
    for key in ("ugr", "power_max_w", "ambient_temp_min_c", "ambient_temp_max_c"):
        if key in out:
            out[key] = _normalize_numeric(out.get(key), "<=")
    for key in ("luminaire_height", "luminaire_width", "luminaire_length", "diameter"):
        if key in out:
            out[key] = _normalize_numeric(out.get(key), "=")
    for key in ("cri", "efficacy_lm_w", "power_min_w", "beam_angle_deg", "warranty_years", "lumen_maintenance_pct"):
        if key in out:
            out[key] = _normalize_numeric(out.get(key), ">=")
    for key in ("lifetime_hours", "led_rated_life_h"):
        if key in out:
            out[key] = _normalize_numeric(out.get(key), ">=", allow_thousands=True)
    if "cct_k" in out:
        cct = _normalize_numeric(out.get("cct_k"), "")
        out["cct_k"] = str(cct or "").lstrip("<>=")
    if "shape" in out:
        out["shape"] = _normalize_shape(out.get("shape"))
    if "emergency_present" in out:
        out["emergency_present"] = _normalize_yes_no(out.get("emergency_present"))
    return _drop_empty_and_unknown(out)


def llm_intent_to_filters_with_meta(
    text: str,
    allowed_families: Optional[list[str]] = None,
    log_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = infer_text_filters(
        text=text or "",
        allowed_families=allowed_families,
        response_model=IntentFilters,
        system_prompt=_text_system_prompt(allowed_families),
        log_context=log_context,
    )
    content = dict(result.get("content") or {})
    content.pop("confidence", None)
    content.pop("notes", None)
    content = _normalize_llm_filters(content, allowed_families)
    return {
        "filters": content,
        "status": str(result.get("status") or "ok"),
        "provider": str(result.get("provider") or "openai"),
        "model": str(result.get("model") or ""),
        "used_retry": bool(result.get("used_retry")),
        "message": str(result.get("message") or ""),
    }


def llm_intent_to_filters(
    text: str,
    allowed_families: Optional[list[str]] = None,
    log_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return dict(llm_intent_to_filters_with_meta(text, allowed_families=allowed_families, log_context=log_context).get("filters") or {})


def llm_image_to_filters(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    allowed_families: Optional[list[str]] = None,
    log_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta = llm_image_to_inference(
        image_bytes=image_bytes,
        mime_type=mime_type,
        allowed_families=allowed_families,
        log_context=log_context,
    )
    return dict(meta.get("filters") or {})


def llm_image_to_inference(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    allowed_families: Optional[list[str]] = None,
    log_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = infer_image_filters(
        image_bytes=image_bytes,
        mime_type=mime_type,
        response_model=ImageIntentFilters,
        system_prompt=_image_system_prompt(allowed_families),
        user_prompt=(
            "Identify likely luminaire family/type and visible shape. "
            "If clearly visible, include asymmetry and housing_color. "
            "Return strict JSON only."
        ),
        log_context=log_context,
    )
    content = dict(result.get("content") or {})
    confidence = str(content.pop("confidence", "medium") or "medium")
    notes = str(content.pop("notes", "") or "")
    content = _normalize_llm_filters(content, allowed_families)
    if result.get("message") and not notes:
        notes = str(result.get("message") or "")
    return {
        "filters": content,
        "confidence": confidence,
        "notes": notes,
        "model": str(result.get("model") or ""),
        "status": str(result.get("status") or "ok"),
        "provider": str(result.get("provider") or "openai"),
        "used_retry": bool(result.get("used_retry")),
    }
