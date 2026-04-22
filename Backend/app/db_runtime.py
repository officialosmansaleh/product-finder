from __future__ import annotations

import os
from dataclasses import dataclass


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
    product_database_url = str(os.getenv("PRODUCT_DATABASE_URL", "")).strip()
    product_db_backend = str(os.getenv("PRODUCT_DB_BACKEND", "")).strip().lower()
    if not product_db_backend:
        product_db_backend = "postgres" if product_database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
    return DatabaseRuntimeSettings(
        product_db_backend=product_db_backend,
        product_db_path=str(os.getenv("PRODUCT_DB_PATH", "data/products.db")).strip() or "data/products.db",
        product_database_url=product_database_url,
        auth_db_path=str(os.getenv("AUTH_DB_PATH", "data/auth.db")).strip() or "data/auth.db",
        auth_database_url=str(os.getenv("AUTH_DATABASE_URL", "")).strip(),
    )
