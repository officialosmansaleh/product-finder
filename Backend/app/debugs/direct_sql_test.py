# app/direct_sql_test.py
import sqlite3

conn = sqlite3.connect("data/test_fixed.db")
conn.row_factory = sqlite3.Row

print("Direct SQL tests...")

# Test 1: Simple count
cursor = conn.execute("SELECT COUNT(*) as total FROM products")
total = cursor.fetchone()[0]
print(f"1. Total products: {total}")

# Test 2: Products with IP ratings
cursor = conn.execute("SELECT COUNT(*) as count FROM products WHERE ip_rating IS NOT NULL AND ip_rating != ''")
with_ip = cursor.fetchone()[0]
print(f"2. Products with IP rating: {with_ip}")

# Test 3: Try different IP queries
queries = [
    ("Exact IP65", 'SELECT COUNT(*) FROM products WHERE ip_rating = "IP65"'),
    ("Contains 65", 'SELECT COUNT(*) FROM products WHERE ip_rating LIKE "%65%"'),
    ("IP% pattern", 'SELECT COUNT(*) FROM products WHERE ip_rating LIKE "IP%"'),
    ("SUBSTR test", 'SELECT COUNT(*) FROM products WHERE ip_rating LIKE "IP%" AND SUBSTR(ip_rating, 3) = "65"'),
    ("Manual >=65", 'SELECT COUNT(*) FROM products WHERE ip_rating LIKE "IP%" AND CAST(SUBSTR(ip_rating, 3) AS INTEGER) >= 65'),
]

for name, sql in queries:
    try:
        cursor = conn.execute(sql)
        count = cursor.fetchone()[0]
        print(f"3. {name}: {count} products")
        
        if count > 0 and "Manual" in name:
            # Show samples
            sample_sql = sql.replace("COUNT(*)", "product_code, ip_rating") + " LIMIT 3"
            cursor = conn.execute(sample_sql)
            print(f"   Samples:")
            for row in cursor.fetchall():
                print(f"     {row[0]}: {row[1]}")
    except Exception as e:
        print(f"3. {name}: ERROR - {e}")

conn.close()