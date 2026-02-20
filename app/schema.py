from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


# -----------------------------
# Search input
# -----------------------------

# app/schema.py

ALLOWED_FILTER_KEYS = {
    "ip_rating",
    "ik_rating",
    "cct_k",
    "control_protocol",
    "power_min_w",
    "power_max_w",
    "lumen_output",
    "beam_angle_deg",
    "beam_type",
    "asymmetry",
    "cri",
    "ugr",
    "emergency_present",
    "product_family",
    "efficacy_lm_w",
    "lifetime_hours",
    "led_rated_life_h",
    "warranty_years",
    "lumen_maintenance_pct",
    "luminaire_height",
    "luminaire_width",
    "luminaire_length",
    "luminaire_size_min",
    "luminaire_size_max",
    "diameter",
    "housing_color",
    "name_prefix",
    "manufacturer",


  

}
HARD_FILTER_KEYS = {
    "ip_rating",
    "ik_rating",
    "product_family",
    "cri",
    "ugr",
    "cct_k",
    "power_min_w",
    "power_max_w",
    "lumen_output",
    "efficacy_lm_w",
    "lifetime_hours",
    "led_rated_life_h",
    "warranty_years",
    "lumen_maintenance_pct",
    "luminaire_size_min",
    "luminaire_size_max",
}

SOFT_FILTER_KEYS = {

    "control_protocol",
    "emergency_present",
    "beam_angle_deg",
    "beam_type",
    "asymmetry",
    "efficacy_lm_w",


}


class SearchRequest(BaseModel):
    text: str = Field(..., description="Descrizione generica dell'utente")
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 20
    include_similar: bool = True

    # 🔎 show debug payload only if true
    debug: bool = False


# -----------------------------
# Parsed filter structure (AI / local parser)
# -----------------------------

class FilterSpec(BaseModel):
    hard_filters: Dict[str, Any] = Field(default_factory=dict)
    soft_prefs: Dict[str, Any] = Field(default_factory=dict)
    free_text: str = ""
    unknowns: List[str] = Field(default_factory=list)
    confidence: str = "medium"


# -----------------------------
# Search result
# -----------------------------

class ProductHit(BaseModel):
    product_code: str
    product_name: str
    score: float

    matched: Dict[str, Any]
    deviations: List[str]
    missing: List[str]

    # quick UI preview fields
    preview: Dict[str, Any] = Field(default_factory=dict)

    # 🧠 included only when debug=true
    debug_filters: Optional[Dict[str, Any]] = None

    # optional full row dump (normally unused)
    raw: Optional[Dict[str, Any]] = None

class SearchResponse(BaseModel):
    exact: List[ProductHit] = Field(default_factory=list)
    similar: List[ProductHit] = Field(default_factory=list)
    interpreted: Dict[str, Any] = Field(default_factory=dict)
    backend_debug_filters: Optional[Dict[str, Any]] = None

class FacetValue(BaseModel):
    value: str
    count: int
    raw: Optional[str] = None

class FacetsResponse(BaseModel):
    families: List[FacetValue] = Field(default_factory=list)
    manufacturers: List[FacetValue] = Field(default_factory=list)
    similar_names: List[FacetValue] = Field(default_factory=list)
    warranty_lifetime: Dict[str, Any] = Field(default_factory=dict)
    photometrics: Dict[str, Any] = Field(default_factory=dict)
    power_voltage: Dict[str, Any] = Field(default_factory=dict)
    dimensions_options: Dict[str, Any] = Field(default_factory=dict)
    price_consumption: Dict[str, Any] = Field(default_factory=dict)

