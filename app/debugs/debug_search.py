# app/debug_search.py
import sys
import os
sys.path.append('.')

from app.database import ProductDatabase

print("🔍 Debugging search issue...")

# Connect to database
db = ProductDatabase("data/test_fixed.db")

# 1. Check what IP ratings exist in the database
print("\n1. Checking IP ratings in database...")
conn = db.connect()
cursor = conn.execute('SELECT DISTINCT ip_rating FROM products WHERE ip_rating IS NOT NULL AND ip_rating != "" LIMIT 20')
ip_ratings = [row[0] for row in cursor.fetchall()]
print(f"   Found {len(ip_ratings)} unique IP ratings")
print(f"   Sample IP ratings: {ip_ratings[:10]}")

# 2. Check if any products have IP65 or higher
print("\n2. Testing different search queries...")

# Test 1: Exact match
cursor = conn.execute('SELECT COUNT(*) FROM products WHERE ip_rating = "IP65"')
count_exact = cursor.fetchone()[0]
print(f"   Products with exact 'IP65': {count_exact}")

# Test 2: Contains IP65
cursor = conn.execute('SELECT COUNT(*) FROM products WHERE ip_rating LIKE "%IP65%"')
count_like = cursor.fetchone()[0]
print(f"   Products containing 'IP65': {count_like}")

# Test 3: IP65 or higher (numeric comparison)
cursor = conn.execute('''
    SELECT COUNT(*) FROM products 
    WHERE ip_rating LIKE "IP%" 
    AND CAST(SUBSTR(ip_rating, 3) AS INTEGER) >= 65
''')
count_numeric = cursor.fetchone()[0]
print(f"   Products with IP65 or higher (numeric): {count_numeric}")

# Test 4: Show some samples
print("\n3. Sample products with IP ratings:")
cursor = conn.execute('''
    SELECT product_code, product_name, ip_rating 
    FROM products 
    WHERE ip_rating IS NOT NULL AND ip_rating != ""
    LIMIT 5
''')
for row in cursor.fetchall():
    print(f"   Code: {row[0]}, IP: {row[2]}, Name: {row[1][:30]}...")

# Test the actual search method
print("\n4. Testing db.search_products() method...")
test_filters = {"ip_rating": ">=IP65"}
results = db.search_products(test_filters, limit=5)
print(f"   search_products with '>=IP65': Found {len(results)} results")

if results:
    print("   Sample results:")
    for prod in results:
        print(f"     - {prod.get('product_code')}: IP {prod.get('ip_rating')}")

# Check what the actual query is doing
print("\n5. Debugging the search query...")
cursor = conn.execute("PRAGMA table_info(products)")
columns = [row[1] for row in cursor.fetchall()]
print(f"   Available columns: {columns}")

# Test raw SQL that should work
print("\n6. Testing raw SQL that should match...")
cursor = conn.execute('''
    SELECT COUNT(*) 
    FROM products 
    WHERE ip_rating LIKE "IP%" 
    AND CAST(SUBSTR(ip_rating, 3) AS INTEGER) >= 65
    LIMIT 10
''')
raw_count = cursor.fetchone()[0]
print(f"   Raw SQL count: {raw_count}")

db.close()
print("\n✅ Debug complete")