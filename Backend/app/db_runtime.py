from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus


def _first_env(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def normalize_postgres_url(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("${{") or raw.endswith("}}"):
        return ""
    if raw.startswith(("postgres://", "postgresql://")):
        return raw

    host = raw if raw and " " not in raw and "=" not in raw else ""
    if not host:
        return ""

    user = _first_env("PGUSER", "POSTGRES_USER")
    password = _first_env("PGPASSWORD", "POSTGRES_PASSWORD")
    database = _first_env("PGDATABASE", "POSTGRES_DB", "POSTGRES_DATABASE")
    port = _first_env("PGPORT", "POSTGRES_PORT") or "5432"

    if not all([user, password, database]):
        return ""

    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(database)}?sslmode=disable"
    )


@dataclass(frozen=True)
class DatabaseRuntimeSettings:
    product_db_backend: str
    product_db_path: str
    product_database_url: str
    auth_db_path: str
    auth_database_url: str

    @property
    def product_postgres_requested(self) -> bool:
        return self.product_db_backend == "postgres" or self.product_database_url.startswith(("postgres://", "postgresql://"))

    @property
    def auth_postgres_requested(self) -> bool:
        return self.auth_database_url.startswith(("postgres://", "postgresql://"))


def load_database_runtime_settings() -> DatabaseRuntimeSettings:
    product_database_url = normalize_postgres_url(str(os.getenv("PRODUCT_DATABASE_URL", "")).strip())
    product_db_backend = str(os.getenv("PRODUCT_DB_BACKEND", "")).strip().lower()
    if not product_db_backend:
        product_db_backend = "postgres" if product_database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
    return DatabaseRuntimeSettings(
        product_db_backend=product_db_backend,
        product_db_path=str(os.getenv("PRODUCT_DB_PATH", "data/products.db")).strip() or "data/products.db",
        product_database_url=product_database_url,
        auth_db_path=str(os.getenv("AUTH_DB_PATH", "data/auth.db")).strip() or "data/auth.db",
        auth_database_url=normalize_postgres_url(str(os.getenv("AUTH_DATABASE_URL", "")).strip()),
    )
