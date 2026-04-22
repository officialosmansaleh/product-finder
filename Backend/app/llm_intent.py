import json
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from app.ai_service import infer_image_filters, infer_text_filters


class IntentFilters(BaseModel):
    product_family: Optional[str] = Field(None, description="e.g. highbay, street lighting, waterproof, floodlight, wall, linear, downlight, panels")
    ip_rating: Optional[str] = Field(None, description="e.g. >=IP65, >=IP66")
    ip_visible: Optional[str] = Field(None, description="IP visible side (IP v.l.), e.g. >=IP65")
    ip_non_visible: Optional[str] = Field(None, description="IP non-visible side (IP v.a.), e.g. >=IP20")
    ik_rating: Optional[str] = Field(None, description="e.g. >=IK08")
    asymmetry: Optional[str] = Field(None, description="e.g. asymmetric, asimmetrico, yes")
    ugr: Optional[str] = Field(None, description="e.g. <=19, <=22")
    efficacy_lm_w: Optional[str] = Field(None, description="e.g. >=130, >=140")
    cct_k: Optional[str] = Field(None, description="e.g. 4000, 3000")
    control_protocol: Optional[str] = Field(None, description="generic control capability when interface is not specified")
    interface: Optional[str] = Field(None, description="e.g. dali, dmx, 1-10v, zhaga")
    emergency_present: Optional[str] = Field(None, description="yes/no")
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
        "Return only fields in the schema. "
        "IMPORTANT: Do NOT output lumen_output. "
        "IMPORTANT: map DALI, DMX, 1-10V dimmer, and Zhaga/antenna requests to 'interface' (not 'control_protocol'). "
        + allowed_txt
        + "Use operators like >=, <= when appropriate (e.g. >=IP65, <=19 for UGR). "
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


def llm_intent_to_filters_with_meta(text: str, allowed_families: Optional[list[str]] = None) -> Dict[str, Any]:
    result = infer_text_filters(
        text=text or "",
        allowed_families=allowed_families,
        response_model=IntentFilters,
        system_prompt=_text_system_prompt(allowed_families),
    )
    content = dict(result.get("content") or {})
    content.pop("confidence", None)
    content.pop("notes", None)
    return {
        "filters": content,
        "status": str(result.get("status") or "ok"),
        "provider": str(result.get("provider") or "openai"),
        "model": str(result.get("model") or ""),
        "used_retry": bool(result.get("used_retry")),
        "message": str(result.get("message") or ""),
    }


def llm_intent_to_filters(text: str, allowed_families: Optional[list[str]] = None) -> Dict[str, Any]:
    return dict(llm_intent_to_filters_with_meta(text, allowed_families=allowed_families).get("filters") or {})


def llm_image_to_filters(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    allowed_families: Optional[list[str]] = None,
) -> Dict[str, Any]:
    meta = llm_image_to_inference(
        image_bytes=image_bytes,
        mime_type=mime_type,
        allowed_families=allowed_families,
    )
    return dict(meta.get("filters") or {})


def llm_image_to_inference(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    allowed_families: Optional[list[str]] = None,
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
    )
    content = dict(result.get("content") or {})
    confidence = str(content.pop("confidence", "medium") or "medium")
    notes = str(content.pop("notes", "") or "")
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
