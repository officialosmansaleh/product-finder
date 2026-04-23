import hashlib
import json
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from app.db_runtime import normalize_postgres_url
from app.runtime_config import cfg_float, cfg_list


class CompatRow(dict):
    def __init__(self, data: Dict[str, Any], order: List[str]):
        super().__init__(data)
        self._order = order

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(self._order[key])
        return super().__getitem__(key)


class CompatCursor:
    def __init__(self, rows: List[CompatRow]):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class PostgresCompatConnection:
    def __init__(self, raw_conn):
        self.raw_conn = raw_conn

    def _translate(self, query: str) -> str:
        out: List[str] = []
        i = 0
        in_single = False
        while i < len(query):
            ch = query[i]
            if ch == "'" and (i == 0 or query[i - 1] != "\\"):
                in_single = not in_single
                out.append(ch)
            elif ch == "?" and not in_single:
                out.append("%s")
            else:
                out.append(ch)
            i += 1
        return "".join(out)

    def _pragma_table_info(self, table_name: str) -> CompatCursor:
        q = """
            SELECT
                ordinal_position - 1 AS cid,
                column_name,
                data_type,
                CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END AS notnull,
                column_default AS dflt_value,
                0 AS pk
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            ORDER BY ordinal_position
        """
        with self.raw_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(q, (table_name,))
            rows = [CompatRow(dict(r), ["cid", "column_name", "data_type", "notnull", "dflt_value", "pk"]) for r in cur.fetchall()]
        return CompatCursor(rows)

    def execute(self, query: str, params: Any = None):
        stripped = str(query or "").strip()
        pragma = re.match(r'^PRAGMA\s+table_info\((?:"?)([A-Za-z0-9_]+)(?:"?)\)\s*$', stripped, flags=re.IGNORECASE)
        if pragma:
            return self._pragma_table_info(pragma.group(1))

        with self.raw_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(self._translate(query), params or ())
            rows = []
            if cur.description:
                order = [d.name for d in cur.description]
                rows = [CompatRow(dict(r), order) for r in cur.fetchall()]
        return CompatCursor(rows)

    def commit(self):
        self.raw_conn.commit()

    def close(self):
        self.raw_conn.close()


