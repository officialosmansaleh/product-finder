from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from app.schema import ALLOWED_FILTER_KEYS


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    label: str
    category: str
    description: str
    env_name: str
    secret: bool = False
    multiline: bool = False
    restart_required: bool = False
    immediate_apply: bool = True
    placeholder: str = ""


SCORING_FIELD_DEFAULTS: dict[str, float] = {
    "product_family": 4.0,
    "lumen_output": 1.5,
    "power_max_w": 1.2,
    "efficacy_lm_w": 1.3,
    "cct_k": 1.0,
    "cri": 0.8,
    "ugr": 0.6,
    "warranty_years": 0.7,
    "lifetime_hours": 0.8,
    "led_rated_life_h": 0.8,
    "lumen_maintenance_pct": 0.7,
    "beam_angle_deg": 0.8,
    "asymmetry": 0.6,
}

SCORING_FIELD_LABELS: dict[str, str] = {
    "cct_k": "CCT",
    "cri": "CRI",
    "ugr": "UGR",
    "ip_rating": "IP Rating",
    "ip_visible": "IP Visible",
    "ip_non_visible": "IP Non Visible",
    "ik_rating": "IK Rating",
    "control_protocol": "Control Protocol",
    "interface": "Interface",
    "power_min_w": "Power Min",
    "power_max_w": "Power Max",
    "lumen_output": "Lumen Output",
    "beam_angle_deg": "Beam Angle",
    "beam_type": "Beam Type",
    "emergency_present": "Emergency",
    "product_family": "Product Family",
    "efficacy_lm_w": "Efficacy",
    "lifetime_hours": "Lifetime Hours",
    "led_rated_life_h": "LED Rated Life",
    "warranty_years": "Warranty Years",
    "lumen_maintenance_pct": "Lumen Maintenance",
    "luminaire_height": "Luminaire Height",
    "luminaire_width": "Luminaire Width",
    "luminaire_length": "Luminaire Length",
    "ambient_temp_min_c": "Ambient Temp Min",
    "ambient_temp_max_c": "Ambient Temp Max",
    "housing_color": "Housing Color",
    "product_name_short": "Product Name Short",
    "product_name_contains": "Product Name Contains",
    "name_prefix": "Name Prefix",
}


def _scoring_field_label(field_key: str) -> str:
    label = SCORING_FIELD_LABELS.get(field_key)
    if label:
        return label
    return field_key.replace("_", " ").title()


def _scoring_field_default(field_key: str) -> str:
    return str(float(SCORING_FIELD_DEFAULTS.get(field_key, 1.0)))


def _missing_scoring_weight_definitions(existing_keys: set[str]) -> tuple[SettingDefinition, ...]:
    generated: list[SettingDefinition] = []
    for field_key in sorted(ALLOWED_FILTER_KEYS):
        setting_key = f"scoring_weight_{field_key}"
        if setting_key in existing_keys:
            continue
        generated.append(
            SettingDefinition(
                key=setting_key,
                label=f"Weight: {_scoring_field_label(field_key)}",
                category="Scoring",
                description=f"Importance of {field_key.replace('_', ' ')} in the match percentage.",
                env_name=f"SCORING_WEIGHT_{field_key.upper()}",
                placeholder=_scoring_field_default(field_key),
            )
        )
    return tuple(generated)


CATEGORY_ORDER: tuple[str, ...] = (
    "AI",
    "Email",
    "Security",
    "Administration",
    "Scoring",
    "Operations",
    "Deployment",
)


