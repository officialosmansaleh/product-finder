# app/database.py
import os
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd


class ProductDatabase:
    """SQLite database for products"""

    def __init__(self, db_path: str = "data/products.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            finally:
                self.conn = None

    # ------------------------------------------------------------
    # Schema helpers (kept compatible with your current init_db)
    # ------------------------------------------------------------
    def _create_table_from_columns(self, columns: List[str]):
        cols_sql = ['id INTEGER PRIMARY KEY AUTOINCREMENT']
        cols_sql += [f'"{c}" TEXT' for c in columns]
        cols_sql += ['imported_at TEXT']
        sql = f'CREATE TABLE IF NOT EXISTS products ({", ".join(cols_sql)})'
        self.conn.execute(sql)

    def _add_missing_columns(self, columns: List[str]):
        cursor = self.conn.execute("PRAGMA table_info(products)")
        existing = {row[1] for row in cursor.fetchall()}
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
        """Return N sample rows to verify DB content quickly."""
        if not self.conn:
            self.connect()

        cur = self.conn.execute("SELECT * FROM products LIMIT ?", (int(n),))
        rows = cur.fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d.pop("id", None)
            d.pop("imported_at", None)
            out.append(d)
        return out
    # In database.py, aggiungi:

    def recreate_database(self, xlsx_path: str, family_map_path: str = None):
        """Ricrea il database da zero per assicurarsi che tutte le colonne siano presenti"""
        print("🔄 Recreating database from scratch...")
        
        if self.conn:
            # Drop la tabella esistente
            self.conn.execute("DROP TABLE IF EXISTS products")
            self.conn.commit()
        
        # Ricrea con init_db
        return self.init_db(xlsx_path, family_map_path)
    # ------------------------------------------------------------
    # Init DB from Excel (uses pim_loader.load_products)
    # ------------------------------------------------------------
    # def init_db(self, xlsx_path: str, family_map_path: str = None):
    #     print(f"🔄 Initializing SQLite database from {xlsx_path}...")

    #     from app.pim_loader import load_products

    #     try:
    #         df = load_products(xlsx_path, verbose=True)
    #         if df is None or df.empty:
    #             print("❌ No products loaded")
    #             return 0
    #         print(f"📊 DataFrame shape: {df.shape}")
            
    #         # DEBUG: stampa le colonne del DataFrame
    #         print(f"📋 DataFrame columns: {list(df.columns)}")
            
    #         # Verifica se product_family è presente
    #         if 'product_family' not in df.columns:
    #             print("⚠️ WARNING: 'product_family' column not found in DataFrame!")
    #             # Potremmo crearla dai dati esistenti?
    #             # Ad esempio, usando etim_search_key o altre colonne
    #             if 'etim_search_key' in df.columns:
    #                 print("ℹ️ Using etim_search_key as fallback for product_family")
    #                 df['product_family'] = df['etim_search_key']
            
    #     except Exception as e:
    #         print(f"❌ Failed to load products: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         return 0

    #     if not self.conn:
    #         self.connect()

    #     columns = list(df.columns)
    #     print(f"📋 Creating table with columns: {columns}")


    #     inserted = 0
    #     updated = 0
    #     errors = 0

    #     for idx, row in df.iterrows():
    #         try:
    #             row_data: Dict[str, Any] = {}
    #             for col in columns:
    #                 v = row[col]
    #                 row_data[col] = None if pd.isna(v) else str(v).strip()

    #             product_code = row_data.get("product_code", "")
    #             if not product_code:
    #                 continue

    #             cursor = self.conn.execute("SELECT id FROM products WHERE product_code = ?", (product_code,))
    #             if cursor.fetchone():
    #                 update_parts = [f'"{col}" = ?' for col in row_data.keys()]
    #                 values = list(row_data.values()) + [product_code]
    #                 self.conn.execute(f'UPDATE products SET {", ".join(update_parts)} WHERE product_code = ?', values)
    #                 updated += 1
    #             else:
    #                 cols = ", ".join([f'"{c}"' for c in row_data.keys()])
    #                 placeholders = ", ".join(["?"] * len(row_data))
    #                 self.conn.execute(f'INSERT INTO products ({cols}) VALUES ({placeholders})', list(row_data.values()))
    #                 inserted += 1

    #         except Exception:
    #             errors += 1
    #             if errors <= 5:
    #                 print(f"❌ Row {idx} insert/update failed")
    #             continue

    #     # indexes
    #     key_fields = ["ip_rating", "ik_rating", "cct_k", "power_max_w", "lumen_output", "efficacy_lm_w", "product_family"]
    #     for field in key_fields:
    #         if field in columns:
    #             try:
    #                 idx_name = f'idx_{field.replace("_","")}'
    #                 self.conn.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON products("{field}")')
    #             except Exception:
    #                 pass

    #     self.conn.commit()
    #     print(f"✅ DB ready. inserted={inserted} updated={updated} errors={errors}")
    #     return inserted + updated

    def init_db(self, xlsx_path: str, family_map_path: str = None):
        print(f"🔄 Initializing SQLite database from {xlsx_path}...")

        from app.pim_loader import load_products

        try:
            df = load_products(xlsx_path, verbose=True)
            if df is None or df.empty:
                print("❌ No products loaded")
                return 0
            print(f"📊 DataFrame shape: {df.shape}")
            print(f"📋 DataFrame columns: {list(df.columns)}")
            
            # Verifica che product_family sia presente
            if 'product_family' not in df.columns:
                print("❌ CRITICAL: 'product_family' still missing after loading!")
                return 0
                
        except Exception as e:
            print(f"❌ Failed to load products: {e}")
            import traceback
            traceback.print_exc()
            return 0

        if not self.conn:
            self.connect()

        # Drop la tabella esistente per ricrearla pulita
        self.conn.execute("DROP TABLE IF EXISTS products")
        self.conn.commit()

        columns = list(df.columns)
        print(f"📋 Creating table with columns: {columns}")
        
        self._create_table_from_columns(columns)
        self._add_missing_columns(columns)

        inserted = 0
        updated = 0
        errors = 0

        for idx, row in df.iterrows():
            try:
                row_data: Dict[str, Any] = {}
                for col in columns:
                    v = row[col]
                    # Gestisci i valori NaN
                    if pd.isna(v):
                        row_data[col] = None
                    else:
                        row_data[col] = str(v).strip()

                product_code = row_data.get("product_code", "")
                if not product_code:
                    continue

                cursor = self.conn.execute("SELECT id FROM products WHERE product_code = ?", (product_code,))
                if cursor.fetchone():
                    update_parts = [f'"{col}" = ?' for col in row_data.keys()]
                    values = list(row_data.values()) + [product_code]
                    self.conn.execute(f'UPDATE products SET {", ".join(update_parts)} WHERE product_code = ?', values)
                    updated += 1
                else:
                    cols = ", ".join([f'"{c}"' for c in row_data.keys()])
                    placeholders = ", ".join(["?"] * len(row_data))
                    self.conn.execute(f'INSERT INTO products ({cols}) VALUES ({placeholders})', list(row_data.values()))
                    inserted += 1

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"❌ Row {idx} insert/update failed: {e}")
                    print(f"   Data: {dict(row_data)}")
                continue

        # indexes
        key_fields = ["ip_rating", "ik_rating", "cct_k", "power_max_w", "lumen_output", "efficacy_lm_w", "product_family"]
        for field in key_fields:
            if field in columns:
                try:
                    idx_name = f'idx_{field.replace("_", "")}'
                    self.conn.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON products("{field}")')
                except Exception as e:
                    print(f"⚠️ Could not create index on {field}: {e}")

        self.conn.commit()
        print(f"✅ DB ready. inserted={inserted} updated={updated} errors={errors}")
        return inserted + updated

    # ------------------------------------------------------------
    # Search
    # ------------------------------------------------------------
    def search_products(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        if not self.conn:
            self.connect()

        cursor = self.conn.execute("PRAGMA table_info(products)")
        table_columns = {row[1] for row in cursor.fetchall()}

        query_parts = ["SELECT * FROM products WHERE 1=1"]
        params: List[Any] = []

        def build_numeric_fragment(col: str, expr: Any, default_op: str = ">="):
            v = str(expr).strip().replace(" ", "")

            # >=40, <=40, >40, <40
            m = re.match(r"^(>=|<=|>|<)(\d+(?:\.\d+)?)$", v)
            if m:
                op, num = m.group(1), float(m.group(2))
                return (f'CAST("{col}" AS REAL) {op} ?', [num])

            # 30-40
            if "-" in v and not v.startswith("-"):
                a, b = v.split("-", 1)
                try:
                    lo = float(a); hi = float(b)
                    if lo > hi:
                        lo, hi = hi, lo
                    return (f'(CAST("{col}" AS REAL) >= ? AND CAST("{col}" AS REAL) <= ?)', [lo, hi])
                except Exception:
                    return (None, [])

            # exact number
            try:
                num = float(v)
                return (f'CAST("{col}" AS REAL) {default_op} ?', [num])
            except Exception:
                return (None, [])

        def build_condition(key: str, value: Any):
            if value is None:
                return (None, [])


            # Generic numeric compare helper (if you already have one, usa il tuo)
            def _parse_numeric_filter(v: str, default_op: str = ">="):
                v = str(v).strip().replace(" ", "")
                m = re.match(r"^(>=|<=|>|<)(-?\d+(?:\.\d+)?)$", v)
                if m:
                    return m.group(1), float(m.group(2))
                m = re.search(r"(-?\d+(?:\.\d+)?)", v.replace(",", "."))
                if m:
                    return default_op, float(m.group(1))
                return None, None
            

            # ---- Numeric SQLite columns ----
            NUMERIC_COLS = {
                "ugr_value",
                "efficacy_value",
                "lumen_output_value",
                "power_max_value",
                "power_min_value",
                "lifetime_h_value",
                "led_rated_life_value",
                "warranty_y_value",
                    # ✅ NEW numeric dimensions/optics (stored as TEXT but compared as numbers)
                "beam_angle_deg",
                "diameter",
                "luminaire_height",
                "luminaire_width",
                "luminaire_length",
                "luminaire_size_min",
                "luminaire_size_max",
            }
            if key == "housing_color":
                v = str(value).strip().lower()
                return ('LOWER("housing_color") LIKE ?', [f"%{v}%"])

            
            if key in NUMERIC_COLS:
                op, num = _parse_numeric_filter(value, default_op="<=" if key == "ugr_value" else ">=")
                if op is None or num is None:
                    return (None, [])
                return (f'CAST("{key}" AS REAL) {op} ?', [num])
            # product_family exact (lower)
            if key == "product_family":
                v = str(value).strip().lower()
                return ("LOWER(product_family) = ?", [v])

            if key == "name_prefix":
                v = str(value).strip().lower()
                return ('LOWER(SUBSTR(TRIM(product_name), 1, INSTR(TRIM(product_name) || " ", " ") - 1)) = ?', [v])

            # IP rating
            if key == "ip_rating":
                v = str(value).strip().upper().replace(" ", "").replace("IPX", "IP0")
                m = re.search(r"(>=|<=|>|<)?IP(\d{2})", v)
                if not m:
                    return (None, [])
                op = m.group(1) or ">="
                num = float(m.group(2))
                frag = 'CAST(REPLACE(REPLACE(UPPER(ip_rating), "IPX", "IP0"), "IP", "") AS REAL) {} ?'.format(op)
                return (frag, [num])

            # IK rating
            if key == "ik_rating":
                v = str(value).strip().upper().replace(" ", "")
                m = re.search(r"(>=|<=|>|<)?IK(\d{1,2})", v)
                if not m:
                    return (None, [])
                op = m.group(1) or ">="
                num = float(m.group(2))
                frag = 'CAST(REPLACE(UPPER(ik_rating), "IK", "") AS REAL) {} ?'.format(op)
                return (frag, [num])

            # CCT
            if key == "cct_k":
                m = re.search(r"(\d+)", str(value))
                if not m:
                    return (None, [])
                return ("CAST(cct_k AS INTEGER) = ?", [int(m.group(1))])

            # UGR numeric (we filter on ugr_value, not on ugr text)
            if key == "ugr_value":
                v = str(value).strip().replace(" ", "")
                m = re.match(r"^(>=|<=|>|<)(\d+(?:\.\d+)?)$", v)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    return ('CAST("ugr_value" AS REAL) {} ?'.format(op), [num])
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", v).group())
                    return ('CAST("ugr_value" AS REAL) <= ?', [num])
                except Exception:
                    return (None, [])

            if key == "ugr":
                v = str(value).strip().replace(" ", "")
                m = re.match(r"^(>=|<=|>|<)(\d+(?:\.\d+)?)$", v)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    return ('CAST("ugr" AS REAL) {} ?'.format(op), [num])
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", v).group())
                    return ('CAST("ugr" AS REAL) <= ?', [num])
                except Exception:
                    return (None, [])

            # CRI numeric
            if key == "cri":
                v = str(value).strip().replace(" ", "")
                m = re.match(r"^(>=|<=|>|<|=)(\d+(?:\.\d+)?)$", v)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    return ('CAST("cri" AS REAL) {} ?'.format(op), [num])
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", v).group())
                    return ('CAST("cri" AS REAL) >= ?', [num])
                except Exception:
                    return (None, [])

            # Warranty numeric (same logic as CRI, default >=)
            if key == "warranty_years":
                v = str(value).strip().replace(" ", "")
                m = re.match(r"^(>=|<=|>|<|=)(\d+(?:\.\d+)?)$", v)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    col = "warranty_y_value" if "warranty_y_value" in table_columns else "warranty_years"
                    return (f'CAST("{col}" AS REAL) {op} ?', [num])
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", v).group())
                    col = "warranty_y_value" if "warranty_y_value" in table_columns else "warranty_years"
                    return (f'CAST("{col}" AS REAL) >= ?', [num])
                except Exception:
                    return (None, [])

            # Lifetime numeric (same logic as CRI, default >=)
            if key == "lifetime_hours":
                v = str(value).strip().replace(" ", "")
                m = re.match(r"^(>=|<=|>|<|=)(\d+(?:\.\d+)?)$", v)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    col = "lifetime_h_value" if "lifetime_h_value" in table_columns else "lifetime_hours"
                    return (f'CAST("{col}" AS REAL) {op} ?', [num])
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", v).group())
                    col = "lifetime_h_value" if "lifetime_h_value" in table_columns else "lifetime_hours"
                    return (f'CAST("{col}" AS REAL) >= ?', [num])
                except Exception:
                    return (None, [])

            # LED rated life numeric (same logic as CRI, default >=)
            if key == "led_rated_life_h":
                v = str(value).strip().replace(" ", "")
                m = re.match(r"^(>=|<=|>|<|=)(\d+(?:\.\d+)?)$", v)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    col = "led_rated_life_value" if "led_rated_life_value" in table_columns else "led_rated_life_h"
                    return (f'CAST("{col}" AS REAL) {op} ?', [num])
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", v).group())
                    col = "led_rated_life_value" if "led_rated_life_value" in table_columns else "led_rated_life_h"
                    return (f'CAST("{col}" AS REAL) >= ?', [num])
                except Exception:
                    return (None, [])

            # Lumen maintenance numeric (same logic as CRI, default >=)
            if key == "lumen_maintenance_pct":
                v = str(value).strip().replace(" ", "")
                m = re.match(r"^(>=|<=|>|<|=)(\d+(?:\.\d+)?)$", v)
                if m:
                    op, num = m.group(1), float(m.group(2))
                    return ('CAST("lumen_maintenance_pct" AS REAL) {} ?'.format(op), [num])
                try:
                    num = float(re.search(r"\d+(?:\.\d+)?", v).group())
                    return ('CAST("lumen_maintenance_pct" AS REAL) >= ?', [num])
                except Exception:
                    return (None, [])


            # Control protocol contains
            if key == "control_protocol":
                return ("LOWER(control_protocol) LIKE ?", [f"%{str(value).lower()}%"])

            # Numeric-ish fields (IMPORTANT: includes efficacy_lm_w)
            if key in {
                "power_max_w", "power_min_w", "lumen_output", "efficacy_lm_w",
                "warranty_years", "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct",
            }:
                numeric_companion = {
                    "power_max_w": "power_max_value",
                    "power_min_w": "power_min_value",
                    "lumen_output": "lumen_output_value",
                    "efficacy_lm_w": "efficacy_value",
                    "warranty_years": "warranty_y_value",
                    "lifetime_hours": "lifetime_h_value",
                    "led_rated_life_h": "led_rated_life_value",
                }
                col = numeric_companion.get(key, key)
                if col not in table_columns:
                    col = key
                frag, p = build_numeric_fragment(col, value, default_op=">=")
                return (frag, p)
            

            # fallback: contains match
            return (f'LOWER("{key}") LIKE ?', [f"%{str(value).lower()}%"])

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
        virtual_keys = {"name_prefix"}

        for key, value in (filters or {}).items():
            actual_key = key
            if actual_key not in table_columns and actual_key in alias_map and alias_map[actual_key] in table_columns:
                actual_key = alias_map[actual_key]
            if actual_key not in table_columns and actual_key not in virtual_keys:
                continue
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, list) and len(value) == 0:
                continue

            # multi-value OR
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

        query_parts.append("ORDER BY product_code LIMIT ?")
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
            print(f"❌ Search error: {e}")
            print(f"   Query: {query}")
            print(f"   Params: {params}")
            return []
    # def get_distinct_families(self, limit: int = 500) -> List[str]:
    #     if not self.conn:
    #         self.connect()

    #     cur = self.conn.execute("""
    #         SELECT DISTINCT LOWER(TRIM(product_family)) AS fam
    #         FROM products
    #         WHERE product_family IS NOT NULL
    #         AND TRIM(product_family) <> ''
    #         ORDER BY fam
    #         LIMIT ?
    #     """, (int(limit),))

    #     out = []
    #     for r in cur.fetchall():
    #         if r["fam"]:
    #             out.append(str(r["fam"]))
    #     return out
    def get_distinct_families(self, limit: int = 500) -> List[str]:
        if not self.conn:
            self.connect()
        
        # Prima verifica se la colonna esiste
        cursor = self.conn.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "product_family" not in columns:
            print("⚠️ Column 'product_family' not found in database!")
            return []
        
        # Query senza LOWER() per vedere i valori originali
        cur = self.conn.execute("""
            SELECT DISTINCT product_family AS fam
            FROM products
            WHERE product_family IS NOT NULL
            AND TRIM(product_family) <> ''
            ORDER BY fam
            LIMIT ?
        """, (int(limit),))
        
        out = []
        for r in cur.fetchall():
            if r["fam"]:
                out.append(str(r["fam"]))
        
        print(f"📊 Found {len(out)} distinct families: {out[:10]}")
        return out
