import os
import sys
import unittest
import tempfile
from unittest import mock

import pandas as pd


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.db_runtime import load_database_runtime_settings
from app.database import ProductDatabase


class DbRuntimeTests(unittest.TestCase):
    def test_runtime_settings_detect_postgres(self):
        old_url = os.environ.get("PRODUCT_DATABASE_URL")
        old_backend = os.environ.get("PRODUCT_DB_BACKEND")
        try:
            os.environ["PRODUCT_DATABASE_URL"] = "postgresql://user:pass@localhost:5432/productfinder"
            os.environ.pop("PRODUCT_DB_BACKEND", None)
            settings = load_database_runtime_settings()
            self.assertTrue(settings.product_postgres_requested)
            self.assertEqual(settings.product_db_backend, "postgres")
        finally:
            if old_url is None:
                os.environ.pop("PRODUCT_DATABASE_URL", None)
            else:
                os.environ["PRODUCT_DATABASE_URL"] = old_url
            if old_backend is None:
                os.environ.pop("PRODUCT_DB_BACKEND", None)
            else:
                os.environ["PRODUCT_DB_BACKEND"] = old_backend

    def test_product_database_backend_selection(self):
        pg = ProductDatabase(db_path="data/products.db", database_url="postgresql://user:pass@localhost:5432/productfinder")
        sq = ProductDatabase(db_path="data/products.db", database_url="")
        self.assertEqual(pg.backend, "postgres")
        self.assertEqual(sq.backend, "sqlite")

    def test_release_diff_export_tracks_only_changes(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "products.db")
            db = ProductDatabase(db_path=db_path, database_url="")
            try:
                release_one = pd.DataFrame([
                    {"product_code": "A1", "product_name": "Alpha", "product_family": "Street lighting", "price": "100"},
                    {"product_code": "B1", "product_name": "Beta", "product_family": "Linear", "price": "200"},
                ])
                release_two = pd.DataFrame([
                    {"product_code": "A1", "product_name": "Alpha Plus", "product_family": "Street lighting", "price": "110"},
                    {"product_code": "C1", "product_name": "Gamma", "product_family": "Floodlight", "price": "300"},
                ])
                with mock.patch("app.pim_loader.load_products", side_effect=[release_one, release_two]):
                    first = db.init_db("release-one.xlsx")
                    second = db.init_db("release-two.xlsx")
                self.assertEqual(first, 2)
                self.assertEqual(second, 2)

                diff = db.get_latest_release_diff()
                summary = diff["summary"]
                self.assertTrue(diff["has_release"])
                self.assertEqual(summary["added_count"], 1)
                self.assertEqual(summary["changed_count"], 1)
                self.assertEqual(summary["removed_count"], 1)
                self.assertEqual(summary["total_modified_products"], 3)

                by_code = {item["product_code"]: item for item in diff["items"]}
                self.assertEqual(by_code["C1"]["change_type"], "added")
                self.assertEqual(by_code["B1"]["change_type"], "removed")
                self.assertEqual(by_code["A1"]["change_type"], "changed")
                self.assertIn("product_name", by_code["A1"]["changed_fields"])
                self.assertIn("price", by_code["A1"]["changed_fields"])

                csv_text = db.export_latest_release_diff_csv()
                self.assertIn("product_code,change_type,field_name,previous_value,current_value", csv_text)
                self.assertIn("A1,changed,product_name,Alpha,Alpha Plus", csv_text)
                self.assertIn("B1,removed,product_name,Beta,", csv_text)
                self.assertIn("C1,added,product_name,,Gamma", csv_text)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