SETTINGS_CATALOG: tuple[SettingDefinition, ...] = (
    SettingDefinition(
        key="openai_api_key",
        label="OpenAI API Key",
        category="AI",
        description="Backend key used for AI-powered parsing and reasoning.",
        env_name="OPENAI_API_KEY",
        secret=True,
        placeholder="sk-...",
    ),
    SettingDefinition(
        key="disano_store_ids",
        label="Disano Store IDs",
        category="AI",
        description="Comma-separated store IDs used for external product image lookups.",
        env_name="DISANO_STORE_IDS",
        placeholder="10051,10151",
    ),
    SettingDefinition(
        key="disano_lang_id",
        label="Disano Language ID",
        category="AI",
        description="Language identifier used when querying Disano product content.",
        env_name="DISANO_LANG_ID",
        placeholder="-4",
    ),
    SettingDefinition(
        key="app_domain",
        label="App Domain",
        category="Deployment",
        description="Primary public domain used for deployment and SSL.",
        env_name="APP_DOMAIN",
        restart_required=True,
        immediate_apply=False,
        placeholder="ProFinder.disano.it",
    ),
    SettingDefinition(
        key="acme_email",
        label="ACME Email",
        category="Deployment",
        description="Email used for certificate issuance and renewal notices.",
        env_name="ACME_EMAIL",
        restart_required=True,
        immediate_apply=False,
        placeholder="ops@example.com",
    ),
    SettingDefinition(
        key="enable_debug_endpoints",
        label="Enable Debug Endpoints",
        category="Operations",
        description="Turn on local-only debug endpoints for troubleshooting.",
        env_name="ENABLE_DEBUG_ENDPOINTS",
        placeholder="true or false",
    ),
    SettingDefinition(
        key="cors_allowed_origins",
        label="Allowed Origins",
        category="Security",
        description="Comma-separated browser origins allowed to call the backend.",
        env_name="CORS_ALLOWED_ORIGINS",
        multiline=True,
        restart_required=True,
        immediate_apply=False,
        placeholder="https://example.com,https://app.example.com",
    ),
    SettingDefinition(
        key="auth_token_expire_minutes",
        label="Token Lifetime (minutes)",
        category="Security",
        description="Lifetime of newly issued access tokens.",
        env_name="AUTH_TOKEN_EXPIRE_MINUTES",
        placeholder="120",
    ),
    SettingDefinition(
        key="auth_refresh_token_expire_days",
        label="Refresh Token Lifetime (days)",
        category="Security",
        description="How long refresh sessions remain valid before users must sign in again.",
        env_name="AUTH_REFRESH_TOKEN_EXPIRE_DAYS",
        placeholder="14",
    ),
    SettingDefinition(
        key="auth_cookie_secure",
        label="Secure Cookies",
        category="Security",
        description="Use secure cookies only over HTTPS. Set to true in production.",
        env_name="AUTH_COOKIE_SECURE",
        placeholder="true or false",
    ),
    SettingDefinition(
        key="auth_cookie_samesite",
        label="Cookie SameSite",
        category="Security",
        description="Cookie SameSite policy for auth cookies.",
        env_name="AUTH_COOKIE_SAMESITE",
        placeholder="lax, strict, or none",
    ),
    SettingDefinition(
        key="auth_jwt_secret",
        label="JWT Secret",
        category="Security",
        description="Signing secret for JWT access tokens.",
        env_name="AUTH_JWT_SECRET",
        secret=True,
        restart_required=True,
        immediate_apply=False,
        placeholder="long-random-secret",
    ),
    SettingDefinition(
        key="admin_bootstrap_email",
        label="Bootstrap Admin Email",
        category="Administration",
        description="Admin account email ensured during startup and updates.",
        env_name="ADMIN_BOOTSTRAP_EMAIL",
        placeholder="admin@example.com",
    ),
    SettingDefinition(
        key="admin_bootstrap_name",
        label="Bootstrap Admin Name",
        category="Administration",
        description="Display name for the bootstrap admin account.",
        env_name="ADMIN_BOOTSTRAP_NAME",
        placeholder="Administrator",
    ),
    SettingDefinition(
        key="admin_bootstrap_password",
        label="Bootstrap Admin Password",
        category="Administration",
        description="Password for the bootstrap admin account.",
        env_name="ADMIN_BOOTSTRAP_PASSWORD",
        secret=True,
        placeholder="strong-admin-password",
    ),
    SettingDefinition(
        key="admin_token",
        label="Legacy Admin Token",
        category="Administration",
        description="Fallback admin token for legacy debug or maintenance endpoints.",
        env_name="ADMIN_TOKEN",
        secret=True,
        placeholder="legacy-admin-token",
    ),
    SettingDefinition(
        key="postgres_password",
        label="Postgres Password",
        category="Deployment",
        description="Database password used by deployment and Docker compose.",
        env_name="POSTGRES_PASSWORD",
        secret=True,
        restart_required=True,
        immediate_apply=False,
        placeholder="strong-db-password",
    ),
    SettingDefinition(
        key="smtp_host",
        label="SMTP Host",
        category="Email",
        description="SMTP server hostname for password reset emails.",
        env_name="SMTP_HOST",
        placeholder="smtp.example.com",
    ),
    SettingDefinition(
        key="smtp_port",
        label="SMTP Port",
        category="Email",
        description="SMTP server port.",
        env_name="SMTP_PORT",
        placeholder="587",
    ),
    SettingDefinition(
        key="smtp_username",
        label="SMTP Username",
        category="Email",
        description="SMTP login username.",
        env_name="SMTP_USERNAME",
        placeholder="mailer@example.com",
    ),
    SettingDefinition(
        key="smtp_password",
        label="SMTP Password",
        category="Email",
        description="SMTP login password or app password.",
        env_name="SMTP_PASSWORD",
        secret=True,
        placeholder="smtp-password",
    ),
    SettingDefinition(
        key="smtp_from_email",
        label="SMTP From Email",
        category="Email",
        description="Sender address used for password reset emails.",
        env_name="SMTP_FROM_EMAIL",
        placeholder="no-reply@example.com",
    ),
    SettingDefinition(
        key="scoring_weight_product_family",
        label="Weight: Product Family",
        category="Scoring",
        description="Importance of product family in the match percentage.",
        env_name="SCORING_WEIGHT_PRODUCT_FAMILY",
        placeholder="4.0",
    ),
    SettingDefinition(
        key="scoring_weight_lumen_output",
        label="Weight: Lumen Output",
        category="Scoring",
        description="Importance of lumen output in the match percentage.",
        env_name="SCORING_WEIGHT_LUMEN_OUTPUT",
        placeholder="1.5",
    ),
    SettingDefinition(
        key="scoring_weight_power_max_w",
        label="Weight: Power Max",
        category="Scoring",
        description="Importance of maximum power in the match percentage.",
        env_name="SCORING_WEIGHT_POWER_MAX_W",
        placeholder="1.2",
    ),
    SettingDefinition(
        key="scoring_weight_efficacy_lm_w",
        label="Weight: Efficacy",
        category="Scoring",
        description="Importance of efficacy in the match percentage.",
        env_name="SCORING_WEIGHT_EFFICACY_LM_W",
        placeholder="1.3",
    ),
    SettingDefinition(
        key="scoring_weight_cct_k",
        label="Weight: CCT",
        category="Scoring",
        description="Importance of CCT in the match percentage.",
        env_name="SCORING_WEIGHT_CCT_K",
        placeholder="1.0",
    ),
    SettingDefinition(
        key="scoring_weight_cri",
        label="Weight: CRI",
        category="Scoring",
        description="Importance of CRI in the match percentage.",
        env_name="SCORING_WEIGHT_CRI",
        placeholder="0.8",
    ),
    SettingDefinition(
        key="scoring_weight_ugr",
        label="Weight: UGR",
        category="Scoring",
        description="Importance of UGR in the match percentage.",
        env_name="SCORING_WEIGHT_UGR",
        placeholder="0.6",
    ),
    SettingDefinition(
        key="scoring_missing_penalty",
        label="Missing Penalty",
        category="Scoring",
        description="Penalty applied when a scored field is missing on a product.",
        env_name="SCORING_MISSING_PENALTY",
        placeholder="0.5",
    ),
    SettingDefinition(
        key="scoring_deviation_penalty",
        label="Deviation Penalty",
        category="Scoring",
        description="Penalty applied when a scored field does not match.",
        env_name="SCORING_DEVIATION_PENALTY",
        placeholder="1.0",
    ),
    SettingDefinition(
        key="scoring_family_missing_multiplier",
        label="Family Missing Multiplier",
        category="Scoring",
        description="Extra penalty multiplier when product family is missing.",
        env_name="SCORING_FAMILY_MISSING_MULTIPLIER",
        placeholder="2.0",
    ),
    SettingDefinition(
        key="scoring_family_mismatch_multiplier",
        label="Family Mismatch Multiplier",
        category="Scoring",
        description="Extra penalty multiplier when product family does not match.",
        env_name="SCORING_FAMILY_MISMATCH_MULTIPLIER",
        placeholder="3.0",
    ),
    SettingDefinition(
        key="rate_limit_store",
        label="Rate Limit Store",
        category="Operations",
        description="Storage backend for rate limiting, such as memory or database.",
        env_name="RATE_LIMIT_STORE",
        placeholder="memory or database",
    ),
    SettingDefinition(
        key="rate_limit_database_url",
        label="Rate Limit Database URL",
        category="Operations",
        description="Database URL used by shared rate limiting when enabled.",
        env_name="RATE_LIMIT_DATABASE_URL",
        secret=True,
        multiline=True,
        restart_required=True,
        immediate_apply=False,
        placeholder="postgresql://user:pass@host/dbname",
    ),
)

