from __future__ import annotations

import ipaddress
import os
import socket
import sqlite3
import time
from threading import Lock
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest, urlopen

import psycopg2
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from psycopg2.extras import RealDictCursor

from app.runtime_config import cfg_bool, cfg_int, cfg_list


PUBLIC_FETCH_HOSTS = {
    "www.disano.it",
    "disano.it",
    "fosnova.it",
    "www.fosnova.it",
    "azprodmedia.blob.core.windows.net",
}


def env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    return raw.lower() not in {"0", "false", "no", "off"}


def cors_allowed_origins() -> list[str]:
    raw = str(os.getenv("CORS_ALLOWED_ORIGINS", "")).strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return cfg_list(
        "main.cors_allowed_origins",
        [
            "http://localhost",
            "http://localhost:3000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
        ],
    )


def setup_cors(app) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
    )


def looks_like_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-")


def looks_like_supported_image(data: bytes) -> bool:
    return (
        data.startswith(b"\xff\xd8\xff")
        or data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"RIFF") and b"WEBP" in data[:16]
    )


def is_public_hostname(hostname: str) -> bool:
    host = str(hostname or "").strip().rstrip(".").lower()
    if not host or host == "localhost":
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return False
        found_public = False
        for info in infos:
            try:
                ip = ipaddress.ip_address(info[4][0])
            except Exception:
                return False
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
            found_public = True
        return found_public


def hostname_allowed(hostname: str, allowed_hosts: Optional[set[str]] = None) -> bool:
    host = str(hostname or "").strip().rstrip(".").lower()
    if not host or not is_public_hostname(host):
        return False
    if not allowed_hosts:
        return True
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)


