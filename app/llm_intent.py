from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, Field
from openai import OpenAI

client = OpenAI()

class IntentFilters(BaseModel):
    product_family: Optional[str] = Field(None, description="e.g. highbay, road lighting, waterproof, floodlight, wall, linear, downlight, panels")
    ip_rating: Optional[str] = Field(None, description="e.g. >=IP65, >=IP66")
    ik_rating: Optional[str] = Field(None, description="e.g. >=IK08")
    asymmetry: Optional[str] = Field(None, description="e.g. asymmetric, asimmetrico, yes")
    ugr: Optional[str] = Field(None, description="e.g. <=19, <=22")
    efficacy_lm_w: Optional[str] = Field(None, description="e.g. >=130, >=140")
    cct_k: Optional[str] = Field(None, description="e.g. 4000, 3000")
    luminaire_length: Optional[str] = Field(None, description="mm, preferably range expression like 590-610 for 600 module")
    luminaire_width: Optional[str] = Field(None, description="mm, preferably range expression like 590-610 for 600 module")
    control_protocol: Optional[str] = Field(None, description="e.g. dali")
    emergency_present: Optional[str] = Field(None, description="yes/no")

    confidence: Literal["low","medium","high"] = "medium"
    notes: Optional[str] = None


def llm_intent_to_filters(text: str, allowed_families: Optional[list[str]] = None) -> Dict[str, Any]:
    """
    Estrae intent/applicazione -> filtri tecnici suggeriti.
    Ritorna un dict piatto compatibile col tuo main.
    IMPORTANT: niente lumen_output (evita bug lm/w -> lm).
    """
    allowed_txt = ""
    if allowed_families:
        allowed_txt = (
            "Allowed product_family values (choose ONLY from these): "
            + ", ".join(allowed_families[:200])  # evita prompt troppo lungo
            + ". "
        )

    system = (
        "You convert a lighting application request into filters. "
        "Return only fields in the schema. "
        "IMPORTANT: Do NOT output lumen_output. "
        + allowed_txt +
        "Interpret lighting size shorthand in Italian/English. "
        "Examples: '60x60', '60 per 60', '60 by 60' for panel/troffer usually means 600x600 mm. "
        "When size is present, prefer luminaire_length/luminaire_width in millimeters (can use ranges). "
        "Use operators like >=, <= when appropriate (e.g. >=IP65, <=19 for UGR). "
        "If unsure, leave fields null."
    )



    completion = client.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text or ""},
        ],
        response_format=IntentFilters,
    )

    obj: IntentFilters = completion.choices[0].message.parsed
    d = obj.model_dump(exclude_none=True)
    d.pop("confidence", None)
    d.pop("notes", None)
    return d