SETTINGS_CATALOG = SETTINGS_CATALOG + _missing_scoring_weight_definitions({item.key for item in SETTINGS_CATALOG})

SETTINGS_BY_KEY: dict[str, SettingDefinition] = {item.key: item for item in SETTINGS_CATALOG}


def normalize_setting_value(definition: SettingDefinition, value: str) -> str:
    text = str(value or "").strip()
    if definition.key.startswith("scoring_") and text:
        try:
            number = float(text)
        except ValueError:
            raise ValueError(f"{definition.label} must be a number")
        if definition.key.startswith("scoring_weight_"):
            if number < 0 or number > 20:
                raise ValueError(f"{definition.label} must be between 0 and 20")
        elif definition.key in {"scoring_missing_penalty", "scoring_deviation_penalty"}:
            if number < 0 or number > 5:
                raise ValueError(f"{definition.label} must be between 0 and 5")
        elif definition.key in {"scoring_family_missing_multiplier", "scoring_family_mismatch_multiplier"}:
            if number < 0 or number > 10:
                raise ValueError(f"{definition.label} must be between 0 and 10")
        return str(number)
    if definition.key in {"auth_token_expire_minutes", "smtp_port", "auth_refresh_token_expire_days"}:
        number = int(text or "0")
        if definition.key == "auth_token_expire_minutes":
            if number < 5 or number > 1440:
                raise ValueError("Token lifetime must be between 5 and 1440 minutes")
        elif definition.key == "auth_refresh_token_expire_days":
            if number < 1 or number > 365:
                raise ValueError("Refresh token lifetime must be between 1 and 365 days")
        else:
            if number < 1 or number > 65535:
                raise ValueError("SMTP port must be between 1 and 65535")
        return str(number)
    if definition.key in {"auth_cookie_secure", "enable_debug_endpoints", "pim_verbose"}:
        lowered = text.lower()
        if lowered not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
            raise ValueError(f"{definition.label} must be true or false")
        return "1" if lowered in {"1", "true", "yes", "on"} else "0"
    if definition.key == "auth_cookie_samesite":
        lowered = text.lower()
        if lowered not in {"lax", "strict", "none"}:
            raise ValueError("SameSite must be lax, strict, or none")
        return lowered
    if definition.key == "cors_allowed_origins":
        parts = [part.strip() for part in text.split(",") if part.strip()]
        return ",".join(parts)
    if definition.key == "rate_limit_store" and text:
        lowered = text.lower()
        if lowered not in {"memory", "database", "db"}:
            raise ValueError("Rate limit store must be memory or database")
        return "database" if lowered == "db" else lowered
    if definition.key in {"admin_bootstrap_email", "acme_email", "smtp_from_email"} and text:
        if "@" not in text or "." not in text.split("@")[-1]:
            raise ValueError("Please enter a valid email address")
        return text.lower()
    return text


def mask_secret_value(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    if len(clean) <= 6:
        return "*" * len(clean)
    return f"{clean[:2]}{'*' * max(4, len(clean) - 6)}{clean[-2:]}"