class ProductDatabase:
    """Product database backed by SQLite or PostgreSQL."""

    def __init__(self, db_path: str = "data/products.db", database_url: str = "", backend: str = ""):
        self.db_path = db_path
        self.database_url = normalize_postgres_url(str(database_url or "").strip())
        requested_backend = str(backend or "").strip().lower()
        if requested_backend in {"postgres", "sqlite"}:
            self.backend = requested_backend
        else:
            self.backend = "postgres" if self.database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
        self.conn: Optional[Any] = None
        self.last_release_diff: Dict[str, Any] = {}

    def connect(self):
        if self.backend == "postgres":
            if not self.database_url:
                raise ValueError("PostgreSQL database URL is missing or unresolved")
            raw = psycopg2.connect(self.database_url)
            raw.autocommit = False
            self.conn = PostgresCompatConnection(raw)
            self._ensure_release_tables()
            return
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_release_tables()

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            finally:
                self.conn = None

    def _placeholder(self) -> str:
        return "%s" if self.backend == "postgres" else "?"

    def _utc_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure_release_tables(self) -> None:
        if not self.conn:
            return
        if self.backend == "postgres":
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS product_releases (
                    id BIGSERIAL PRIMARY KEY,
                    source_path TEXT NOT NULL DEFAULT '',
                    source_filename TEXT NOT NULL DEFAULT '',
                    imported_at TEXT NOT NULL,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    fingerprint TEXT NOT NULL DEFAULT '',
                    previous_release_id BIGINT,
                    added_count INTEGER NOT NULL DEFAULT 0,
                    changed_count INTEGER NOT NULL DEFAULT 0,
                    removed_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS product_release_items (
                    id BIGSERIAL PRIMARY KEY,
                    release_id BIGINT NOT NULL,
                    product_code TEXT NOT NULL,
                    row_json TEXT NOT NULL DEFAULT '{}',
                    row_hash TEXT NOT NULL DEFAULT ''
                )
                """
            )
        else:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS product_releases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL DEFAULT '',
                    source_filename TEXT NOT NULL DEFAULT '',
                    imported_at TEXT NOT NULL,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    fingerprint TEXT NOT NULL DEFAULT '',
                    previous_release_id INTEGER,
                    added_count INTEGER NOT NULL DEFAULT 0,
                    changed_count INTEGER NOT NULL DEFAULT 0,
                    removed_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS product_release_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    release_id INTEGER NOT NULL,
                    product_code TEXT NOT NULL,
                    row_json TEXT NOT NULL DEFAULT '{}',
                    row_hash TEXT NOT NULL DEFAULT ''
                )
                """
            )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_product_releases_imported_at ON product_releases(imported_at)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_product_release_items_release_id ON product_release_items(release_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_product_release_items_code ON product_release_items(release_id, product_code)")
        self.conn.commit()

    def _latest_release_row(self) -> Optional[Dict[str, Any]]:
        if not self.conn:
            self.connect()
        cur = self.conn.execute(
            "SELECT * FROM product_releases ORDER BY imported_at DESC, id DESC LIMIT 1"
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def _release_items_map(self, release_id: int) -> Dict[str, Dict[str, Any]]:
        if not self.conn:
            self.connect()
        ph = self._placeholder()
        cur = self.conn.execute(
            f"SELECT product_code, row_json FROM product_release_items WHERE release_id = {ph}",
            (int(release_id),),
        )
        out: Dict[str, Dict[str, Any]] = {}
        for row in cur.fetchall():
            code = str(row["product_code"] or "").strip()
            if not code:
                continue
            try:
                payload = json.loads(str(row["row_json"] or "{}"))
            except Exception:
                payload = {}
            out[code] = payload if isinstance(payload, dict) else {}
        return out

    def _normalize_release_row(self, row: Dict[str, Any]) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        for key, value in (row or {}).items():
            clean_key = str(key or "").strip()
            if not clean_key:
                continue
            if value is None:
                normalized[clean_key] = ""
            else:
                normalized[clean_key] = str(value).strip()
        return normalized

    def _row_hash(self, payload: Dict[str, Any]) -> str:
        text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _fingerprint_release_rows(self, rows: Dict[str, Dict[str, Any]]) -> str:
        joined = "||".join(
            f"{code}:{self._row_hash(payload)}"
            for code, payload in sorted(rows.items(), key=lambda item: item[0])
        )
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def _compute_release_diff(
        self,
        previous_rows: Dict[str, Dict[str, Any]],
        current_rows: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        all_codes = sorted(set(previous_rows) | set(current_rows))
        for code in all_codes:
            before = previous_rows.get(code)
            after = current_rows.get(code)
            if before is None and after is not None:
                entries.append(
                    {
                        "product_code": code,
                        "change_type": "added",
                        "changed_fields": sorted([k for k, v in after.items() if str(v or "").strip()]),
                        "previous": {},
                        "current": after,
                    }
                )
                continue
            if after is None and before is not None:
                entries.append(
                    {
                        "product_code": code,
                        "change_type": "removed",
                        "changed_fields": sorted([k for k, v in before.items() if str(v or "").strip()]),
                        "previous": before,
                        "current": {},
                    }
                )
                continue
            if before is None or after is None:
                continue
            changed_fields = sorted(
                key for key in (set(before) | set(after))
                if str(before.get(key) or "") != str(after.get(key) or "")
            )
            if changed_fields:
                entries.append(
                    {
                        "product_code": code,
                        "change_type": "changed",
                        "changed_fields": changed_fields,
                        "previous": before,
                        "current": after,
                    }
                )
        return entries

    def _record_release_snapshot(self, xlsx_path: str, current_rows: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        if not self.conn:
            self.connect()
        latest = self._latest_release_row()
        fingerprint = self._fingerprint_release_rows(current_rows)
        previous_id = int(latest["id"]) if latest and latest.get("id") is not None else None
        previous_rows = self._release_items_map(previous_id) if previous_id else {}
        diff_entries = self._compute_release_diff(previous_rows, current_rows)
        if latest and str(latest.get("fingerprint") or "") == fingerprint:
            return {
                "release_id": int(latest["id"]),
                "previous_release_id": int(latest["previous_release_id"]) if latest.get("previous_release_id") is not None else previous_id,
                "row_count": int(latest.get("row_count") or len(current_rows)),
                "added_count": int(latest.get("added_count") or 0),
                "changed_count": int(latest.get("changed_count") or 0),
                "removed_count": int(latest.get("removed_count") or 0),
                "has_changes": False,
                "unchanged_against_previous": True,
                "imported_at": str(latest.get("imported_at") or ""),
                "source_filename": str(latest.get("source_filename") or ""),
            }
        imported_at = self._utc_iso()
        ph = self._placeholder()
        self.conn.execute(
            f"""
            INSERT INTO product_releases (
                source_path, source_filename, imported_at, row_count, fingerprint, previous_release_id,
                added_count, changed_count, removed_count
            )
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (
                str(xlsx_path or ""),
                os.path.basename(str(xlsx_path or "")),
                imported_at,
                len(current_rows),
                fingerprint,
                previous_id,
                sum(1 for item in diff_entries if item["change_type"] == "added"),
                sum(1 for item in diff_entries if item["change_type"] == "changed"),
                sum(1 for item in diff_entries if item["change_type"] == "removed"),
            ),
        )
        release_row = self._latest_release_row()
        release_id = int(release_row["id"]) if release_row else 0
        for code, payload in sorted(current_rows.items(), key=lambda item: item[0]):
            self.conn.execute(
                f"""
                INSERT INTO product_release_items (release_id, product_code, row_json, row_hash)
                VALUES ({ph}, {ph}, {ph}, {ph})
                """,
                (
                    release_id,
                    code,
                    json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
                    self._row_hash(payload),
                ),
            )
        self.conn.commit()
        return {
            "release_id": release_id,
            "previous_release_id": previous_id,
            "row_count": len(current_rows),
            "added_count": sum(1 for item in diff_entries if item["change_type"] == "added"),
            "changed_count": sum(1 for item in diff_entries if item["change_type"] == "changed"),
            "removed_count": sum(1 for item in diff_entries if item["change_type"] == "removed"),
            "has_changes": bool(diff_entries),
            "unchanged_against_previous": False,
            "imported_at": imported_at,
            "source_filename": os.path.basename(str(xlsx_path or "")),
        }

    def get_latest_release_diff(self) -> Dict[str, Any]:
        if not self.conn:
            self.connect()
        latest = self._latest_release_row()
        if not latest:
            return {"has_release": False, "items": [], "summary": {}}
        latest_id = int(latest["id"])
        previous_id = int(latest["previous_release_id"]) if latest.get("previous_release_id") is not None else None
        current_rows = self._release_items_map(latest_id)
        previous_rows = self._release_items_map(previous_id) if previous_id else {}
        diff_entries = self._compute_release_diff(previous_rows, current_rows)
        summary = {
            "release_id": latest_id,
            "previous_release_id": previous_id,
            "imported_at": str(latest.get("imported_at") or ""),
            "source_filename": str(latest.get("source_filename") or ""),
            "row_count": int(latest.get("row_count") or len(current_rows)),
            "added_count": int(latest.get("added_count") or 0),
            "changed_count": int(latest.get("changed_count") or 0),
            "removed_count": int(latest.get("removed_count") or 0),
            "total_modified_products": len(diff_entries),
            "has_previous_release": previous_id is not None,
        }
        items: List[Dict[str, Any]] = []
        for entry in diff_entries:
            before = entry["previous"] or {}
            after = entry["current"] or {}
            items.append(
                {
                    "product_code": entry["product_code"],
                    "change_type": entry["change_type"],
                    "product_name_previous": str(before.get("product_name") or ""),
                    "product_name_current": str(after.get("product_name") or ""),
                    "changed_fields": entry["changed_fields"],
                }
            )
        return {"has_release": True, "summary": summary, "items": items}

    def export_latest_release_diff_csv(self) -> str:
        if not self.conn:
            self.connect()
        latest = self._latest_release_row()
        if not latest:
            return "product_code,change_type,field_name,previous_value,current_value\r\n"
        latest_id = int(latest["id"])
        previous_id = int(latest["previous_release_id"]) if latest.get("previous_release_id") is not None else None
        current_rows = self._release_items_map(latest_id)
        previous_rows = self._release_items_map(previous_id) if previous_id else {}
        diff_entries = self._compute_release_diff(previous_rows, current_rows)

        def csv_escape(value: Any) -> str:
            text = str(value or "")
            if any(ch in text for ch in ['"', ",", "\n", "\r"]):
                return '"' + text.replace('"', '""') + '"'
            return text

        lines = [[
            "product_code",
            "change_type",
            "field_name",
            "previous_value",
            "current_value",
        ]]
        for entry in diff_entries:
            before = entry["previous"] or {}
            after = entry["current"] or {}
            for field in entry["changed_fields"]:
                lines.append([
                    entry["product_code"],
                    entry["change_type"],
                    field,
                    before.get(field, ""),
                    after.get(field, ""),
                ])
        return "\r\n".join(",".join(csv_escape(cell) for cell in row) for row in lines)

    def _table_exists(self, table_name: str = "products") -> bool:
        if not self.conn:
            self.connect()
        if self.backend == "postgres":
            cur = self.conn.execute(
                """
                SELECT 1 AS ok
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name = %s
                LIMIT 1
                """,
                (table_name,),
            )
            return bool(cur.fetchone())
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        )
        return bool(cur.fetchone())

    def _table_columns(self, table_name: str = "products") -> List[str]:
        cursor = self.conn.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]

    def _create_table_from_columns(self, columns: List[str]):
        if self.backend == "postgres":
            cols_sql = ['id BIGSERIAL PRIMARY KEY']
            cols_sql += [f'"{c}" TEXT' for c in columns]
            cols_sql += ['imported_at TEXT']
        else:
            cols_sql = ['id INTEGER PRIMARY KEY AUTOINCREMENT']
            cols_sql += [f'"{c}" TEXT' for c in columns]
            cols_sql += ['imported_at TEXT']
        sql_stmt = f'CREATE TABLE IF NOT EXISTS products ({", ".join(cols_sql)})'
        self.conn.execute(sql_stmt)

    def _add_missing_columns(self, columns: List[str]):
        existing = set(self._table_columns("products"))
        for c in columns:
            if c not in existing:
                self.conn.execute(f'ALTER TABLE products ADD COLUMN "{c}" TEXT')

    def get_stats(self) -> Dict[str, Any]:
        if not self.conn:
            self.connect()
        cur = self.conn.execute("SELECT COUNT(*) AS n FROM products")
        n = cur.fetchone()["n"]
        return {"total_products": int(n)}

    def debug_sample(self, n: int = 5) -> List[Dict[str, Any]]:
        if not self.conn:
            self.connect()
        ph = self._placeholder()
        cur = self.conn.execute(f"SELECT * FROM products LIMIT {ph}", (int(n),))
        rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d.pop("id", None)
            d.pop("imported_at", None)
            out.append(d)
        return out

    def recreate_database(self, xlsx_path: str, family_map_path: str = None, df: Optional[pd.DataFrame] = None):
        print("Recreating database from scratch...")
        if not self.conn:
            self.connect()
        self.conn.execute("DROP TABLE IF EXISTS products")
        self.conn.commit()
        return self.init_db(xlsx_path, family_map_path, df=df)

    def update_prices_from_map(self, price_df: pd.DataFrame) -> Dict[str, int]:
        if not self.conn:
            self.connect()
        if price_df is None or price_df.empty:
            return {"matched": 0, "cleared": 0, "price_rows": 0}

        self._add_missing_columns(["price"])
        lookup = {
            str(row.get("compact_code") or "").strip().lower(): str(row.get("price") or "").strip()
            for _, row in price_df.iterrows()
            if str(row.get("compact_code") or "").strip() and str(row.get("price") or "").strip()
        }
        rows = self.conn.execute("SELECT product_code FROM products").fetchall()
        cleared = len(rows)
        matched = 0
        ph = self._placeholder()
        self.conn.execute("UPDATE products SET price = NULL")
        for row in rows:
            product_code = str(dict(row).get("product_code") or "").strip()
            compact_code = re.sub(r"[^0-9A-Za-z]", "", product_code).lower()
            price = lookup.get(compact_code)
            if price:
                self.conn.execute(f"UPDATE products SET price = {ph} WHERE product_code = {ph}", (price, product_code))
                matched += 1
        self.conn.commit()
        return {"matched": matched, "cleared": cleared, "price_rows": len(lookup)}

    def update_families_from_map(self, family_map: Dict[str, str]) -> Dict[str, int]:
        if not self.conn:
            self.connect()
        if not family_map:
            return {"matched": 0, "family_keys": 0}

        self._add_missing_columns(["product_family"])
        rows = self.conn.execute("SELECT product_code, short_product_code, product_name FROM products").fetchall()
        matched = 0
        ph = self._placeholder()
        for row in rows:
            data = dict(row)
            product_code = str(data.get("product_code") or "").strip()
            short_key = str(data.get("short_product_code") or "").strip().lower()
            name_key = str(data.get("product_name") or "").strip().split()[0].lower() if str(data.get("product_name") or "").strip() else ""
            family = family_map.get(short_key) or family_map.get(name_key)
            if family and product_code:
                self.conn.execute(f"UPDATE products SET product_family = {ph} WHERE product_code = {ph}", (str(family).strip(), product_code))
                matched += 1
        self.conn.commit()
        return {"matched": matched, "family_keys": len(family_map)}

    def init_db(self, xlsx_path: str, family_map_path: str = None, df: Optional[pd.DataFrame] = None):
        if df is None:
            print(f"Initializing {self.backend} database from {xlsx_path}...")
            from app.pim_loader import load_products

            try:
                df = load_products(xlsx_path, family_map_path=family_map_path, verbose=True)
            except Exception as e:
                print(f"Failed to load products: {e}")
                import traceback
                traceback.print_exc()
                return 0
        else:
            print(f"Initializing {self.backend} database from preloaded DataFrame for {xlsx_path}...")

        if df is None or df.empty:
            print("No products loaded")
            return 0

        print(f"DataFrame shape: {df.shape}")
        columns = list(df.columns)
        print(f"DataFrame columns: {columns}")
        if "product_family" not in columns:
            print("CRITICAL: 'product_family' still missing after loading!")
            return 0

        if not self.conn:
            self.connect()

        self.conn.execute("DROP TABLE IF EXISTS products")
        self.conn.commit()

        print(f"Creating table with columns: {columns}")
        self._create_table_from_columns(columns)
        self._add_missing_columns(columns)
        current_release_rows: Dict[str, Dict[str, Any]] = {}

        product_code_ph = self._placeholder()
        inserted = 0
        updated = 0
        errors = 0

        for idx, row_values in enumerate(df.itertuples(index=False, name=None)):
            try:
                row_data: Dict[str, Any] = {}
                for col, v in zip(columns, row_values):
                    row_data[col] = None if pd.isna(v) else str(v).strip()

                product_code = row_data.get("product_code", "")
                if not product_code:
                    continue
                current_release_rows[product_code] = self._normalize_release_row(row_data)

                cursor = self.conn.execute(
                    f"SELECT id FROM products WHERE product_code = {product_code_ph}",
                    (product_code,),
                )
                if cursor.fetchone():
                    update_parts = [f'"{col}" = {self._placeholder()}' for col in row_data.keys()]
                    values = list(row_data.values()) + [product_code]
                    self.conn.execute(
                        f'UPDATE products SET {", ".join(update_parts)} WHERE product_code = {product_code_ph}',
                        values,
                    )
                    updated += 1
                else:
                    cols = ", ".join([f'"{c}"' for c in row_data.keys()])
                    placeholders = ", ".join([self._placeholder()] * len(row_data))
                    self.conn.execute(
                        f'INSERT INTO products ({cols}) VALUES ({placeholders})',
                        list(row_data.values()),
                    )
                    inserted += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"Row {idx} insert/update failed: {e}")
                continue

        key_fields = ["ip_rating", "ik_rating", "cct_k", "power_max_w", "lumen_output", "efficacy_lm_w", "product_family"]
        for field in key_fields:
            if field in columns:
                try:
                    idx_name = f'idx_{field.replace("_", "")}'
                    self.conn.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON products("{field}")')
                except Exception as e:
                    print(f"Could not create index on {field}: {e}")

        self.conn.commit()
        self.last_release_diff = self._record_release_snapshot(xlsx_path, current_release_rows)
        print(f"DB ready. inserted={inserted} updated={updated} errors={errors}")
        return inserted + updated

    def search_products(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        if not self.conn:
            self.connect()

        table_columns = set(self._table_columns("products"))
        query_parts = ["SELECT * FROM products WHERE 1=1"]
        params: List[Any] = []
        ph = self._placeholder()
        dimension_keys = set(cfg_list("main.dimension_keys", ["diameter", "luminaire_height", "luminaire_width", "luminaire_length"]))
        dimension_tolerance = cfg_float("database.dimension_tolerance", 0.05)

        def numeric_expr(col: str) -> str:
            if self.backend == "postgres":
                return f"""CAST(NULLIF(REGEXP_REPLACE(COALESCE("{col}", ''), '[^0-9.\\-]+', '', 'g'), '') AS REAL)"""
            return f'CAST("{col}" AS REAL)'

        def build_numeric_fragment(col: str, expr: Any, default_op: str = ">="):
            v = str(expr).strip().replace(" ", "")
            m = re.match(r"^(>=|<=|>|<)(-?\d+(?:\.\d+)?)$", v)
            if m:
                op, num = m.group(1), float(m.group(2))
                return (f'{numeric_expr(col)} {op} {ph}', [num])
            if "-" in v and not v.startswith("-"):
                a, b = v.split("-", 1)
                try:
                    lo = float(a)
                    hi = float(b)
                    if lo > hi:
                        lo, hi = hi, lo
                    return (f'({numeric_expr(col)} >= {ph} AND {numeric_expr(col)} <= {ph})', [lo, hi])
                except Exception:
                    return (None, [])
            try:
                num = float(v)
                return (f'{numeric_expr(col)} {default_op} {ph}', [num])
            except Exception:
                return (None, [])

        def build_condition(key: str, value: Any):
            if value is None:
                return (None, [])

            def _parse_numeric_filter(v: str, default_op: str = ">="):
                txt = str(v).strip().replace(" ", "")
                m = re.match(r"^(>=|<=|>|<)(-?\d+(?:\.\d+)?)$", txt)
                if m:
                    return m.group(1), float(m.group(2))
                m = re.search(r"(-?\d+(?:\.\d+)?)", txt.replace(",", "."))
                if m:
                    return default_op, float(m.group(1))
                return None, None

            numeric_cols = {
                "ugr_value",
                "efficacy_value",
                "lumen_output_value",
                "power_max_value",
                "power_min_value",
                "lifetime_h_value",
                "led_rated_life_value",
                "warranty_y_value",
                "beam_angle_deg",
                "diameter",
                "luminaire_height",
                "luminaire_width",
                "luminaire_length",
                "ambient_temp_min_c",
                "ambient_temp_max_c",
            }
            if key == "housing_color":
                v = str(value).strip().lower()
                return ('LOWER("housing_color") LIKE ' + ph, [f"%{v}%"])

            if key in numeric_cols:
                default_num_op = "<=" if key in {"ugr_value", "ambient_temp_min_c", "ambient_temp_max_c"} else ">="
                op, num = _parse_numeric_filter(value, default_op=default_num_op)
                if op is None or num is None:
                    return (None, [])
                if key in dimension_keys:
                    tol = abs(float(num)) * dimension_tolerance
                    if op in {">=", ">"}:
                        return (f'{numeric_expr(key)} {op} {ph}', [float(num) - tol])
                    if op in {"<=", "<"}:
                        return (f'{numeric_expr(key)} {op} {ph}', [float(num) + tol])
                return (f'{numeric_expr(key)} {op} {ph}', [num])

            if key == "product_family":
                return ("LOWER(product_family) = " + ph, [str(value).strip().lower()])

            if key == "product_name_contains":
                v = str(value).strip().lower()
                return ('LOWER(product_name) LIKE ' + ph, [f"%{v}%"])

            if key in {"product_name_short", "name_prefix"}:
                v = str(value).strip().lower()
                return ('LOWER(SPLIT_PART(TRIM(product_name), \' \', 1)) = ' + ph, [v]) if self.backend == "postgres" else (
                    'LOWER(SUBSTR(TRIM(product_name), 1, INSTR(TRIM(product_name) || " ", " ") - 1)) = ' + ph,
                    [v],
                )

            if key in {"ip_rating", "ip_visible", "ip_non_visible"}:
                v = str(value).strip().upper().replace(" ", "").replace("IPX", "IP0")
                m = re.search(r"(>=|<=|>|<)?IP(\d{2})", v)
                if not m:
                    return (None, [])
                op = m.group(1) or ">="
                num = float(m.group(2))
                col = key
                frag = f'CAST(REPLACE(REPLACE(UPPER("{col}"), \'IPX\', \'IP0\'), \'IP\', \'\') AS REAL) {op} {ph}'
                return (frag, [num])

            if key == "ik_rating":
                v = str(value).strip().upper().replace(" ", "")
                m = re.search(r"(>=|<=|>|<)?IK(\d{1,2})", v)
                if not m:
                    return (None, [])
                op = m.group(1) or ">="
                num = float(m.group(2))
                return (f'CAST(REPLACE(UPPER("ik_rating"), \'IK\', \'\') AS REAL) {op} {ph}', [num])

            if key == "cct_k":
                m = re.search(r"(\d+)", str(value))
                if not m:
                    return (None, [])
                return (numeric_expr("cct_k") + " = " + ph, [int(m.group(1))])

            if key in {"ugr", "cri", "warranty_years", "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct"}:
                col_map = {
                    "warranty_years": "warranty_y_value" if "warranty_y_value" in table_columns else "warranty_years",
                    "lifetime_hours": "lifetime_h_value" if "lifetime_h_value" in table_columns else "lifetime_hours",
                    "led_rated_life_h": "led_rated_life_value" if "led_rated_life_value" in table_columns else "led_rated_life_h",
                    "ugr": "ugr_value" if "ugr_value" in table_columns else "ugr",
                    "cri": "cri",
                    "lumen_maintenance_pct": "lumen_maintenance_pct",
                }
                default_op = "<=" if key == "ugr" else ">="
                op, num = _parse_numeric_filter(value, default_op=default_op)
                if op is None or num is None:
                    return (None, [])
                return (f'{numeric_expr(col_map[key])} {op} {ph}', [num])

            if key == "control_protocol":
                return ('LOWER(control_protocol) LIKE ' + ph, [f"%{str(value).lower()}%"])

            if key in {"power_max_w", "power_min_w", "lumen_output", "efficacy_lm_w"}:
                numeric_companion = {
                    "power_max_w": "power_max_value",
                    "power_min_w": "power_min_value",
                    "lumen_output": "lumen_output_value",
                    "efficacy_lm_w": "efficacy_value",
                }
                col = numeric_companion.get(key, key)
                if col not in table_columns:
                    col = key
                return build_numeric_fragment(col, value, default_op=">=")

            return (f'LOWER("{key}") LIKE {ph}', [f"%{str(value).lower()}%"])

        alias_map = {
            "ik_value": "ik_rating",
            "ugr_value": "ugr",
            "warranty_y_value": "warranty_years",
            "lifetime_h_value": "lifetime_hours",
            "power_max_value": "power_max_w",
            "power_min_value": "power_min_w",
            "lumen_output_value": "lumen_output",
            "efficacy_value": "efficacy_lm_w",
        }
        virtual_keys = {"product_name_short", "name_prefix", "product_name_contains"}

        for key, value in (filters or {}).items():
            actual_key = key
            if actual_key not in table_columns and actual_key in alias_map and alias_map[actual_key] in table_columns:
                actual_key = alias_map[actual_key]
            if actual_key not in table_columns and actual_key not in virtual_keys:
                continue
            if value is None or (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and len(value) == 0):
                continue

            if isinstance(value, list):
                or_frags: List[str] = []
                or_params: List[Any] = []
                for v1 in value:
                    frag, p = build_condition(actual_key, v1)
                    if frag:
                        or_frags.append(f"({frag})")
                        or_params.extend(p)
                if or_frags:
                    query_parts.append("AND (" + " OR ".join(or_frags) + ")")
                    params.extend(or_params)
                continue

            frag, p = build_condition(actual_key, value)
            if frag:
                query_parts.append(f"AND ({frag})")
                params.extend(p)

        query_parts.append(f"ORDER BY product_code LIMIT {ph}")
        params.append(int(limit))
        query = " ".join(query_parts)

        try:
            cur = self.conn.execute(query, params)
            out: List[Dict[str, Any]] = []
            for row in cur.fetchall():
                d = dict(row)
                d.pop("id", None)
                d.pop("imported_at", None)
                out.append(d)
            return out
        except Exception as e:
            print(f"Search error: {e}")
            print(f"Query: {query}")
            print(f"Params: {params}")
            return []

    def get_distinct_families(self, limit: int = 500) -> List[str]:
        if not self.conn:
            self.connect()
        columns = self._table_columns("products")
        if "product_family" not in columns:
            print("Column 'product_family' not found in database!")
            return []
        ph = self._placeholder()
        cur = self.conn.execute(
            f"""
            SELECT DISTINCT product_family AS fam
            FROM products
            WHERE product_family IS NOT NULL
              AND TRIM(product_family) <> ''
            ORDER BY fam
            LIMIT {ph}
            """,
            (int(limit),),
        )
        out = []
        for r in cur.fetchall():
            if r["fam"]:
                out.append(str(r["fam"]))
        print(f"Found {len(out)} distinct families: {out[:10]}")
        return out