def safe_open_url(
    url: str,
    *,
    timeout: int,
    allowed_hosts: Optional[set[str]] = None,
    headers: Optional[dict[str, str]] = None,
):
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Unsupported URL scheme")
    if not hostname_allowed(parsed.hostname or "", allowed_hosts=allowed_hosts):
        raise ValueError("Blocked outbound host")
    req = UrlRequest(parsed.geturl(), headers=headers or {"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=timeout)


class SecurityManager:
    def __init__(self) -> None:
        self.enable_debug_endpoints = env_bool("ENABLE_DEBUG_ENDPOINTS", cfg_bool("main.enable_debug_endpoints", False))
        self.admin_token = str(os.getenv("ADMIN_TOKEN", "")).strip()
        self.rate_limit_store_backend = str(os.getenv("RATE_LIMIT_STORE", "")).strip().lower()
        self.rate_limit_database_url = (
            str(os.getenv("RATE_LIMIT_DATABASE_URL", "")).strip()
            or str(os.getenv("AUTH_DATABASE_URL", "")).strip()
        )
        self.rate_limit_db_path = str(os.getenv("AUTH_DB_PATH", "data/auth.db")).strip()
        self._rate_limit_state: dict[str, list[float]] = {}
        self._rate_limit_lock = Lock()
        self._rate_limit_schema_ready = False
        self._rate_limit_schema_lock = Lock()

    def _rate_limit_shared_enabled(self) -> bool:
        if self.rate_limit_store_backend == "memory":
            return False
        if self.rate_limit_store_backend in {"shared", "database", "db"}:
            return True
        return bool(self.rate_limit_database_url or self.rate_limit_db_path)

    def _db_backend(self) -> str:
        if self.rate_limit_database_url.startswith(("postgres://", "postgresql://")):
            return "postgres"
        return "sqlite"

    def _translate_query(self, query: str) -> str:
        if self._db_backend() != "postgres":
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

    def _connect_rate_limit_db(self):
        if self._db_backend() == "postgres":
            return psycopg2.connect(self.rate_limit_database_url)
        db_dir = os.path.dirname(self.rate_limit_db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.rate_limit_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_rate_limit_schema(self) -> None:
        if not self._rate_limit_shared_enabled() or self._rate_limit_schema_ready:
            return
        with self._rate_limit_schema_lock:
            if self._rate_limit_schema_ready:
                return
            conn = self._connect_rate_limit_db()
            try:
                if self._db_backend() == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            CREATE TABLE IF NOT EXISTS rate_limit_hits (
                                bucket_key TEXT PRIMARY KEY,
                                window_start BIGINT NOT NULL,
                                hits INTEGER NOT NULL,
                                updated_at TEXT NOT NULL
                            )
                            """
                        )
                    conn.commit()
                else:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS rate_limit_hits (
                            bucket_key TEXT PRIMARY KEY,
                            window_start INTEGER NOT NULL,
                            hits INTEGER NOT NULL,
                            updated_at TEXT NOT NULL
                        )
                        """
                    )
                    conn.commit()
                self._rate_limit_schema_ready = True
            finally:
                conn.close()

    def _rate_limit_hit(self, key: str, limit: int, window_sec: int) -> bool:
        if self._rate_limit_shared_enabled():
            try:
                return self._rate_limit_hit_shared(key, limit=limit, window_sec=window_sec)
            except Exception:
                pass
        now = time.time()
        with self._rate_limit_lock:
            hits = [ts for ts in self._rate_limit_state.get(key, []) if now - ts < window_sec]
            if len(hits) >= limit:
                self._rate_limit_state[key] = hits
                return True
            hits.append(now)
            self._rate_limit_state[key] = hits
            if len(self._rate_limit_state) > 5000:
                stale_before = now - max(window_sec, 60)
                for old_key in list(self._rate_limit_state.keys())[:1000]:
                    self._rate_limit_state[old_key] = [ts for ts in self._rate_limit_state[old_key] if ts >= stale_before]
                    if not self._rate_limit_state[old_key]:
                        self._rate_limit_state.pop(old_key, None)
            return False

    def _rate_limit_hit_shared(self, key: str, limit: int, window_sec: int) -> bool:
        self._ensure_rate_limit_schema()
        now = int(time.time())
        window_start = now - (now % max(1, int(window_sec)))
        updated_at = str(now)
        conn = self._connect_rate_limit_db()
        try:
            if self._db_backend() == "postgres":
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        INSERT INTO rate_limit_hits (bucket_key, window_start, hits, updated_at)
                        VALUES (%s, %s, 1, %s)
                        ON CONFLICT (bucket_key) DO UPDATE
                        SET
                            window_start = CASE
                                WHEN rate_limit_hits.window_start = EXCLUDED.window_start THEN rate_limit_hits.window_start
                                ELSE EXCLUDED.window_start
                            END,
                            hits = CASE
                                WHEN rate_limit_hits.window_start = EXCLUDED.window_start THEN rate_limit_hits.hits + 1
                                ELSE 1
                            END,
                            updated_at = EXCLUDED.updated_at
                        RETURNING hits
                        """,
                        (key, window_start, updated_at),
                    )
                    row = cur.fetchone()
                    cur.execute("DELETE FROM rate_limit_hits WHERE updated_at < %s", (str(now - (window_sec * 4)),))
                conn.commit()
                hits = int((row or {}).get("hits") or 0)
                return hits > int(limit)

            cur = conn.execute(
                "SELECT bucket_key, window_start, hits FROM rate_limit_hits WHERE bucket_key = ?",
                (key,),
            )
            row = cur.fetchone()
            if row and int(row["window_start"]) == window_start:
                hits = int(row["hits"]) + 1
                conn.execute(
                    "UPDATE rate_limit_hits SET hits = ?, updated_at = ? WHERE bucket_key = ?",
                    (hits, updated_at, key),
                )
            else:
                hits = 1
                conn.execute(
                    """
                    INSERT INTO rate_limit_hits (bucket_key, window_start, hits, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(bucket_key) DO UPDATE SET
                        window_start = excluded.window_start,
                        hits = excluded.hits,
                        updated_at = excluded.updated_at
                    """,
                    (key, window_start, hits, updated_at),
                )
            conn.execute("DELETE FROM rate_limit_hits WHERE updated_at < ?", (str(now - (window_sec * 4)),))
            conn.commit()
            return hits > int(limit)
        finally:
            conn.close()

    def _is_local_client(self, host: str) -> bool:
        if not host:
            return False
        if host in {"127.0.0.1", "::1", "localhost", "testclient"}:
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def require_admin_access(self, request: Request) -> None:
        if not self.enable_debug_endpoints:
            raise HTTPException(status_code=404, detail="Not found")
        client_host = str(getattr(getattr(request, "client", None), "host", "") or "")
        provided = str(request.headers.get("x-admin-token") or "").strip()
        auth = str(request.headers.get("authorization") or "").strip()
        bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        token = provided or bearer
        if self.admin_token:
            if token != self.admin_token:
                raise HTTPException(status_code=403, detail="Admin token required")
            return
        if not self._is_local_client(client_host):
            raise HTTPException(status_code=403, detail="Debug/admin endpoints are local-only")

    def enforce_rate_limit(self, request: Request, bucket: str, limit: int, window_sec: int) -> None:
        client_host = str(getattr(getattr(request, "client", None), "host", "") or "unknown")
        key = f"{bucket}:{client_host}"
        if self._rate_limit_hit(key, limit=limit, window_sec=window_sec):
            raise HTTPException(status_code=429, detail="Too many requests")

    def preview_limit(self) -> tuple[int, int]:
        return cfg_int("main.preview_rate_limit", 60), cfg_int("main.preview_rate_window_sec", 60)

    def debug_pdf_limit(self) -> tuple[int, int]:
        return cfg_int("main.debug_pdf_rate_limit", 10), cfg_int("main.debug_pdf_rate_window_sec", 60)

    def debug_image_limit(self) -> tuple[int, int]:
        return cfg_int("main.debug_image_rate_limit", 20), cfg_int("main.debug_image_rate_window_sec", 60)

    def public_search_limit(self) -> tuple[int, int]:
        return cfg_int("main.public_search_rate_limit", 30), cfg_int("main.public_search_rate_window_sec", 60)

    def public_facets_limit(self) -> tuple[int, int]:
        return cfg_int("main.public_facets_rate_limit", 60), cfg_int("main.public_facets_rate_window_sec", 60)
