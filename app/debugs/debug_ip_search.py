# app/debug_ip_search.py (FIXED - with import)
import sys
import os
import re  # ← ADD THIS IMPORT
sys.path.append('.')

from app.database import ProductDatabase

print("🔍 Debugging IP rating search issue...")

# Connect to the test database
db = ProductDatabase("data/test_fixed.db")
conn = db.connect()

# 1. First, let's see what IP ratings actually exist
print("\n1. Checking actual IP rating values in database...")
cursor = conn.execute('''
    SELECT ip_rating, COUNT(*) as count 
    FROM products 
    WHERE ip_rating IS NOT NULL AND ip_rating != ''
    GROUP BY ip_rating
    ORDER BY count DESC
    LIMIT 20
''')

print("   Top IP ratings:")
for row in cursor.fetchall():
    ip = row[0]
    count = row[1]
    print(f"   '{ip}': {count} products")
    
    # Debug: Check what SUBSTR would extract
    if ip and isinstance(ip, str) and ip.startswith('IP'):
        try:
            num_part = ip[2:]  # Remove 'IP' prefix
            if num_part and num_part.isdigit():
                ip_num = int(num_part)
                print(f"      → Numeric part: {ip_num} (>=65? {ip_num >= 65})")
        except:
            pass

# 2. Test the exact query the search_products method would generate
print("\n2. Testing the search query logic...")

# Test different IP rating patterns
test_ips = [
    ">=IP65",
    "IP65",
    "65",
    "IP66",
    "IP67",
]

for test_ip in test_ips:
    print(f"\n   Testing filter: ip_rating = '{test_ip}'")
    
    # Build query like search_products does
    query_parts = ['SELECT COUNT(*) FROM products WHERE 1=1']
    params = []
    
    if test_ip.startswith('>='):
        ip_match = re.search(r'(\d+)', test_ip)
        if ip_match:
            query_parts.append('AND (ip_rating LIKE "IP%" AND CAST(SUBSTR(ip_rating, 3) AS INTEGER) >= ?)')
            params.append(int(ip_match.group(1)))
    else:
        query_parts.append('AND ip_rating = ?')
        params.append(str(test_ip))
    
    query = ' '.join(query_parts)
    
    try:
        cursor = conn.execute(query, params)
        count = cursor.fetchone()[0]
        print(f"      Query: {query}")
        print(f"      Params: {params}")
        print(f"      Result: {count} products")
    except Exception as e:
        print(f"      ❌ Query failed: {e}")

# 3. Check if SUBSTR function works correctly
print("\n3. Testing SUBSTR function on actual data...")
cursor = conn.execute('''
    SELECT ip_rating, 
           SUBSTR(ip_rating, 3) as substr_result,
           CAST(SUBSTR(ip_rating, 3) AS INTEGER) as numeric_result
    FROM products 
    WHERE ip_rating LIKE 'IP%'
    AND ip_rating IS NOT NULL
    LIMIT 10
''')

print("   SUBSTR test results:")
for row in cursor.fetchall():
    ip = row[0]
    substr = row[1]
    numeric = row[2]
    print(f"   '{ip}' → SUBSTR: '{substr}', Numeric: {numeric}")

# 4. Try a manual query that should work
print("\n4. Manual query to find IP65 or higher...")
cursor = conn.execute('''
    SELECT COUNT(*) 
    FROM products 
    WHERE ip_rating LIKE 'IP%'
    AND CAST(SUBSTR(ip_rating, 3) AS INTEGER) >= 65
''')
manual_count = cursor.fetchone()[0]
print(f"   Manual query count: {manual_count} products")

# 5. If manual query works, debug why search_products doesn't
if manual_count > 0:
    print("\n5. Comparing manual vs search_products...")
    
    # Get some sample products from manual query
    cursor = conn.execute('''
        SELECT product_code, ip_rating 
        FROM products 
        WHERE ip_rating LIKE 'IP%'
        AND CAST(SUBSTR(ip_rating, 3) AS INTEGER) >= 65
        LIMIT 5
    ''')
    
    print("   Sample products (manual query):")
    for row in cursor.fetchall():
        print(f"     {row[0]}: {row[1]}")
    
    # Now test search_products
    print("\n   Testing search_products method:")
    results = db.search_products({"ip_rating": ">=IP65"}, limit=5)
    print(f"     search_products found: {len(results)}")
    
    if results:
        for prod in results:
            print(f"     {prod.get('product_code')}: {prod.get('ip_rating')}")
    else:
        print("     ❌ No results from search_products!")

# 6. Check for data issues
print("\n6. Checking for data format issues...")

# Check for non-standard IP formats
cursor = conn.execute('''
    SELECT DISTINCT ip_rating 
    FROM products 
    WHERE ip_rating IS NOT NULL 
    AND ip_rating != ''
    AND (
        ip_rating NOT LIKE 'IP%' 
        OR LENGTH(ip_rating) < 3 
        OR SUBSTR(ip_rating, 3) NOT GLOB '[0-9]*'
    )
    LIMIT 10
''')

non_standard = cursor.fetchall()
if non_standard:
    print("   Non-standard IP formats found:")
    for row in non_standard:
        print(f"     '{row[0]}'")
else:
    print("   All IP ratings appear to be standard format")

db.close()
print("\n✅ Debug complete")