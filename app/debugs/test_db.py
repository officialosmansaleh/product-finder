# app/test_db_fixed.py
import sys
import os

# Add parent directory to path
sys.path.append('.')

print("🧪 Testing database setup (FIXED VERSION)...")

try:
    from app.database import ProductDatabase
    from app.pim_loader import load_products
    
    # Test 1: Load products
    print("\n1. Testing Excel loading...")
    try:
        xlsx_path = "data/ExportRO-2025-10-28_09.34.43.xlsx"
        if os.path.exists(xlsx_path):
            df = load_products(xlsx_path, verbose=True)
            print(f"✅ Excel loading OK: {len(df)} products")
            print(f"   Columns: {list(df.columns)}")
            print(f"   Has 'etim_search_key' column: {'etim_search_key' in df.columns}")
        else:
            print(f"❌ Excel file not found at: {xlsx_path}")
            # Try alternative paths
            for alt_path in [
                "../data/ExportRO-2025-10-28_09.34.43.xlsx",
                "./ExportRO-2025-10-28_09.34.43.xlsx"
            ]:
                if os.path.exists(alt_path):
                    df = load_products(alt_path, verbose=False)
                    print(f"✅ Excel loading OK (from {alt_path}): {len(df)} products")
                    break
    except Exception as e:
        print(f"❌ Excel loading failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Create database
    print("\n2. Testing database creation...")
    try:
        # Use a test database
        db_path = "data/test_fixed.db"
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"🗑️  Removed old test database")
            
        db = ProductDatabase(db_path)
        count = db.init_db(xlsx_path)
        print(f"✅ Database creation: {count} products loaded")
        
        # Test 3: Get stats
        print("\n3. Testing database stats...")
        stats = db.get_stats()
        print(f"✅ Database stats: {stats['total_products']} total products")
        
        # Test 4: Simple search
        print("\n4. Testing search...")
        test_filters = {"ip_rating": ">=IP65"}
        results = db.search_products(test_filters, limit=3)
        print(f"✅ Search test: Found {len(results)} products with IP65 or higher")
        
        if results:
            print("\n📦 Sample products:")
            for i, prod in enumerate(results[:2]):
                print(f"  Product {i+1}:")
                print(f"    Code: {prod.get('product_code')}")
                print(f"    Name: {prod.get('product_name', 'N/A')[:50]}...")
                print(f"    IP: {prod.get('ip_rating', 'N/A')}")
                print(f"    CCT: {prod.get('cct_k', 'N/A')}")
                print(f"    Family: {prod.get('product_family', 'N/A')}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("\n🔍 Checking what's wrong...")
    
    # Check if files exist
    for file in ['database.py', 'pim_loader.py']:
        path = f"app/{file}"
        if os.path.exists(path):
            print(f"✅ {file} exists")
            with open(path, 'r') as f:
                content = f.read()
                if "class ProductDatabase" in content and file == "database.py":
                    print(f"   Contains ProductDatabase class")
                if "def load_products" in content and file == "pim_loader.py":
                    print(f"   Contains load_products function")
        else:
            print(f"❌ {file} not found")