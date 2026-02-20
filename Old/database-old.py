# app/database.py (FIXED VERSION)
import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
import re
import os

class ProductDatabase:
    """SQLite database for products - FIXED VERSION"""
    
    def __init__(self, db_path: str = "data/products.db"):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Establish database connection"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def _create_table_from_columns(self, columns: List[str]):
        """Create table with all required columns"""
        # Always include these base columns
        base_columns = [
            "id INTEGER PRIMARY KEY AUTOINCREMENT",
            "imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ]
        
        # Add all DataFrame columns
        for col in columns:
            if col not in ['id', 'imported_at']:
                # Use TEXT for everything to keep it simple
                base_columns.append(f'"{col}" TEXT')
        
        create_sql = f"CREATE TABLE IF NOT EXISTS products ({', '.join(base_columns)})"
        self.conn.execute(create_sql)
        self.conn.commit()
        
        # Verify table was created
        cursor = self.conn.execute("PRAGMA table_info(products)")
        created_columns = [row[1] for row in cursor.fetchall()]
        
        print(f"📋 Table created with {len(created_columns)} columns")
        print(f"📋 Missing from DataFrame but expected: {set(columns) - set(created_columns)}")
        print(f"📋 Extra in table: {set(created_columns) - set(columns)}")
    
    def _add_missing_columns(self, required_columns: List[str]):
        """Add any missing columns to the table"""
        cursor = self.conn.execute("PRAGMA table_info(products)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        for col in required_columns:
            if col not in existing_columns and col not in ['id', 'imported_at']:
                try:
                    self.conn.execute(f'ALTER TABLE products ADD COLUMN "{col}" TEXT')
                    print(f"➕ Added missing column: {col}")
                except Exception as e:
                    print(f"⚠️  Failed to add column {col}: {e}")
        
        self.conn.commit()
    
    def init_db(self, xlsx_path: str, family_map_path: str = None):
        """Initialize database from Excel file - FIXED"""
        print(f"🔄 Initializing SQLite database from {xlsx_path}...")
        
        # Import pim_loader
        from app.pim_loader import load_products
        
        try:
            # Load products with verbose to see what's happening
            df = load_products(xlsx_path, verbose=True)  # Changed to True for debugging
            if df is None or df.empty:
                print("❌ No products loaded")
                return 0
                
            print(f"📊 DataFrame shape: {df.shape}")
            print(f"📊 DataFrame columns: {list(df.columns)}")
                
        except Exception as e:
            print(f"❌ Failed to load products: {e}")
            import traceback
            traceback.print_exc()
            return 0
        
        self.connect()
        
        # Get all columns from DataFrame
        columns = list(df.columns)
        print(f"🎯 Columns to store ({len(columns)}): {columns}")
        
        # Create or update table
        self._create_table_from_columns(columns)
        
        # Ensure all columns exist
        self._add_missing_columns(columns)
        
        # Insert or update products
        inserted = 0
        updated = 0
        errors = 0
        
        for idx, row in df.iterrows():
            try:
                # Prepare data - ensure all columns are present
                row_data = {}
                for col in columns:
                    value = row[col]
                    if pd.isna(value):
                        row_data[col] = None
                    else:
                        row_data[col] = str(value).strip()
                
                # Check if product exists
                product_code = row_data.get('product_code', '')
                if not product_code:
                    print(f"⚠️  Row {idx} has no product_code, skipping")
                    continue
                
                cursor = self.conn.execute(
                    'SELECT id FROM products WHERE product_code = ?',
                    (product_code,)
                )
                
                if cursor.fetchone():
                    # Update existing - build dynamic UPDATE
                    update_parts = []
                    values = []
                    for col, val in row_data.items():
                        update_parts.append(f'"{col}" = ?')
                        values.append(val)
                    values.append(product_code)  # For WHERE clause
                    
                    update_sql = f'UPDATE products SET {", ".join(update_parts)} WHERE product_code = ?'
                    self.conn.execute(update_sql, values)
                    updated += 1
                    
                    if updated % 1000 == 0:
                        print(f"   Updated {updated} products...")
                        
                else:
                    # Insert new - build dynamic INSERT
                    cols = ', '.join([f'"{c}"' for c in row_data.keys()])
                    placeholders = ', '.join(['?'] * len(row_data))
                    
                    insert_sql = f'INSERT INTO products ({cols}) VALUES ({placeholders})'
                    self.conn.execute(insert_sql, list(row_data.values()))
                    inserted += 1
                    
                    if inserted % 1000 == 0:
                        print(f"   Inserted {inserted} products...")
                        
            except Exception as e:
                errors += 1
                if errors <= 5:  # Only show first 5 errors
                    print(f"❌ Error with product {row.get('product_code', f'row {idx}')}: {e}")
                continue
        
        # Create indexes for key fields
        key_fields = ['ip_rating', 'cct_k', 'power_max_w', 'control_protocol', 'product_family']
        for field in key_fields:
            if field in columns:
                try:
                    idx_name = f'idx_{field.replace("_", "")}'
                    self.conn.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON products("{field}")')
                except Exception as e:
                    print(f"⚠️  Could not create index for {field}: {e}")
        
        self.conn.commit()
        
        print(f"\n✅ Database initialization complete:")
        print(f"   📥 Inserted: {inserted}")
        print(f"   🔄 Updated: {updated}")
        print(f"   ❌ Errors: {errors}")
        print(f"   📊 Total in database: {inserted + updated}")
        
        return inserted + updated
    
    def search_products(self, filters: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
        """Search products in database"""
        if not self.conn:
            self.connect()
        
        # Get available columns
        cursor = self.conn.execute("PRAGMA table_info(products)")
        table_columns = [row[1] for row in cursor.fetchall()]
        
        query_parts = ['SELECT * FROM products WHERE 1=1']
        params = []
        
        for key, value in filters.items():
            if value is None or value == "" or key not in table_columns:
                continue
                
            if key == 'ip_rating' and value:
                # Supports stored values like "65.0" or "IP65"
                if isinstance(value, str) and value.startswith('>='):
                    ip_match = re.search(r'(\d+)', value)
                    if ip_match:
                        query_parts.append(
                            'AND CAST(REPLACE(ip_rating, "IP", "") AS REAL) >= ?'
                        )
                        params.append(float(ip_match.group(1)))
                else:
                    ip_match = re.search(r'(\d+)', str(value))
                    if ip_match:
                        query_parts.append(
                            'AND CAST(REPLACE(ip_rating, "IP", "") AS REAL) = ?'
                        )
                        params.append(float(ip_match.group(1)))

            
            elif key == 'cct_k' and value:
                    # Stored like "4000 K" -> match by numeric part
                    m = re.search(r'(\d+)', str(value))
                    if m:
                        query_parts.append('AND CAST(cct_k AS INTEGER) = ?')
                        params.append(int(m.group(1)))

            
            elif key == 'control_protocol' and value:
                query_parts.append('AND LOWER(control_protocol) LIKE ?')
                params.append(f"%{str(value).lower()}%")
            elif key == "product_family" and value:
                # exact match, case-insensitive
                query_parts.append('AND LOWER(product_family) = ?')
                params.append(str(value).strip().lower())
            
            elif key in ['power_min_w', 'power_max_w'] and value:
                try:
                    v = str(value).strip()

                    # Support ">=40", "<=40", ">40", "<40"
                    m = re.match(r'^(>=|<=|>|<)\s*(\d+(?:\.\d+)?)$', v)
                    if m:
                        op, num = m.group(1), float(m.group(2))

                        # both filters are applied against the product's power_max_w column (your current design)
                        if op == ">=":
                            query_parts.append('AND CAST(power_max_w AS REAL) >= ?')
                        elif op == ">":
                            query_parts.append('AND CAST(power_max_w AS REAL) > ?')
                        elif op == "<=":
                            query_parts.append('AND CAST(power_max_w AS REAL) <= ?')
                        elif op == "<":
                            query_parts.append('AND CAST(power_max_w AS REAL) < ?')

                        params.append(num)

                    # Support range "30-40"
                    elif "-" in v:
                        a, b = v.split("-", 1)
                        a_f = float(a.strip())
                        b_f = float(b.strip())
                        lo, hi = (a_f, b_f) if a_f <= b_f else (b_f, a_f)
                        query_parts.append('AND CAST(power_max_w AS REAL) >= ?')
                        query_parts.append('AND CAST(power_max_w AS REAL) <= ?')
                        params.extend([lo, hi])

                    # Plain number "40"
                    else:
                        num = float(v)
                        if key == 'power_min_w':
                            query_parts.append('AND CAST(power_max_w AS REAL) >= ?')
                        else:
                            query_parts.append('AND CAST(power_max_w AS REAL) <= ?')
                        params.append(num)

                    

                except Exception:
                    pass

        
        query_parts.append(f'ORDER BY product_code LIMIT {limit}')
        
        query = ' '.join(query_parts)
        try:
            cursor = self.conn.execute(query, params)
            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                # Remove internal fields
                row_dict.pop('id', None)
                row_dict.pop('imported_at', None)
                results.append(row_dict)
            return results
        except Exception as e:
            print(f"❌ Search error: {e}")
            print(f"   Query: {query}")
            print(f"   Params: {params}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        if  self.conn is None:
            self.connect()
        
        stats = {'total_products': 0, 'field_coverage': {}}
        
        try:
            cursor = self.conn.execute('SELECT COUNT(*) FROM products')
            stats['total_products'] = cursor.fetchone()[0]
            
            # Get key fields coverage
            key_fields = ['ip_rating', 'cct_k', 'power_max_w', 'control_protocol', 
                         'lumen_output', 'product_family', 'emergency_present']
            
            cursor = self.conn.execute("PRAGMA table_info(products)")
            table_columns = [row[1] for row in cursor.fetchall()]
            
            for field in key_fields:
                if field in table_columns:
                    cursor = self.conn.execute(
                        f'SELECT COUNT(*) FROM products WHERE "{field}" IS NOT NULL AND "{field}" != ""'
                    )
                    stats['field_coverage'][field] = cursor.fetchone()[0]
                else:
                    stats['field_coverage'][field] = 0
                    
        except Exception as e:
            print(f"❌ Stats error: {e}")
        
        return stats
    # temp
    def debug_sample(self, n: int = 3):
        if self.conn is None:
            self.connect()
        cur = self.conn.execute('SELECT ip_rating, cct_k, power_max_w FROM products WHERE ip_rating IS NOT NULL LIMIT ?', (n,))
        return [dict(r) for r in cur.fetchall()]
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    


# Test
if __name__ == "__main__":
    print("✅ Database module ready")