from __future__ import annotations

import base64
import json
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import smtplib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Iterator, Optional

import jwt
import psycopg2
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator, model_validator
from psycopg2.extras import RealDictCursor

from app.admin_settings import CATEGORY_ORDER, SETTINGS_BY_KEY, SETTINGS_CATALOG, mask_secret_value, normalize_setting_value
from app.db_runtime import normalize_postgres_url

ROLE_USER = "user"
ROLE_MANAGER = "manager"
ROLE_DIRECTOR = "director"
ROLE_ADMIN = "admin"
ROLE_ORDER = (ROLE_USER, ROLE_MANAGER, ROLE_DIRECTOR, ROLE_ADMIN)
STAFF_ROLES = {ROLE_MANAGER, ROLE_DIRECTOR, ROLE_ADMIN}
LEADERSHIP_ROLES = {ROLE_DIRECTOR, ROLE_ADMIN}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().isoformat()


def _password_hash(password: str, *, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations_raw, salt_b64, digest_b64 = str(stored_hash or "").split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(default="", max_length=120)
    company_name: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = str(value or "").strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ValueError("Invalid email address")
        return email


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = str(value or "").strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ValueError("Invalid email address")
        return email


class UserPublic(BaseModel):
    id: int
    email: str
    full_name: str = ""
    company_name: str = ""
    country: str = ""
    assigned_countries: list[str] = Field(default_factory=list)
    role: str
    status: str
    created_at: str
    approved_at: Optional[str] = None
    last_login_at: Optional[str] = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str = ""
    user: UserPublic


class UserStatusUpdateResponse(BaseModel):
    success: bool
    user: UserPublic


class UserApprovalRequest(BaseModel):
    role: str = Field(default=ROLE_USER, pattern="^(admin|director|manager|user)$")
    assigned_countries: list[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return str(value or ROLE_USER).strip().lower() or ROLE_USER

    @field_validator("assigned_countries")
    @classmethod
    def normalize_assigned_countries(cls, value: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in value or []:
            clean = str(item or "").strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(clean)
        return out

    @model_validator(mode="after")
    def validate_manager_countries(self) -> "UserApprovalRequest":
        if self.role == ROLE_MANAGER and not self.assigned_countries:
            raise ValueError("Managers must have at least one assigned country")
        return self


class AdminUserUpdateRequest(BaseModel):
    full_name: str = Field(default="", max_length=120)
    company_name: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=120)
    role: str = Field(default=ROLE_USER, pattern="^(admin|director|manager|user)$")
    assigned_countries: list[str] = Field(default_factory=list)

    @field_validator("full_name", "company_name", "country")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("role")
    @classmethod
    def normalize_update_role(cls, value: str) -> str:
        return str(value or ROLE_USER).strip().lower() or ROLE_USER

    @field_validator("assigned_countries")
    @classmethod
    def normalize_update_assigned_countries(cls, value: list[str]) -> list[str]:
        return UserApprovalRequest.normalize_assigned_countries(value)

    @model_validator(mode="after")
    def validate_update(self) -> "AdminUserUpdateRequest":
        if not self.country:
            raise ValueError("Country is required")
        if self.role == ROLE_MANAGER and not self.assigned_countries:
            raise ValueError("Managers must have at least one assigned country")
        return self


class SavedQuoteItem(BaseModel):
    product_code: str
    product_name: str = ""
    manufacturer: str = ""
    qty: int = 1
    notes: str = ""
    project_reference: str = ""
    source: str = ""
    sort_order: int = 0
    compare_sheet: dict[str, Any] = Field(default_factory=dict)


class SavedQuoteUpsertRequest(BaseModel):
    company: str = Field(default="", max_length=200)
    project: str = Field(min_length=1, max_length=200)
    project_status: str = Field(default="design_phase", max_length=40)
    contractor_name: str = Field(default="", max_length=200)
    consultant_name: str = Field(default="", max_length=200)
    project_notes: str = Field(default="", max_length=2000)
    items: list[SavedQuoteItem] = Field(default_factory=list)

    @field_validator("project_status")
    @classmethod
    def normalize_project_status(cls, value: str) -> str:
        allowed = {"design_phase", "tender", "job_in_hand_contractor", "job_in_hand"}
        status = str(value or "design_phase").strip().lower() or "design_phase"
        return status if status in allowed else "design_phase"

    @field_validator("contractor_name", "consultant_name")
    @classmethod
    def normalize_quote_parties(cls, value: str) -> str:
        return str(value or "").strip()

    @model_validator(mode="after")
    def validate_required_quote_fields(self) -> "SavedQuoteUpsertRequest":
        if not self.contractor_name:
            raise ValueError("Contractor name is required")
        if not self.consultant_name:
            raise ValueError("Consultant name is required")
        return self


class SavedQuoteSummary(BaseModel):
    id: int
    company: str = ""
    project: str
    project_status: str = "design_phase"
    contractor_name: str = ""
    consultant_name: str = ""
    project_notes: str = ""
    item_count: int = 0
    created_at: str
    updated_at: str


class SavedQuoteDetail(SavedQuoteSummary):
    items: list[SavedQuoteItem] = Field(default_factory=list)


class VisibleQuoteSummary(BaseModel):
    quote_id: int
    user_id: int
    project: str = ""
    customer_name: str = ""
    country: str = ""
    contractor_name: str = ""
    project_status: str = "design_phase"
    consultant_name: str = ""
    quote_owner_name: str = ""
    quote_owner_email: str = ""
    item_count: int = 0
    updated_at: str = ""
    created_at: str = ""


class AdminSettingPublic(BaseModel):
    key: str
    label: str
    category: str
    description: str
    value: str = ""
    secret: bool = False
    configured: bool = False
    masked_value: str = ""
    restart_required: bool = False
    multiline: bool = False
    placeholder: str = ""
    updated_at: Optional[str] = None
    updated_by: Optional[int] = None


class AdminSettingUpdateRequest(BaseModel):
    value: str = ""


class PasswordResetRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = str(value or "").strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ValueError("Invalid email address")
        return email


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    password: str = Field(min_length=10, max_length=128)


class CookieConsentRequest(BaseModel):
    analytics: bool = False
    source: str = Field(default="banner", max_length=40)
    consent_version: str = Field(default="2026-03-31", max_length=40)


class AnalyticsEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    page: str = Field(default="", max_length=200)
    path: str = Field(default="", max_length=200)
    product_code: str = Field(default="", max_length=120)
    query_text: str = Field(default="", max_length=500)
    filters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuthService:
    def __init__(self, db_path: str | None = None, database_url: str | None = None) -> None:
        self.db_path = db_path or os.getenv("AUTH_DB_PATH", "data/auth.db")
        self.database_url = normalize_postgres_url(str(database_url or os.getenv("AUTH_DATABASE_URL", "")).strip())
        self.backend = "postgres" if self.database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
        self.jwt_secret = str(os.getenv("AUTH_JWT_SECRET", "dev-insecure-change-me")).strip() or "dev-insecure-change-me"
        self.jwt_algorithm = "HS256"
        self.token_expire_minutes = int(os.getenv("AUTH_TOKEN_EXPIRE_MINUTES", "120") or "120")
        self.refresh_token_expire_days = int(os.getenv("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "14") or "14")
        self.access_cookie_name = str(os.getenv("AUTH_ACCESS_COOKIE_NAME", "pf_access_token")).strip() or "pf_access_token"
        self.refresh_cookie_name = str(os.getenv("AUTH_REFRESH_COOKIE_NAME", "pf_refresh_token")).strip() or "pf_refresh_token"
        self.consent_cookie_name = str(os.getenv("CONSENT_COOKIE_NAME", "pf_cookie_consent")).strip() or "pf_cookie_consent"
        self.analytics_session_cookie_name = str(os.getenv("ANALYTICS_SESSION_COOKIE_NAME", "pf_analytics_sid")).strip() or "pf_analytics_sid"
        self.cookie_secure = str(os.getenv("AUTH_COOKIE_SECURE", "0")).strip().lower() in {"1", "true", "yes", "on"}
        self.cookie_samesite = str(os.getenv("AUTH_COOKIE_SAMESITE", "lax")).strip().lower() or "lax"
        self.bootstrap_email = str(os.getenv("ADMIN_BOOTSTRAP_EMAIL", "")).strip().lower()
        self.bootstrap_password = str(os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")).strip()
        self.bootstrap_name = str(os.getenv("ADMIN_BOOTSTRAP_NAME", "Administrator")).strip() or "Administrator"

    def _translate_query(self, query: str) -> str:
        if self.backend != "postgres":
            return query
        out: list[str] = []
        in_single = False
        for i, ch in enumerate(query):
            if ch == "'" and (i == 0 or query[i - 1] != "\\"):
                in_single = not in_single
                out.append(ch)
            elif ch == "?" and not in_single:
                out.append("%s")
            else:
                out.append(ch)
        return "".join(out)

    def _parse_assigned_countries(self, value: Any) -> list[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        out: list[str] = []
        seen: set[str] = set()
        for part in raw.split(","):
            clean = str(part or "").strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(clean)
        return out

    def _serialize_assigned_countries(self, values: list[str] | None) -> str:
        return ", ".join(self._parse_assigned_countries(",".join(values or [])))

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.backend == "postgres":
            conn = psycopg2.connect(self.database_url)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            return

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _fetchone(self, conn: Any, query: str, params: tuple[Any, ...] = ()) -> Optional[dict[str, Any]]:
        if self.backend == "postgres":
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(self._translate_query(query), params)
                row = cur.fetchone()
                return dict(row) if row else None
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None

    def _fetchall(self, conn: Any, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if self.backend == "postgres":
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(self._translate_query(query), params)
                return [dict(r) for r in cur.fetchall()]
        return [dict(r) for r in conn.execute(query, params).fetchall()]

    def _execute(self, conn: Any, query: str, params: tuple[Any, ...] = ()) -> None:
        if self.backend == "postgres":
            with conn.cursor() as cur:
                cur.execute(self._translate_query(query), params)
            return
        conn.execute(query, params)

    def init_db(self) -> None:
        with self.connect() as conn:
            if self.backend == "postgres":
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGSERIAL PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        full_name TEXT NOT NULL DEFAULT '',
                        company_name TEXT NOT NULL DEFAULT '',
                        country TEXT NOT NULL DEFAULT '',
                        assigned_countries TEXT NOT NULL DEFAULT '',
                        role TEXT NOT NULL DEFAULT 'user',
                        status TEXT NOT NULL DEFAULT 'pending',
                        created_at TEXT NOT NULL,
                        approved_at TEXT,
                        approved_by BIGINT,
                        last_login_at TEXT
                    )
                    """,
                )
            else:
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        full_name TEXT NOT NULL DEFAULT '',
                        company_name TEXT NOT NULL DEFAULT '',
                        country TEXT NOT NULL DEFAULT '',
                        assigned_countries TEXT NOT NULL DEFAULT '',
                        role TEXT NOT NULL DEFAULT 'user',
                        status TEXT NOT NULL DEFAULT 'pending',
                        created_at TEXT NOT NULL,
                        approved_at TEXT,
                        approved_by INTEGER,
                        last_login_at TEXT
                    )
                    """,
                )
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
            if self.backend == "postgres":
                self._execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name TEXT NOT NULL DEFAULT ''")
                self._execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS country TEXT NOT NULL DEFAULT ''")
                self._execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS assigned_countries TEXT NOT NULL DEFAULT ''")
            else:
                try:
                    self._execute(conn, "ALTER TABLE users ADD COLUMN company_name TEXT NOT NULL DEFAULT ''")
                except Exception:
                    pass
                try:
                    self._execute(conn, "ALTER TABLE users ADD COLUMN country TEXT NOT NULL DEFAULT ''")
                except Exception:
                    pass
                try:
                    self._execute(conn, "ALTER TABLE users ADD COLUMN assigned_countries TEXT NOT NULL DEFAULT ''")
                except Exception:
                    pass
            if self.backend == "postgres":
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS saved_quotes (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        company TEXT NOT NULL DEFAULT '',
                        project TEXT NOT NULL,
                        project_status TEXT NOT NULL DEFAULT 'draft',
                        contractor_name TEXT NOT NULL DEFAULT '',
                        consultant_name TEXT NOT NULL DEFAULT '',
                        project_notes TEXT NOT NULL DEFAULT '',
                        items_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """,
                )
            else:
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS saved_quotes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        company TEXT NOT NULL DEFAULT '',
                        project TEXT NOT NULL,
                        project_status TEXT NOT NULL DEFAULT 'draft',
                        contractor_name TEXT NOT NULL DEFAULT '',
                        consultant_name TEXT NOT NULL DEFAULT '',
                        project_notes TEXT NOT NULL DEFAULT '',
                        items_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """,
                )
            if self.backend == "postgres":
                self._execute(conn, "ALTER TABLE saved_quotes ADD COLUMN IF NOT EXISTS project_status TEXT NOT NULL DEFAULT 'draft'")
                self._execute(conn, "ALTER TABLE saved_quotes ADD COLUMN IF NOT EXISTS contractor_name TEXT NOT NULL DEFAULT ''")
                self._execute(conn, "ALTER TABLE saved_quotes ADD COLUMN IF NOT EXISTS consultant_name TEXT NOT NULL DEFAULT ''")
                self._execute(conn, "ALTER TABLE saved_quotes ADD COLUMN IF NOT EXISTS project_notes TEXT NOT NULL DEFAULT ''")
            else:
                try:
                    self._execute(conn, "ALTER TABLE saved_quotes ADD COLUMN project_status TEXT NOT NULL DEFAULT 'draft'")
                except Exception:
                    pass
                try:
                    self._execute(conn, "ALTER TABLE saved_quotes ADD COLUMN contractor_name TEXT NOT NULL DEFAULT ''")
                except Exception:
                    pass
                try:
                    self._execute(conn, "ALTER TABLE saved_quotes ADD COLUMN consultant_name TEXT NOT NULL DEFAULT ''")
                except Exception:
                    pass
                try:
                    self._execute(conn, "ALTER TABLE saved_quotes ADD COLUMN project_notes TEXT NOT NULL DEFAULT ''")
                except Exception:
                    pass
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_saved_quotes_user_id ON saved_quotes(user_id)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_saved_quotes_user_project ON saved_quotes(user_id, project)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_saved_quotes_user_created_at ON saved_quotes(user_id, created_at)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_saved_quotes_user_updated_at ON saved_quotes(user_id, updated_at)")
            if self.backend == "postgres":
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS refresh_sessions (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        token_hash TEXT NOT NULL UNIQUE,
                        issued_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        rotated_at TEXT,
                        revoked_at TEXT,
                        replaced_by_hash TEXT
                    )
                    """,
                )
            else:
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS refresh_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        token_hash TEXT NOT NULL UNIQUE,
                        issued_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        rotated_at TEXT,
                        revoked_at TEXT,
                        replaced_by_hash TEXT
                    )
                    """,
                )
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_refresh_sessions_user_id ON refresh_sessions(user_id)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_refresh_sessions_expires_at ON refresh_sessions(expires_at)")
            if self.backend == "postgres":
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        token_hash TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        used_at TEXT
                    )
                    """,
                )
            else:
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        token_hash TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        used_at TEXT
                    )
                    """,
                )
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id)")
            if self.backend == "postgres":
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL DEFAULT '',
                        is_secret BOOLEAN NOT NULL DEFAULT FALSE,
                        updated_at TEXT NOT NULL,
                        updated_by BIGINT
                    )
                    """,
                )
            else:
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL DEFAULT '',
                        is_secret INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT NOT NULL,
                        updated_by INTEGER
                    )
                    """,
                )
            if self.backend == "postgres":
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS consent_preferences (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                        session_id TEXT NOT NULL DEFAULT '',
                        analytics_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                        consent_version TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT '',
                        ip_hash TEXT NOT NULL DEFAULT '',
                        user_agent_hash TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """,
                )
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS activity_events (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                        session_id TEXT NOT NULL DEFAULT '',
                        event_type TEXT NOT NULL,
                        page TEXT NOT NULL DEFAULT '',
                        path TEXT NOT NULL DEFAULT '',
                        product_code TEXT NOT NULL DEFAULT '',
                        query_text TEXT NOT NULL DEFAULT '',
                        filters_json TEXT NOT NULL DEFAULT '{}',
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        consent_scope TEXT NOT NULL DEFAULT 'analytics',
                        ip_hash TEXT NOT NULL DEFAULT '',
                        user_agent_hash TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL
                    )
                    """,
                )
            else:
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS consent_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        session_id TEXT NOT NULL DEFAULT '',
                        analytics_enabled INTEGER NOT NULL DEFAULT 0,
                        consent_version TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT '',
                        ip_hash TEXT NOT NULL DEFAULT '',
                        user_agent_hash TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """,
                )
                self._execute(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS activity_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        session_id TEXT NOT NULL DEFAULT '',
                        event_type TEXT NOT NULL,
                        page TEXT NOT NULL DEFAULT '',
                        path TEXT NOT NULL DEFAULT '',
                        product_code TEXT NOT NULL DEFAULT '',
                        query_text TEXT NOT NULL DEFAULT '',
                        filters_json TEXT NOT NULL DEFAULT '{}',
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        consent_scope TEXT NOT NULL DEFAULT 'analytics',
                        ip_hash TEXT NOT NULL DEFAULT '',
                        user_agent_hash TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL
                    )
                    """,
                )
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_consent_preferences_user_id ON consent_preferences(user_id)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_consent_preferences_session_id ON consent_preferences(session_id)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_activity_events_created_at ON activity_events(created_at)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_activity_events_event_type ON activity_events(event_type)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_activity_events_user_id ON activity_events(user_id)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_activity_events_session_id ON activity_events(session_id)")
        self.ensure_bootstrap_admin()
        self.apply_runtime_overrides()

    def _access_cookie_max_age(self) -> int:
        return max(60, self.token_expire_minutes * 60)

    def _refresh_cookie_max_age(self) -> int:
        return max(3600, self.refresh_token_expire_days * 24 * 60 * 60)

    def _create_access_token(self, row: dict[str, Any]) -> str:
        now = _utc_now()
        return jwt.encode(
            {
                "sub": str(row["id"]),
                "email": str(row["email"]),
                "role": str(row["role"] or "user"),
                "status": str(row["status"] or "pending"),
                "exp": now + timedelta(minutes=self.token_expire_minutes),
                "iat": now,
            },
            self.jwt_secret,
            algorithm=self.jwt_algorithm,
        )

    def _hash_refresh_token(self, token: str) -> str:
        return hashlib.sha256(f"{self.jwt_secret}:{token}".encode("utf-8")).hexdigest()

    def _issue_refresh_token(self, user_id: int) -> str:
        token = secrets.token_urlsafe(48)
        token_hash = self._hash_refresh_token(token)
        issued_at = _utc_iso()
        expires_at = (_utc_now() + timedelta(days=self.refresh_token_expire_days)).isoformat()
        with self.connect() as conn:
            self._execute(
                conn,
                """
                INSERT INTO refresh_sessions (user_id, token_hash, issued_at, expires_at, rotated_at, revoked_at, replaced_by_hash)
                VALUES (?, ?, ?, ?, NULL, NULL, NULL)
                """,
                (int(user_id), token_hash, issued_at, expires_at),
            )
        return token

    def _delete_expired_refresh_sessions(self, conn: Any) -> None:
        self._execute(conn, "DELETE FROM refresh_sessions WHERE expires_at <= ?", (_utc_iso(),))

    def _rotate_refresh_token(self, refresh_token: str) -> tuple[str, UserPublic, str]:
        token_hash = self._hash_refresh_token(str(refresh_token or ""))
        now_iso = _utc_iso()
        with self.connect() as conn:
            self._delete_expired_refresh_sessions(conn)
            session = self._fetchone(
                conn,
                """
                SELECT rs.*, u.email, u.full_name, u.company_name, u.country, u.assigned_countries, u.role, u.status, u.created_at, u.approved_at, u.last_login_at
                FROM refresh_sessions rs
                JOIN users u ON u.id = rs.user_id
                WHERE rs.token_hash = ?
                """,
                (token_hash,),
            )
            if not session:
                raise HTTPException(status_code=401, detail="Invalid refresh session")
            if session.get("revoked_at"):
                raise HTTPException(status_code=401, detail="Refresh session revoked")
            if session.get("rotated_at"):
                raise HTTPException(status_code=401, detail="Refresh session already used")
            if str(session.get("status") or "pending") != "approved":
                raise HTTPException(status_code=403, detail="User is not approved")

            new_refresh = secrets.token_urlsafe(48)
            new_hash = self._hash_refresh_token(new_refresh)
            new_exp = (_utc_now() + timedelta(days=self.refresh_token_expire_days)).isoformat()
            self._execute(
                conn,
                """
                UPDATE refresh_sessions
                SET rotated_at = ?, replaced_by_hash = ?
                WHERE token_hash = ?
                """,
                (now_iso, new_hash, token_hash),
            )
            self._execute(
                conn,
                """
                INSERT INTO refresh_sessions (user_id, token_hash, issued_at, expires_at, rotated_at, revoked_at, replaced_by_hash)
                VALUES (?, ?, ?, ?, NULL, NULL, NULL)
                """,
                (int(session["user_id"]), new_hash, now_iso, new_exp),
            )
            fresh = self._fetchone(conn, "SELECT * FROM users WHERE id = ?", (int(session["user_id"]),))
        if not fresh:
            raise HTTPException(status_code=401, detail="User not found")
        return self._create_access_token(fresh), self._row_to_user(fresh), new_refresh

    def revoke_refresh_token(self, refresh_token: str) -> None:
        token_hash = self._hash_refresh_token(str(refresh_token or ""))
        if not token_hash:
            return
        with self.connect() as conn:
            self._execute(
                conn,
                "UPDATE refresh_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE token_hash = ?",
                (_utc_iso(), token_hash),
            )

    def set_auth_cookies(self, response: Response, *, access_token: str, refresh_token: str) -> None:
        response.set_cookie(
            key=self.access_cookie_name,
            value=access_token,
            httponly=True,
            secure=self.cookie_secure,
            samesite=self.cookie_samesite,
            max_age=self._access_cookie_max_age(),
            expires=self._access_cookie_max_age(),
            path="/",
        )
        response.set_cookie(
            key=self.refresh_cookie_name,
            value=refresh_token,
            httponly=True,
            secure=self.cookie_secure,
            samesite=self.cookie_samesite,
            max_age=self._refresh_cookie_max_age(),
            expires=self._refresh_cookie_max_age(),
            path="/auth",
        )

    def clear_auth_cookies(self, response: Response) -> None:
        response.delete_cookie(self.access_cookie_name, path="/")
        response.delete_cookie(self.refresh_cookie_name, path="/auth")

    def _consent_cookie_max_age(self) -> int:
        return 180 * 24 * 60 * 60

    def _analytics_session_max_age(self) -> int:
        return 30 * 24 * 60 * 60

    def create_analytics_session_id(self) -> str:
        return secrets.token_urlsafe(24)

    def _hash_tracking_value(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return hashlib.sha256(f"{self.jwt_secret}:tracking:{text}".encode("utf-8")).hexdigest()

    def encode_consent_cookie(self, *, analytics_enabled: bool, consent_version: str, updated_at: str) -> str:
        return json.dumps(
            {
                "analytics": bool(analytics_enabled),
                "version": str(consent_version or "").strip() or "2026-03-31",
                "updated_at": str(updated_at or "").strip() or _utc_iso(),
            },
            separators=(",", ":"),
        )

    def decode_consent_cookie(self, raw: str) -> dict[str, Any]:
        text = str(raw or "").strip()
        if not text:
            return {"analytics": False, "version": "", "updated_at": ""}
        try:
            data = json.loads(text)
        except Exception:
            return {"analytics": False, "version": "", "updated_at": ""}
        return {
            "analytics": bool(data.get("analytics")),
            "version": str(data.get("version") or "").strip(),
            "updated_at": str(data.get("updated_at") or "").strip(),
        }

    def set_consent_cookies(
        self,
        response: Response,
        *,
        analytics_enabled: bool,
        consent_version: str,
        analytics_session_id: str = "",
        updated_at: str = "",
    ) -> None:
        payload = self.encode_consent_cookie(
            analytics_enabled=bool(analytics_enabled),
            consent_version=consent_version,
            updated_at=updated_at or _utc_iso(),
        )
        response.set_cookie(
            key=self.consent_cookie_name,
            value=payload,
            httponly=False,
            secure=self.cookie_secure,
            samesite=self.cookie_samesite,
            max_age=self._consent_cookie_max_age(),
            expires=self._consent_cookie_max_age(),
            path="/",
        )
        if analytics_enabled and analytics_session_id:
            response.set_cookie(
                key=self.analytics_session_cookie_name,
                value=str(analytics_session_id).strip(),
                httponly=False,
                secure=self.cookie_secure,
                samesite=self.cookie_samesite,
                max_age=self._analytics_session_max_age(),
                expires=self._analytics_session_max_age(),
                path="/",
            )
        else:
            response.delete_cookie(self.analytics_session_cookie_name, path="/")

    def consent_from_request(self, request: Request) -> dict[str, Any]:
        return self.decode_consent_cookie(str(request.cookies.get(self.consent_cookie_name) or ""))

    def analytics_session_from_request(self, request: Request) -> str:
        return str(request.cookies.get(self.analytics_session_cookie_name) or "").strip()

    def upsert_consent_preference(
        self,
        *,
        analytics_enabled: bool,
        consent_version: str,
        source: str = "",
        user_id: int | None = None,
        session_id: str = "",
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict[str, Any]:
        now = _utc_iso()
        clean_session = str(session_id or "").strip()
        existing = None
        with self.connect() as conn:
            if user_id:
                existing = self._fetchone(conn, "SELECT * FROM consent_preferences WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1", (int(user_id),))
            elif clean_session:
                existing = self._fetchone(conn, "SELECT * FROM consent_preferences WHERE session_id = ? ORDER BY updated_at DESC LIMIT 1", (clean_session,))
            if existing:
                self._execute(
                    conn,
                    """
                    UPDATE consent_preferences
                    SET user_id = ?, session_id = ?, analytics_enabled = ?, consent_version = ?, source = ?, ip_hash = ?, user_agent_hash = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        int(user_id) if user_id else None,
                        clean_session,
                        bool(analytics_enabled),
                        str(consent_version or "").strip(),
                        str(source or "").strip(),
                        self._hash_tracking_value(ip_address),
                        self._hash_tracking_value(user_agent),
                        now,
                        int(existing["id"]),
                    ),
                )
                row_id = int(existing["id"])
            else:
                self._execute(
                    conn,
                    """
                    INSERT INTO consent_preferences (user_id, session_id, analytics_enabled, consent_version, source, ip_hash, user_agent_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(user_id) if user_id else None,
                        clean_session,
                        bool(analytics_enabled),
                        str(consent_version or "").strip(),
                        str(source or "").strip(),
                        self._hash_tracking_value(ip_address),
                        self._hash_tracking_value(user_agent),
                        now,
                        now,
                    ),
                )
                created = self._fetchone(
                    conn,
                    "SELECT * FROM consent_preferences WHERE (user_id = ? AND ? IS NOT NULL) OR (session_id = ? AND ? <> '') ORDER BY id DESC LIMIT 1",
                    (int(user_id) if user_id else None, int(user_id) if user_id else None, clean_session, clean_session),
                )
                row_id = int((created or {}).get("id") or 0)
        return {
            "id": row_id,
            "analytics": bool(analytics_enabled),
            "version": str(consent_version or "").strip(),
            "source": str(source or "").strip(),
            "updated_at": now,
        }

    def record_activity_event(
        self,
        *,
        event_type: str,
        user_id: int | None = None,
        session_id: str = "",
        page: str = "",
        path: str = "",
        product_code: str = "",
        query_text: str = "",
        filters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        ip_address: str = "",
        user_agent: str = "",
        consent_scope: str = "analytics",
    ) -> None:
        evt = str(event_type or "").strip().lower()
        if not evt:
            return
        filters_json = json.dumps(filters or {}, ensure_ascii=True, separators=(",", ":"))
        metadata_json = json.dumps(metadata or {}, ensure_ascii=True, separators=(",", ":"))
        with self.connect() as conn:
            self._execute(
                conn,
                """
                INSERT INTO activity_events (
                    user_id, session_id, event_type, page, path, product_code, query_text,
                    filters_json, metadata_json, consent_scope, ip_hash, user_agent_hash, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id) if user_id else None,
                    str(session_id or "").strip()[:120],
                    evt[:80],
                    str(page or "").strip()[:200],
                    str(path or "").strip()[:200],
                    str(product_code or "").strip()[:120],
                    str(query_text or "").strip()[:500],
                    filters_json[:4000],
                    metadata_json[:4000],
                    str(consent_scope or "analytics").strip()[:40],
                    self._hash_tracking_value(ip_address),
                    self._hash_tracking_value(user_agent),
                    _utc_iso(),
                ),
            )

    def _activity_rows_since(self, since_iso: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return self._fetchall(
                conn,
                """
                SELECT ae.*, u.email, u.full_name, u.company_name, u.country
                FROM activity_events ae
                LEFT JOIN users u ON u.id = ae.user_id
                WHERE ae.created_at >= ?
                ORDER BY ae.created_at DESC
                """,
                (since_iso,),
            )

    @staticmethod
    def _safe_json_object(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def get_analytics_summary(self, viewer: UserPublic, *, days: int = 30, top_n: int = 10) -> dict[str, Any]:
        days = max(1, min(int(days or 30), 365))
        since_iso = (_utc_now() - timedelta(days=days)).isoformat()
        rows = self._activity_rows_since(since_iso)
        role = str(viewer.role or "user").lower()
        if role == ROLE_MANAGER:
            allowed = {str(item).strip().lower() for item in (viewer.assigned_countries or []) if str(item).strip()}
            rows = [r for r in rows if str(r.get("country") or "").strip().lower() in allowed]
        total_events = len(rows)
        search_rows = [r for r in rows if str(r.get("event_type") or "") == "search"]
        auth_user_ids = {int(r["user_id"]) for r in rows if r.get("user_id") is not None}
        sessions = {str(r.get("session_id") or "").strip() for r in rows if str(r.get("session_id") or "").strip()}
        event_counts: dict[str, int] = {}
        query_counts: dict[str, int] = {}
        country_counts: dict[str, int] = {}
        no_result_query_counts: dict[str, int] = {}
        no_exact_query_counts: dict[str, int] = {}
        family_counts: dict[str, int] = {}
        gap_family_counts: dict[str, int] = {}
        gap_groups: dict[str, dict[str, Any]] = {}
        company_stats: dict[str, dict[str, Any]] = {}
        country_stats: dict[str, dict[str, Any]] = {}
        user_counts: dict[str, dict[str, Any]] = {}
        journey_sessions: dict[str, set[str]] = {}
        product_views: dict[str, int] = {}
        product_compares: dict[str, int] = {}
        product_quotes: dict[str, int] = {}
        product_intent: dict[str, dict[str, int]] = {}
        quote_funnel = {
            "saved": 0,
            "updated": 0,
            "exported_pdf": 0,
            "datasheets_zip": 0,
        }
        journey_stage_order = [
            ("search_started", "Search started"),
            ("search_with_results", "Search with results"),
            ("product_interaction", "Product interaction"),
            ("compare_used", "Compare used"),
            ("quote_built", "Quote built"),
            ("quote_exported", "Quote exported"),
        ]
        zero_result_searches = 0
        searches_without_exact = 0
        for row in rows:
            evt = str(row.get("event_type") or "").strip() or "unknown"
            metadata = self._safe_json_object(row.get("metadata_json"))
            filters = self._safe_json_object(row.get("filters_json"))
            event_counts[evt] = event_counts.get(evt, 0) + 1
            country = str(row.get("country") or "").strip()
            session_id = str(row.get("session_id") or "").strip()
            if country:
                country_counts[country] = country_counts.get(country, 0) + 1
            company_name = str(row.get("company_name") or "").strip()
            if company_name:
                company_bucket = company_stats.setdefault(
                    company_name,
                    {
                        "company_name": company_name,
                        "events": 0,
                        "searches": 0,
                        "quote_exports": 0,
                        "quote_saves": 0,
                        "sessions": set(),
                    },
                )
                company_bucket["events"] += 1
                if evt == "search":
                    company_bucket["searches"] += 1
                if evt == "quote_export_pdf":
                    company_bucket["quote_exports"] += 1
                if evt == "quote_save":
                    company_bucket["quote_saves"] += 1
                if session_id:
                    company_bucket["sessions"].add(session_id)
            if country:
                country_bucket = country_stats.setdefault(
                    country,
                    {
                        "country": country,
                        "events": 0,
                        "searches": 0,
                        "quote_exports": 0,
                        "quote_saves": 0,
                        "sessions": set(),
                    },
                )
                country_bucket["events"] += 1
                if evt == "search":
                    country_bucket["searches"] += 1
                if evt == "quote_export_pdf":
                    country_bucket["quote_exports"] += 1
                if evt == "quote_save":
                    country_bucket["quote_saves"] += 1
                if session_id:
                    country_bucket["sessions"].add(session_id)
            session_flags = journey_sessions.setdefault(session_id, set()) if session_id else None
            product_code = str(row.get("product_code") or "").strip()
            if session_flags is not None:
                if evt == "search":
                    session_flags.add("search_started")
                    has_any_result = bool(metadata.get("has_any_result"))
                    if not has_any_result:
                        has_any_result = (int(metadata.get("exact_count") or 0) + int(metadata.get("similar_count") or 0)) > 0
                    if has_any_result:
                        session_flags.add("search_with_results")
                elif evt in {"product_open_datasheet", "product_open_website"}:
                    session_flags.add("product_interaction")
                elif evt in {"compare_add_from_search", "compare_codes", "compare_products", "compare_spec_products", "alternatives", "alternatives_from_spec", "compare_export_pdf"}:
                    session_flags.add("compare_used")
                elif evt in {"quote_add_from_search", "quote_save", "quote_update"}:
                    session_flags.add("quote_built")
                elif evt in {"quote_export_pdf", "quote_datasheets_zip"}:
                    session_flags.add("quote_exported")
            if product_code:
                intent_bucket = product_intent.setdefault(
                    product_code,
                    {"views": 0, "compares": 0, "quotes": 0},
                )
                if evt in {"product_open_datasheet", "product_open_website"}:
                    product_views[product_code] = product_views.get(product_code, 0) + 1
                    intent_bucket["views"] += 1
                elif evt in {"compare_add_from_search", "compare_codes", "compare_products", "compare_spec_products", "compare_export_pdf"}:
                    product_compares[product_code] = product_compares.get(product_code, 0) + 1
                    intent_bucket["compares"] += 1
                elif evt in {"quote_add_from_search"}:
                    product_quotes[product_code] = product_quotes.get(product_code, 0) + 1
                    intent_bucket["quotes"] += 1
            uid = row.get("user_id")
            if uid is not None:
                key = str(uid)
                user_counts[key] = user_counts.get(
                    key,
                    {
                        "user_id": int(uid),
                        "email": str(row.get("email") or ""),
                        "full_name": str(row.get("full_name") or ""),
                        "company_name": str(row.get("company_name") or ""),
                        "country": country,
                        "events": 0,
                    },
                )
                user_counts[key]["events"] += 1
        for row in search_rows:
            metadata = self._safe_json_object(row.get("metadata_json"))
            filters = self._safe_json_object(row.get("filters_json"))
            q = str(row.get("query_text") or "").strip()
            if not q:
                q = "(empty query)"
            query_counts[q] = query_counts.get(q, 0) + 1
            exact_count = int(metadata.get("exact_count") or 0)
            similar_count = int(metadata.get("similar_count") or 0)
            if exact_count <= 0:
                searches_without_exact += 1
                no_exact_query_counts[q] = no_exact_query_counts.get(q, 0) + 1
            if (exact_count + similar_count) <= 0:
                zero_result_searches += 1
                no_result_query_counts[q] = no_result_query_counts.get(q, 0) + 1
            family = str(metadata.get("requested_family") or "").strip() or str(filters.get("product_family") or "").strip()
            if family:
                family_counts[family] = family_counts.get(family, 0) + 1
            if exact_count <= 0:
                gap_label = family or "Unclassified search"
                gap_family_counts[gap_label] = gap_family_counts.get(gap_label, 0) + 1
                gap_key = f"{gap_label.lower()}|{q.lower()}"
                bucket = gap_groups.get(gap_key)
                if bucket is None:
                    bucket = {
                        "family": gap_label,
                        "example_query": q,
                        "searches": 0,
                        "no_exact_count": 0,
                        "zero_result_count": 0,
                        "closest_only_count": 0,
                    }
                    gap_groups[gap_key] = bucket
                bucket["searches"] += 1
                bucket["no_exact_count"] += 1
                if (exact_count + similar_count) <= 0:
                    bucket["zero_result_count"] += 1
                else:
                    bucket["closest_only_count"] += 1
        quote_funnel["saved"] = int(event_counts.get("quote_save", 0))
        quote_funnel["updated"] = int(event_counts.get("quote_update", 0))
        quote_funnel["exported_pdf"] = int(event_counts.get("quote_export_pdf", 0))
        quote_funnel["datasheets_zip"] = int(event_counts.get("quote_datasheets_zip", 0))
        journey_funnel = []
        previous_sessions = 0
        for stage_key, stage_label in journey_stage_order:
            session_count = sum(1 for flags in journey_sessions.values() if stage_key in flags)
            conversion_from_previous = None
            if previous_sessions > 0:
                conversion_from_previous = round((session_count / previous_sessions) * 100, 1)
            journey_funnel.append(
                {
                    "key": stage_key,
                    "label": stage_label,
                    "sessions": session_count,
                    "conversion_from_previous": conversion_from_previous,
                }
            )
            previous_sessions = session_count
        recent = []
        for row in rows[:50]:
            recent.append(
                {
                    "created_at": str(row.get("created_at") or ""),
                    "event_type": str(row.get("event_type") or ""),
                    "email": str(row.get("email") or ""),
                    "full_name": str(row.get("full_name") or ""),
                    "company_name": str(row.get("company_name") or ""),
                    "country": str(row.get("country") or ""),
                    "query_text": str(row.get("query_text") or ""),
                    "product_code": str(row.get("product_code") or ""),
                    "page": str(row.get("page") or ""),
                    "path": str(row.get("path") or ""),
                    "metadata": json.loads(str(row.get("metadata_json") or "{}") or "{}"),
                }
            )
        return {
            "days": days,
            "generated_at": _utc_iso(),
            "totals": {
                "events": total_events,
                "searches": len(search_rows),
                "known_users": len(auth_user_ids),
                "sessions": len(sessions),
                "zero_result_searches": zero_result_searches,
                "searches_without_exact": searches_without_exact,
                "quote_exports": quote_funnel["exported_pdf"],
                "quote_saves": quote_funnel["saved"],
            },
            "top_events": [{"event_type": k, "count": v} for k, v in sorted(event_counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_searches": [{"query_text": k, "count": v} for k, v in sorted(query_counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_no_result_searches": [{"query_text": k, "count": v} for k, v in sorted(no_result_query_counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_searches_without_exact": [{"query_text": k, "count": v} for k, v in sorted(no_exact_query_counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_requested_families": [{"family": k, "count": v} for k, v in sorted(family_counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_gap_families": [{"family": k, "count": v} for k, v in sorted(gap_family_counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_viewed_products": [{"product_code": k, "count": v} for k, v in sorted(product_views.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_compared_products": [{"product_code": k, "count": v} for k, v in sorted(product_compares.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_quoted_products": [{"product_code": k, "count": v} for k, v in sorted(product_quotes.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_product_intent": [
                {
                    "product_code": code,
                    "views": int(counts.get("views") or 0),
                    "compares": int(counts.get("compares") or 0),
                    "quotes": int(counts.get("quotes") or 0),
                    "intent_score": int((counts.get("quotes") or 0) * 3 + (counts.get("compares") or 0) * 2 + (counts.get("views") or 0)),
                }
                for code, counts in sorted(
                    product_intent.items(),
                    key=lambda item: (
                        -int((item[1].get("quotes") or 0) * 3 + (item[1].get("compares") or 0) * 2 + (item[1].get("views") or 0)),
                        item[0],
                    ),
                )[:top_n]
            ],
            "top_catalog_gaps": [
                {
                    **bucket,
                    "gap_type": (
                        "no_result"
                        if int(bucket.get("zero_result_count") or 0) >= int(bucket.get("closest_only_count") or 0)
                        else "closest_only"
                    ),
                }
                for bucket in sorted(
                    gap_groups.values(),
                    key=lambda item: (
                        -int(item.get("no_exact_count") or 0),
                        -int(item.get("zero_result_count") or 0),
                        str(item.get("family") or ""),
                        str(item.get("example_query") or ""),
                    ),
                )[:top_n]
            ],
            "top_companies": [
                {
                    "company_name": bucket["company_name"],
                    "events": int(bucket["events"]),
                    "searches": int(bucket["searches"]),
                    "quote_saves": int(bucket["quote_saves"]),
                    "quote_exports": int(bucket["quote_exports"]),
                    "sessions": len(bucket["sessions"]),
                }
                for bucket in sorted(
                    company_stats.values(),
                    key=lambda item: (
                        -int(item.get("quote_exports") or 0),
                        -int(item.get("quote_saves") or 0),
                        -int(item.get("searches") or 0),
                        -int(item.get("events") or 0),
                        str(item.get("company_name") or ""),
                    ),
                )[:top_n]
            ],
            "country_insights": [
                {
                    "country": bucket["country"],
                    "events": int(bucket["events"]),
                    "searches": int(bucket["searches"]),
                    "quote_saves": int(bucket["quote_saves"]),
                    "quote_exports": int(bucket["quote_exports"]),
                    "sessions": len(bucket["sessions"]),
                }
                for bucket in sorted(
                    country_stats.values(),
                    key=lambda item: (
                        -int(item.get("quote_exports") or 0),
                        -int(item.get("quote_saves") or 0),
                        -int(item.get("searches") or 0),
                        -int(item.get("events") or 0),
                        str(item.get("country") or ""),
                    ),
                )[:top_n]
            ],
            "top_countries": [{"country": k, "count": v} for k, v in sorted(country_counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]],
            "top_users": sorted(user_counts.values(), key=lambda item: (-int(item.get("events") or 0), str(item.get("email") or "")))[:top_n],
            "quote_funnel": quote_funnel,
            "journey_funnel": journey_funnel,
            "recent_events": recent,
        }

    def _stored_settings_map(self) -> dict[str, dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(conn, "SELECT * FROM app_settings")
        return {str(row.get("key") or ""): row for row in rows if str(row.get("key") or "").strip()}

    def apply_runtime_overrides(self) -> None:
        stored = self._stored_settings_map()
        for definition in SETTINGS_CATALOG:
            row = stored.get(definition.key)
            if row is not None:
                os.environ[definition.env_name] = str(row.get("value") or "")
            elif definition.env_name not in os.environ:
                continue

        self.jwt_secret = str(os.getenv("AUTH_JWT_SECRET", self.jwt_secret)).strip() or self.jwt_secret
        self.token_expire_minutes = int(os.getenv("AUTH_TOKEN_EXPIRE_MINUTES", str(self.token_expire_minutes)) or str(self.token_expire_minutes))
        self.cookie_secure = str(os.getenv("AUTH_COOKIE_SECURE", "1" if self.cookie_secure else "0")).strip().lower() in {"1", "true", "yes", "on"}
        self.cookie_samesite = str(os.getenv("AUTH_COOKIE_SAMESITE", self.cookie_samesite)).strip().lower() or self.cookie_samesite
        self.bootstrap_email = str(os.getenv("ADMIN_BOOTSTRAP_EMAIL", self.bootstrap_email)).strip().lower()
        self.bootstrap_password = str(os.getenv("ADMIN_BOOTSTRAP_PASSWORD", self.bootstrap_password)).strip()
        self.bootstrap_name = str(os.getenv("ADMIN_BOOTSTRAP_NAME", self.bootstrap_name)).strip() or self.bootstrap_name
        if self.bootstrap_email and self.bootstrap_password:
            self.ensure_bootstrap_admin()

    def list_admin_settings(self) -> list[AdminSettingPublic]:
        stored = self._stored_settings_map()
        items: list[AdminSettingPublic] = []
        for definition in SETTINGS_CATALOG:
            row = stored.get(definition.key) or {}
            raw_value = str(row.get("value") if row else os.getenv(definition.env_name, "")).strip()
            items.append(
                AdminSettingPublic(
                    key=definition.key,
                    label=definition.label,
                    category=definition.category,
                    description=definition.description,
                    value="" if definition.secret else raw_value,
                    secret=definition.secret,
                    configured=bool(raw_value),
                    masked_value=mask_secret_value(raw_value) if definition.secret else raw_value,
                    restart_required=definition.restart_required,
                    multiline=definition.multiline,
                    placeholder=definition.placeholder,
                    updated_at=str(row.get("updated_at") or "") or None,
                    updated_by=int(row["updated_by"]) if row and row.get("updated_by") is not None else None,
                )
            )
        category_index = {name: idx for idx, name in enumerate(CATEGORY_ORDER)}
        return sorted(items, key=lambda item: (category_index.get(item.category, 999), item.label.lower()))

    def update_admin_setting(self, key: str, value: str, *, acting_admin_id: int) -> AdminSettingPublic:
        definition = SETTINGS_BY_KEY.get(str(key or "").strip())
        if not definition:
            raise HTTPException(status_code=404, detail="Unknown setting")
        existing_row = self._stored_settings_map().get(definition.key) or {}
        existing_value = str(existing_row.get("value") or os.getenv(definition.env_name, "")).strip()
        try:
            normalized = normalize_setting_value(definition, value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if definition.secret and not normalized and existing_value:
            normalized = existing_value
        now = _utc_iso()
        with self.connect() as conn:
            if normalized:
                self._execute(
                    conn,
                    """
                    INSERT INTO app_settings (key, value, is_secret, updated_at, updated_by)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        is_secret = excluded.is_secret,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (definition.key, normalized, bool(definition.secret), now, int(acting_admin_id)),
                )
            else:
                self._execute(conn, "DELETE FROM app_settings WHERE key = ?", (definition.key,))
        if definition.immediate_apply:
            if normalized:
                os.environ[definition.env_name] = normalized
            else:
                os.environ.pop(definition.env_name, None)
            self.apply_runtime_overrides()
        current = next((item for item in self.list_admin_settings() if item.key == definition.key), None)
        if not current:
            raise HTTPException(status_code=500, detail="Setting update could not be confirmed")
        return current

    def _smtp_settings(self) -> dict[str, str]:
        return {
            "host": str(os.getenv("SMTP_HOST", "")).strip(),
            "port": str(os.getenv("SMTP_PORT", "587")).strip(),
            "username": str(os.getenv("SMTP_USERNAME", "")).strip(),
            "password": str(os.getenv("SMTP_PASSWORD", "")).strip(),
            "from_email": str(os.getenv("SMTP_FROM_EMAIL", "")).strip(),
        }

    def _notification_owner_email(self) -> str:
        return str(os.getenv("SMTP_FROM_EMAIL", "") or "").strip().lower()

    def _send_email(self, *, to_email: str, subject: str, body: str) -> None:
        smtp = self._smtp_settings()
        recipient = str(to_email or "").strip()
        if not recipient:
            return
        if not smtp["host"] or not smtp["from_email"]:
            print(f"[email] {recipient} | {subject}\n{body}")
            return
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = smtp["from_email"]
        msg["To"] = recipient
        msg.set_content(body)
        port = int(smtp["port"] or "587")
        with smtplib.SMTP(smtp["host"], port, timeout=20) as server:
            server.ehlo()
            if port in {587, 25}:
                try:
                    server.starttls()
                    server.ehlo()
                except Exception:
                    pass
            if smtp["username"] and smtp["password"]:
                server.login(smtp["username"], smtp["password"])
            server.send_message(msg)

    def _build_password_reset_url(self, token: str) -> str:
        domain = str(os.getenv("APP_DOMAIN", "")).strip()
        if domain:
            base = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
        else:
            base = "http://localhost:8000"
        return f"{base.rstrip('/')}/frontend/reset-password.html?token={token}"

    def _send_password_reset_email(self, *, to_email: str, reset_url: str) -> None:
        self._send_email(
            to_email=to_email,
            subject="Reset your Laiting password",
            body=(
            "A password reset was requested for your Laiting account.\n\n"
            f"Open this link to set a new password:\n{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
            ),
        )

    def _send_signup_request_notifications(
        self,
        *,
        user_email: str,
        full_name: str,
        company_name: str,
        country: str,
    ) -> None:
        owner_email = self._notification_owner_email()
        user_name = str(full_name or "").strip() or "there"
        company_line = str(company_name or "").strip() or "Not provided"
        country_line = str(country or "").strip() or "Not provided"
        if owner_email:
            self._send_email(
                to_email=owner_email,
                subject="New Laiting access request",
                body=(
                    "A new access request was submitted in Laiting.\n\n"
                    f"Name: {user_name}\n"
                    f"Email: {user_email}\n"
                    f"Company: {company_line}\n"
                    f"Country: {country_line}\n\n"
                    "Open the admin panel to review and approve the account."
                ),
            )
        self._send_email(
            to_email=user_email,
            subject="We received your Laiting access request",
            body=(
                f"Hello {user_name},\n\n"
                "We received your access request for Laiting.\n"
                "Your account is now pending review, and you will be able to sign in after approval.\n\n"
                f"Company: {company_line}\n"
                f"Country: {country_line}\n\n"
                "We will email you again as soon as your access is approved."
            ),
        )

    def _send_approval_email(self, *, to_email: str, full_name: str) -> None:
        user_name = str(full_name or "").strip() or "there"
        self._send_email(
            to_email=to_email,
            subject="Your Laiting access has been approved",
            body=(
                f"Hello {user_name},\n\n"
                "Your Laiting account has been approved.\n"
                "You can now sign in and start using the platform.\n\n"
                "If you did not request this account, please reply to this email."
            ),
        )

    def request_password_reset(self, email: str) -> dict[str, Any]:
        user = self._get_user_row_by_email(email)
        if not user or str(user.get("status") or "pending") != "approved":
            return {"success": True}
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_refresh_token(token)
        now = _utc_iso()
        expires_at = (_utc_now() + timedelta(hours=1)).isoformat()
        with self.connect() as conn:
            self._execute(conn, "DELETE FROM password_reset_tokens WHERE user_id = ?", (int(user["id"]),))
            self._execute(
                conn,
                """
                INSERT INTO password_reset_tokens (user_id, token_hash, created_at, expires_at, used_at)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (int(user["id"]), token_hash, now, expires_at),
            )
        reset_url = self._build_password_reset_url(token)
        self._send_password_reset_email(to_email=str(user["email"]), reset_url=reset_url)
        return {"success": True}

    def confirm_password_reset(self, token: str, new_password: str) -> dict[str, Any]:
        password = str(new_password or "")
        if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise HTTPException(status_code=400, detail="Password must contain letters and numbers")
        token_hash = self._hash_refresh_token(str(token or ""))
        now = _utc_iso()
        with self.connect() as conn:
            self._delete_expired_refresh_sessions(conn)
            row = self._fetchone(
                conn,
                """
                SELECT prt.*, u.email
                FROM password_reset_tokens prt
                JOIN users u ON u.id = prt.user_id
                WHERE prt.token_hash = ?
                """,
                (token_hash,),
            )
            if not row or row.get("used_at") or str(row.get("expires_at") or "") <= now:
                raise HTTPException(status_code=400, detail="Password reset link is invalid or expired")
            self._execute(
                conn,
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (_password_hash(password), int(row["user_id"])),
            )
            self._execute(
                conn,
                "UPDATE password_reset_tokens SET used_at = ? WHERE token_hash = ?",
                (now, token_hash),
            )
            self._execute(
                conn,
                "UPDATE refresh_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE user_id = ?",
                (now, int(row["user_id"])),
            )
        return {"success": True}

    def ensure_bootstrap_admin(self) -> None:
        if not self.bootstrap_email or not self.bootstrap_password:
            return
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT id, role, status, approved_at FROM users WHERE LOWER(email) = LOWER(?)", (self.bootstrap_email,))
            if row:
                self._execute(
                    conn,
                    """
                    UPDATE users
                    SET password_hash = ?, full_name = ?, company_name = COALESCE(company_name, ''), assigned_countries = COALESCE(assigned_countries, ''), role = 'admin', status = 'approved', approved_at = COALESCE(approved_at, ?)
                    WHERE id = ?
                    """,
                    (_password_hash(self.bootstrap_password), self.bootstrap_name, _utc_iso(), int(row["id"])),
                )
            else:
                self._execute(
                    conn,
                    """
                    INSERT INTO users (email, password_hash, full_name, company_name, country, assigned_countries, role, status, created_at, approved_at)
                    VALUES (?, ?, ?, '', '', '', 'admin', 'approved', ?, ?)
                    """,
                    (self.bootstrap_email, _password_hash(self.bootstrap_password), self.bootstrap_name, _utc_iso(), _utc_iso()),
                )

    def _row_to_user(self, row: dict[str, Any]) -> UserPublic:
        return UserPublic(
            id=int(row["id"]),
            email=str(row["email"]),
            full_name=str(row.get("full_name") or ""),
            company_name=str(row.get("company_name") or ""),
            country=str(row.get("country") or ""),
            assigned_countries=self._parse_assigned_countries(row.get("assigned_countries")),
            role=str(row.get("role") or "user"),
            status=str(row.get("status") or "pending"),
            created_at=str(row.get("created_at") or ""),
            approved_at=row.get("approved_at"),
            last_login_at=row.get("last_login_at"),
        )

    def _get_user_row_by_email(self, email: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            return self._fetchone(conn, "SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (str(email or "").strip(),))

    def _get_user_row_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            return self._fetchone(conn, "SELECT * FROM users WHERE id = ?", (int(user_id),))

    def create_signup(self, payload: SignupRequest) -> UserPublic:
        email = str(payload.email).strip().lower()
        full_name = str(payload.full_name or "").strip()
        company_name = str(payload.company_name or "").strip()
        country = str(payload.country or "").strip()
        password = str(payload.password or "")
        if not country:
            raise HTTPException(status_code=400, detail="Country is required")
        if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise HTTPException(status_code=400, detail="Password must contain letters and numbers")
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            if existing:
                raise HTTPException(status_code=409, detail="Email already registered")
            now = _utc_iso()
            self._execute(
                conn,
                """
                INSERT INTO users (email, password_hash, full_name, company_name, country, role, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'user', 'pending', ?)
                """,
                (email, _password_hash(password), full_name, company_name, country, now),
            )
            row = self._fetchone(conn, "SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create user")
        user = self._row_to_user(row)
        self._send_signup_request_notifications(
            user_email=user.email,
            full_name=user.full_name,
            company_name=user.company_name,
            country=user.country,
        )
        return user

    def authenticate(self, payload: LoginRequest) -> AuthTokenResponse:
        row = self._get_user_row_by_email(str(payload.email))
        if not row or not _verify_password(str(payload.password or ""), str(row["password_hash"] or "")):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        status = str(row["status"] or "pending")
        if status != "approved":
            raise HTTPException(status_code=403, detail=f"Account status is {status}")
        token = self._create_access_token(row)
        refresh_token = self._issue_refresh_token(int(row["id"]))
        with self.connect() as conn:
            self._execute(conn, "UPDATE users SET last_login_at = ? WHERE id = ?", (_utc_iso(), int(row["id"])))
            fresh = self._fetchone(conn, "SELECT * FROM users WHERE id = ?", (int(row["id"]),))
        if not fresh:
            raise HTTPException(status_code=500, detail="Failed to refresh authenticated user")
        return AuthTokenResponse(access_token=token, refresh_token=refresh_token, user=self._row_to_user(fresh))

    def refresh_session(self, refresh_token: str) -> AuthTokenResponse:
        access_token, user, new_refresh = self._rotate_refresh_token(refresh_token)
        return AuthTokenResponse(access_token=access_token, refresh_token=new_refresh, user=user)

    def decode_token(self, token: str) -> UserPublic:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            user_id = int(payload.get("sub") or 0)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        row = self._get_user_row_by_id(user_id)
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
        if str(row["status"] or "pending") != "approved":
            raise HTTPException(status_code=403, detail="User is not approved")
        return self._row_to_user(row)

    def list_users(self, *, status: Optional[str] = None) -> list[UserPublic]:
        query = "SELECT * FROM users"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC"
        with self.connect() as conn:
            rows = self._fetchall(conn, query, params)
        return [self._row_to_user(r) for r in rows]

    def list_visible_users(self, viewer: UserPublic, *, status: Optional[str] = None) -> list[UserPublic]:
        role = str(viewer.role or "user").lower()
        users = self.list_users(status=status)
        if role in LEADERSHIP_ROLES:
            return users
        if role != ROLE_MANAGER:
            return []
        allowed = {str(item).strip().lower() for item in (viewer.assigned_countries or []) if str(item).strip()}
        if not allowed:
            return []
        return [user for user in users if str(user.country or "").strip().lower() in allowed]

    def can_view_user(self, viewer: UserPublic, user: UserPublic) -> bool:
        role = str(viewer.role or "user").lower()
        if role in LEADERSHIP_ROLES:
            return True
        if role != ROLE_MANAGER:
            return False
        allowed = {str(item).strip().lower() for item in (viewer.assigned_countries or []) if str(item).strip()}
        return str(user.country or "").strip().lower() in allowed

    def _allowed_assignable_roles(self, actor_role: str) -> set[str]:
        role = str(actor_role or ROLE_USER).strip().lower() or ROLE_USER
        if role == ROLE_ADMIN:
            return set(ROLE_ORDER)
        if role == ROLE_DIRECTOR:
            return {ROLE_USER, ROLE_MANAGER, ROLE_DIRECTOR}
        return set()

    def _get_actor_role(self, acting_user_id: int) -> str:
        actor = self._get_user_row_by_id(int(acting_user_id))
        if not actor:
            raise HTTPException(status_code=404, detail="Acting user not found")
        role = str(actor.get("role") or ROLE_USER).strip().lower() or ROLE_USER
        if role not in LEADERSHIP_ROLES:
            raise HTTPException(status_code=403, detail="Director or admin privileges required")
        return role

    def _assert_can_manage_target_role(self, *, actor_role: str, target_current_role: str, next_role: str) -> None:
        if actor_role != ROLE_ADMIN and target_current_role == ROLE_ADMIN:
            raise HTTPException(status_code=403, detail="Only admins can manage admin accounts")
        if next_role not in self._allowed_assignable_roles(actor_role):
            raise HTTPException(status_code=403, detail="You cannot assign this role")

    def _change_status(
        self,
        user_id: int,
        *,
        status: str,
        acting_admin_id: int,
        role: str | None = None,
        assigned_countries: list[str] | None = None,
    ) -> UserPublic:
        actor_role = self._get_actor_role(int(acting_admin_id))
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM users WHERE id = ?", (int(user_id),))
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            if int(row["id"]) == int(acting_admin_id) and status != "approved":
                raise HTTPException(status_code=400, detail="Admin cannot change own account to non-approved")
            approved_at = _utc_iso() if status == "approved" else None
            current_role = str(row.get("role") or ROLE_USER).strip().lower() or ROLE_USER
            next_role = str(role or row.get("role") or ROLE_USER).strip().lower() or ROLE_USER
            if next_role not in ROLE_ORDER:
                raise HTTPException(status_code=400, detail="Invalid role")
            self._assert_can_manage_target_role(
                actor_role=actor_role,
                target_current_role=current_role,
                next_role=next_role,
            )
            next_assigned_countries = self._serialize_assigned_countries(
                assigned_countries if assigned_countries is not None else self._parse_assigned_countries(row.get("assigned_countries"))
            )
            if next_role != ROLE_MANAGER:
                next_assigned_countries = ""
            self._execute(
                conn,
                "UPDATE users SET status = ?, role = ?, assigned_countries = ?, approved_at = ?, approved_by = ? WHERE id = ?",
                (status, next_role, next_assigned_countries, approved_at, int(acting_admin_id), int(user_id)),
            )
            fresh = self._fetchone(conn, "SELECT * FROM users WHERE id = ?", (int(user_id),))
        if not fresh:
            raise HTTPException(status_code=500, detail="Failed to update user")
        return self._row_to_user(fresh)

    def approve_user(
        self,
        user_id: int,
        acting_admin_id: int,
        *,
        role: str = "user",
        assigned_countries: list[str] | None = None,
    ) -> UserPublic:
        user = self._change_status(
            user_id,
            status="approved",
            acting_admin_id=acting_admin_id,
            role=role,
            assigned_countries=assigned_countries,
        )
        self._send_approval_email(to_email=user.email, full_name=user.full_name)
        return user

    def update_user(
        self,
        user_id: int,
        acting_admin_id: int,
        payload: AdminUserUpdateRequest,
    ) -> UserPublic:
        actor_role = self._get_actor_role(int(acting_admin_id))
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM users WHERE id = ?", (int(user_id),))
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            if int(row["id"]) == int(acting_admin_id):
                raise HTTPException(status_code=400, detail="Admin cannot edit own account from the admin table")
            current_role = str(row.get("role") or ROLE_USER).strip().lower() or ROLE_USER
            role = str(payload.role or row.get("role") or ROLE_USER).strip().lower() or ROLE_USER
            if role not in ROLE_ORDER:
                raise HTTPException(status_code=400, detail="Invalid role")
            self._assert_can_manage_target_role(
                actor_role=actor_role,
                target_current_role=current_role,
                next_role=role,
            )
            assigned_countries = self._serialize_assigned_countries(payload.assigned_countries)
            if role != ROLE_MANAGER:
                assigned_countries = ""
            self._execute(
                conn,
                """
                UPDATE users
                SET full_name = ?, company_name = ?, country = ?, role = ?, assigned_countries = ?
                WHERE id = ?
                """,
                (
                    str(payload.full_name or "").strip(),
                    str(payload.company_name or "").strip(),
                    str(payload.country or "").strip(),
                    role,
                    assigned_countries,
                    int(user_id),
                ),
            )
            fresh = self._fetchone(conn, "SELECT * FROM users WHERE id = ?", (int(user_id),))
        if not fresh:
            raise HTTPException(status_code=500, detail="Failed to update user")
        return self._row_to_user(fresh)

    def reject_user(self, user_id: int, acting_admin_id: int) -> UserPublic:
        actor_role = self._get_actor_role(int(acting_admin_id))
        target = self._get_user_row_by_id(int(user_id))
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        self._assert_can_manage_target_role(
            actor_role=actor_role,
            target_current_role=str(target.get("role") or ROLE_USER).strip().lower() or ROLE_USER,
            next_role=str(target.get("role") or ROLE_USER).strip().lower() or ROLE_USER,
        )
        return self._change_status(user_id, status="rejected", acting_admin_id=acting_admin_id)

    def delete_user(self, user_id: int, acting_admin_id: int) -> dict[str, Any]:
        actor_role = self._get_actor_role(int(acting_admin_id))
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM users WHERE id = ?", (int(user_id),))
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            if int(row["id"]) == int(acting_admin_id):
                raise HTTPException(status_code=400, detail="Admin cannot delete own account")
            self._assert_can_manage_target_role(
                actor_role=actor_role,
                target_current_role=str(row.get("role") or ROLE_USER).strip().lower() or ROLE_USER,
                next_role=str(row.get("role") or ROLE_USER).strip().lower() or ROLE_USER,
            )
            if str(row.get("status") or "").strip().lower() != "rejected":
                raise HTTPException(status_code=400, detail="Only blocked/rejected users can be deleted")
            self._execute(conn, "DELETE FROM saved_quotes WHERE user_id = ?", (int(user_id),))
            self._execute(conn, "DELETE FROM refresh_sessions WHERE user_id = ?", (int(user_id),))
            self._execute(conn, "DELETE FROM password_reset_tokens WHERE user_id = ?", (int(user_id),))
            self._execute(conn, "DELETE FROM users WHERE id = ?", (int(user_id),))
        return {"success": True, "deleted_user_id": int(user_id)}

    def _normalize_saved_quote_items(self, items: list[Any]) -> list[SavedQuoteItem]:
        normalized: list[SavedQuoteItem] = []
        for idx, raw in enumerate(items or []):
            try:
                item = SavedQuoteItem.model_validate(raw)
            except Exception:
                continue
            data = item.model_dump()
            data["qty"] = max(1, int(data.get("qty") or 1))
            data["sort_order"] = int(data.get("sort_order") or idx)
            data["compare_sheet"] = data.get("compare_sheet") if isinstance(data.get("compare_sheet"), dict) else {}
            if not str(data.get("product_code") or "").strip():
                continue
            normalized.append(SavedQuoteItem.model_validate(data))
        return normalized

    def _row_to_saved_quote_summary(self, row: dict[str, Any]) -> SavedQuoteSummary:
        item_count = 0
        try:
            item_count = len(json.loads(str(row.get("items_json") or "[]")))
        except Exception:
            item_count = 0
        return SavedQuoteSummary(
            id=int(row["id"]),
            company=str(row.get("company") or ""),
            project=str(row.get("project") or ""),
            project_status=str(row.get("project_status") or "design_phase"),
            contractor_name=str(row.get("contractor_name") or ""),
            consultant_name=str(row.get("consultant_name") or ""),
            project_notes=str(row.get("project_notes") or ""),
            item_count=item_count,
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row.get("updated_at") or ""),
        )

    def _row_to_saved_quote_detail(self, row: dict[str, Any]) -> SavedQuoteDetail:
        try:
            raw_items = json.loads(str(row.get("items_json") or "[]"))
        except Exception:
            raw_items = []
        items = self._normalize_saved_quote_items(raw_items)
        summary = self._row_to_saved_quote_summary(row)
        return SavedQuoteDetail(**summary.model_dump(), items=items)

    def list_saved_quotes(self, user_id: int) -> list[SavedQuoteSummary]:
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT *
                FROM saved_quotes
                WHERE user_id = ?
                ORDER BY LOWER(project) ASC, updated_at DESC, id DESC
                """,
                (int(user_id),),
            )
        return [self._row_to_saved_quote_summary(row) for row in rows]

    def get_saved_quote(self, user_id: int, quote_id: int) -> SavedQuoteDetail:
        with self.connect() as conn:
            row = self._fetchone(
                conn,
                "SELECT * FROM saved_quotes WHERE id = ? AND user_id = ?",
                (int(quote_id), int(user_id)),
            )
        if not row:
            raise HTTPException(status_code=404, detail="Saved quote not found")
        return self._row_to_saved_quote_detail(row)

    def admin_list_saved_quotes(self, user_id: int) -> list[SavedQuoteSummary]:
        return self.list_saved_quotes(user_id)

    def admin_get_saved_quote(self, user_id: int, quote_id: int) -> SavedQuoteDetail:
        return self.get_saved_quote(user_id, quote_id)

    def manager_list_saved_quotes(self, manager: UserPublic, user_id: int) -> list[SavedQuoteSummary]:
        user = self._get_user_row_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user_public = self._row_to_user(user)
        if not self.can_view_user(manager, user_public):
            raise HTTPException(status_code=403, detail="Manager cannot access this user")
        return self.list_saved_quotes(user_id)

    def manager_get_saved_quote(self, manager: UserPublic, user_id: int, quote_id: int) -> SavedQuoteDetail:
        user = self._get_user_row_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user_public = self._row_to_user(user)
        if not self.can_view_user(manager, user_public):
            raise HTTPException(status_code=403, detail="Manager cannot access this user")
        return self.get_saved_quote(user_id, quote_id)

    def _row_to_visible_quote_summary(self, row: dict[str, Any]) -> VisibleQuoteSummary:
        item_count = 0
        try:
            item_count = len(json.loads(str(row.get("items_json") or "[]")))
        except Exception:
            item_count = 0
        customer_name = str(row.get("company") or "").strip() or str(row.get("company_name") or "").strip()
        quote_owner_name = str(row.get("full_name") or "").strip()
        quote_owner_email = str(row.get("email") or "").strip()
        return VisibleQuoteSummary(
            quote_id=int(row.get("id") or 0),
            user_id=int(row.get("user_id") or 0),
            project=str(row.get("project") or "").strip(),
            customer_name=customer_name,
            country=str(row.get("country") or "").strip(),
            contractor_name=str(row.get("contractor_name") or "").strip(),
            project_status=str(row.get("project_status") or "design_phase").strip(),
            consultant_name=str(row.get("consultant_name") or "").strip(),
            quote_owner_name=quote_owner_name,
            quote_owner_email=quote_owner_email,
            item_count=item_count,
            updated_at=str(row.get("updated_at") or "").strip(),
            created_at=str(row.get("created_at") or "").strip(),
        )

    def list_visible_quotes(self, viewer: UserPublic) -> list[VisibleQuoteSummary]:
        role = str(viewer.role or ROLE_USER).strip().lower() or ROLE_USER
        if role not in STAFF_ROLES:
            return []
        query = """
            SELECT sq.*, u.full_name, u.email, u.company_name, u.country
            FROM saved_quotes sq
            JOIN users u ON u.id = sq.user_id
        """
        params: tuple[Any, ...] = ()
        if role == ROLE_MANAGER:
            allowed = [str(item).strip() for item in (viewer.assigned_countries or []) if str(item).strip()]
            if not allowed:
                return []
            placeholders = ", ".join("?" for _ in allowed)
            query += f" WHERE LOWER(u.country) IN ({placeholders})"
            params = tuple(item.lower() for item in allowed)
        query += " ORDER BY sq.updated_at DESC, sq.created_at DESC, sq.id DESC"
        with self.connect() as conn:
            rows = self._fetchall(conn, query, params)
        return [self._row_to_visible_quote_summary(row) for row in rows]

    def save_quote(self, user_id: int, payload: SavedQuoteUpsertRequest, *, quote_id: int | None = None) -> SavedQuoteDetail:
        project = str(payload.project or "").strip()
        if not project:
            raise HTTPException(status_code=400, detail="Project is required")
        items = self._normalize_saved_quote_items(payload.items)
        if not items:
            raise HTTPException(status_code=400, detail="Quote must contain at least one item")
        company = str(payload.company or "").strip()
        project_status = str(payload.project_status or "design_phase").strip().lower() or "design_phase"
        contractor_name = str(payload.contractor_name or "").strip()
        consultant_name = str(payload.consultant_name or "").strip()
        project_notes = str(payload.project_notes or "").strip()
        now = _utc_iso()
        items_json = json.dumps([item.model_dump() for item in items], ensure_ascii=True)
        with self.connect() as conn:
            if quote_id is None:
                duplicate = self._fetchone(
                    conn,
                    "SELECT id FROM saved_quotes WHERE user_id = ? AND LOWER(project) = LOWER(?) LIMIT 1",
                    (int(user_id), project),
                )
                if duplicate:
                    raise HTTPException(status_code=409, detail="A saved quote with this project name already exists")
                self._execute(
                    conn,
                    """
                    INSERT INTO saved_quotes (user_id, company, project, project_status, contractor_name, consultant_name, project_notes, items_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (int(user_id), company, project, project_status, contractor_name, consultant_name, project_notes, items_json, now, now),
                )
                row = self._fetchone(
                    conn,
                    """
                    SELECT *
                    FROM saved_quotes
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (int(user_id),),
                )
            else:
                existing = self._fetchone(
                    conn,
                    "SELECT id FROM saved_quotes WHERE id = ? AND user_id = ?",
                    (int(quote_id), int(user_id)),
                )
                if not existing:
                    raise HTTPException(status_code=404, detail="Saved quote not found")
                duplicate = self._fetchone(
                    conn,
                    "SELECT id FROM saved_quotes WHERE user_id = ? AND LOWER(project) = LOWER(?) AND id <> ? LIMIT 1",
                    (int(user_id), project, int(quote_id)),
                )
                if duplicate:
                    raise HTTPException(status_code=409, detail="A saved quote with this project name already exists")
                self._execute(
                    conn,
                    """
                    UPDATE saved_quotes
                    SET company = ?, project = ?, project_status = ?, contractor_name = ?, consultant_name = ?, project_notes = ?, items_json = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (company, project, project_status, contractor_name, consultant_name, project_notes, items_json, now, int(quote_id), int(user_id)),
                )
                row = self._fetchone(
                    conn,
                    "SELECT * FROM saved_quotes WHERE id = ? AND user_id = ?",
                    (int(quote_id), int(user_id)),
                )
        if not row:
            raise HTTPException(status_code=500, detail="Failed to save quote")
        return self._row_to_saved_quote_detail(row)

    def delete_saved_quote(self, user_id: int, quote_id: int) -> None:
        with self.connect() as conn:
            existing = self._fetchone(
                conn,
                "SELECT id FROM saved_quotes WHERE id = ? AND user_id = ?",
                (int(quote_id), int(user_id)),
            )
            if not existing:
                raise HTTPException(status_code=404, detail="Saved quote not found")
            self._execute(
                conn,
                "DELETE FROM saved_quotes WHERE id = ? AND user_id = ?",
                (int(quote_id), int(user_id)),
            )


def build_auth_dependencies(auth_service: AuthService):
    bearer = HTTPBearer(auto_error=False)

    def get_token_from_request(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
        if credentials and credentials.credentials:
            return credentials.credentials
        cookie_token = str(request.cookies.get(auth_service.access_cookie_name) or "").strip()
        if cookie_token:
            return cookie_token
        auth = str(request.headers.get("authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return ""

    def get_current_user(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> UserPublic:
        token = get_token_from_request(request, credentials)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        return auth_service.decode_token(token)

    def require_admin(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if str(user.role or "").lower() != ROLE_ADMIN:
            raise HTTPException(status_code=403, detail="Admin privileges required")
        return user

    def require_leadership(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if str(user.role or "").lower() not in LEADERSHIP_ROLES:
            raise HTTPException(status_code=403, detail="Director or admin privileges required")
        return user

    def require_staff(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if str(user.role or "").lower() not in STAFF_ROLES:
            raise HTTPException(status_code=403, detail="Admin, director, or manager privileges required")
        return user

    return get_current_user, require_admin, require_leadership, require_staff, get_token_from_request
