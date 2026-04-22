from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


# -----------------------------
# Search input
# -----------------------------

# app/schema.py

ALLOWED_FILTER_KEYS = {
    "ip_rating",
    "ip_visible",
    "ip_non_visible",
    "ik_rating",
    "cct_k",
    "control_protocol",
    "interface",
    "power_min_w",
    "power_max_w",
    "lumen_output",
    "beam_angle_deg",
    "beam_type",
    "asymmetry",
    "shape",
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
    "diameter",
    "ambient_temp_min_c",
    "ambient_temp_max_c",
    "housing_color",
    "product_name_short",
    "product_name_contains",
    "name_prefix",
    "manufacturer",


  

}
HARD_FILTER_KEYS = {
    "ip_rating",
    "ip_visible",
    "ip_non_visible",
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
    "ambient_temp_min_c",
    "ambient_temp_max_c",
}

SOFT_FILTER_KEYS = {

    "control_protocol",
    "interface",
    "emergency_present",
    "beam_angle_deg",
    "beam_type",
    "asymmetry",
    "shape",
    "efficacy_lm_w",


}


class SearchRequest(BaseModel):
    text: str = Field(..., description="Descrizione generica dell'utente")
    filters: Dict[str, Any] = Field(default_factory=dict)
    ignored_ai_filters: List[Dict[str, Any]] = Field(default_factory=list)
    limit: int = 20
    include_similar: bool = True
    allow_ai: bool = True

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
    interpreted: Optional[Dict[str, Any]] = None
    backend_debug_filters: Optional[Dict[str, Any]] = None

class FacetValue(BaseModel):
    value: str
    count: int
    raw: Optional[str] = None

class FacetsResponse(BaseModel):
    families: List[FacetValue] = Field(default_factory=list)
    product_name_short: List[FacetValue] = Field(default_factory=list)
    # Legacy alias kept for backward compatibility with older clients.
    similar_names: List[FacetValue] = Field(default_factory=list)
    warranty_lifetime: Dict[str, Any] = Field(default_factory=dict)
    photometrics: Dict[str, Any] = Field(default_factory=dict)
    power_voltage: Dict[str, Any] = Field(default_factory=dict)
    dimensions_options: Dict[str, Any] = Field(default_factory=dict)
    price_consumption: Dict[str, Any] = Field(default_factory=dict)


class CompareCodesRequest(BaseModel):
    code_a: str
    code_b: str


class CompareProductsRequest(BaseModel):
    codes: List[str]


class IdealSpecAlternativesRequest(BaseModel):
    ideal_spec: Dict[str, Any] = Field(default_factory=dict)
    limit: Optional[int] = None
    sort: str = "score_desc"
    min_score: Optional[float] = None


class CompareSpecProductsRequest(BaseModel):
    ideal_spec: Dict[str, Any] = Field(default_factory=dict)
    codes: List[str]


class CompareExportPdfRequest(BaseModel):
    codes: List[str] = Field(default_factory=list)
    ideal_spec: Dict[str, Any] = Field(default_factory=dict)


class AlternativesRequest(BaseModel):
    code: str
    limit: Optional[int] = None
    min_score: Optional[float] = None


class QuotePdfItem(BaseModel):
    product_code: str
    product_name: str = ""
    qty: int = 1
    notes: str = ""
    project_reference: str = ""
    manufacturer: str = ""
    source: str = ""


class QuotePdfRequest(BaseModel):
    company: str
    project: str
    project_status: str = "design_phase"
    contractor_name: str = ""
    consultant_name: str = ""
    project_notes: str = ""
    items: List[QuotePdfItem] = Field(default_factory=list)


class QuoteDatasheetsZipRequest(BaseModel):
    items: List[QuotePdfItem] = Field(default_factory=list)

