import os
import sys
import tempfile
import unittest

import pandas as pd


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.database import ProductDatabase
from app.pim_loader import _extract_first_number, _extract_ugr_op, _extract_ugr_value, load_products
from app.scoring import score_product


class PimLoaderUgrTests(unittest.TestCase):
    def test_extract_ugr_from_explicit_marker(self):
        text = "Beam 80 / CRI90 / UGR<lt/>19 / 3000K"
        self.assertEqual(_extract_ugr_value(text), 19)
        self.assertEqual(_extract_ugr_op(text), "<")

    def test_ignore_numbers_without_ugr_marker(self):
        text = "Beam 80 / CRI90 / 3000K"
        self.assertIsNone(_extract_ugr_value(text))
        self.assertIsNone(_extract_ugr_op(text))

    def test_extract_first_number_handles_lumen_thousands_separators(self):
        self.assertEqual(_extract_first_number("54.000 lm"), 54000)
        self.assertEqual(_extract_first_number("54,000 lm"), 54000)
        self.assertEqual(_extract_first_number("54 000 lm"), 54000)
        self.assertEqual(_extract_first_number("127.5 lm/W"), 127.5)

    def test_sqlite_ugr_filter_uses_numeric_helper_column(self):
        df = pd.DataFrame([
            {"product_code": "A1", "product_name": "Alpha", "product_family": "Panel", "ugr": "Beam 80 UGR<lt/>19 3000K", "ugr_value": 19},
            {"product_code": "B1", "product_name": "Beta", "product_family": "Panel", "ugr": "Beam 80 CRI90 3000K", "ugr_value": None},
            {"product_code": "C1", "product_name": "Gamma", "product_family": "Panel", "ugr": "UGR<lt/>25", "ugr_value": 25},
        ])

        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "products.db")
            db = ProductDatabase(db_path=db_path, database_url="")
            try:
                inserted = db.init_db("ugr-release.xlsx", df=df)
                self.assertEqual(inserted, 3)

                rows = db.search_products({"ugr": "<=19"})
                codes = {str(row.get("product_code")) for row in rows}
                self.assertEqual(codes, {"A1"})
            finally:
                db.close()

    def test_sqlite_lumen_filter_uses_normalized_thousands_value(self):
        df = pd.DataFrame([
            {"product_code": "A1", "product_name": "Alpha", "product_family": "Highbay", "lumen_output": "53.000 lm"},
            {"product_code": "B1", "product_name": "Beta", "product_family": "Highbay", "lumen_output": "68.900 lm"},
        ])

        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "products.db")
            db = ProductDatabase(db_path=db_path, database_url="")
            try:
                inserted = db.init_db("lumen-release.xlsx", df=df)
                self.assertEqual(inserted, 2)

                rows = db.search_products({"lumen_output": ">=54000"})
                codes = {str(row.get("product_code")) for row in rows}
                self.assertEqual(codes, {"B1"})
            finally:
                db.close()

    def test_sqlite_lifetime_exact_and_range_filters(self):
        df = pd.DataFrame([
            {"product_code": "A1", "product_name": "Alpha", "product_family": "Panel", "lifetime_hours": "9000 hr"},
            {"product_code": "B1", "product_name": "Beta", "product_family": "Panel", "lifetime_hours": "12000 hr"},
            {"product_code": "C1", "product_name": "Gamma", "product_family": "Panel", "lifetime_hours": "50000 hr"},
        ])

        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "products.db")
            db = ProductDatabase(db_path=db_path, database_url="")
            try:
                inserted = db.init_db("lifetime-release.xlsx", df=df)
                self.assertEqual(inserted, 3)

                exact_rows = db.search_products({"lifetime_hours": "=9000"})
                exact_codes = {str(row.get("product_code")) for row in exact_rows}
                self.assertEqual(exact_codes, {"A1"})

                range_rows = db.search_products({"lifetime_hours": "8000-13000"})
                range_codes = {str(row.get("product_code")) for row in range_rows}
                self.assertEqual(range_codes, {"A1", "B1"})
            finally:
                db.close()

    def test_sqlite_ambient_max_filter_uses_minimum_capability(self):
        df = pd.DataFrame([
            {"product_code": "A1", "product_name": "Cold", "product_family": "Panel", "ambient_temp_max_c": "40"},
            {"product_code": "B1", "product_name": "Hot", "product_family": "Panel", "ambient_temp_max_c": "50"},
            {"product_code": "C1", "product_name": "Hotter", "product_family": "Panel", "ambient_temp_max_c": "60"},
        ])

        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "products.db")
            db = ProductDatabase(db_path=db_path, database_url="")
            try:
                inserted = db.init_db("ambient-release.xlsx", df=df)
                self.assertEqual(inserted, 3)

                rows = db.search_products({"ambient_temp_max_c": ">=50"})
                codes = {str(row.get("product_code")) for row in rows}
                self.assertEqual(codes, {"B1", "C1"})
            finally:
                db.close()

    def test_pim_switch_table_expands_power_lumen_and_cct_capability(self):
        description = """Rubin switch table
|***
Code;Wtot;LED(mA);K - Lumen Output - CRI - °
22163710-00 / 22163730-00;9;250;3000K - 1080lm - CRI>80 - 42°
22163710-00 / 22163730-00;12;300;3000K - 1425lm - CRI>80 - 42°
22163710-00 / 22163730-00;9;250;4000K - 1136lm - CRI>80 - 42°
22163710-00 / 22163730-00;12;300;4000K - 1536lm - CRI>80 - 42°
***|"""
        pim = pd.DataFrame([
            {
                "Order code": "22163710-00",
                "<Name>": "Rubin",
                "Short product code": "221637",
                "Product description": description,
                "Total system power": "12 W",
                "Luminous efficacy": "100 lm/W",
                "CCT": "3000 K",
                "Manufacturer": "Disano",
            }
        ])
        family_map = pd.DataFrame([
            {"Short product code": "221637", "Product name": "Rubin", "family": "downlight"}
        ])

        with tempfile.TemporaryDirectory() as td:
            pim_path = os.path.join(td, "pim.xlsx")
            family_path = os.path.join(td, "family.xlsx")
            pim.to_excel(pim_path, index=False)
            family_map.to_excel(family_path, index=False)

            loaded = load_products(pim_path, family_map_path=family_path, verbose=False)
            row = loaded.iloc[0].to_dict()
            self.assertEqual(row["power_max_w"], "9-12 W")
            self.assertEqual(row["lumen_output"], "1080-1536 lm")
            self.assertEqual(row["cct_k"], "3000K / 4000K")
            self.assertEqual(row["switch_power_min_value"], 9)
            self.assertEqual(row["switch_power_max_value"], 12)
            self.assertEqual(row["switch_lumen_min_value"], 1080)
            self.assertEqual(row["switch_lumen_max_value"], 1536)
            self.assertEqual(row["switch_cct_options"], "3000,4000")

    def test_sqlite_switch_capability_filters_match_any_valid_setting(self):
        df = pd.DataFrame([
            {
                "product_code": "SW1",
                "product_name": "Switch",
                "product_family": "downlight",
                "power_max_w": "9-12 W",
                "power_max_value": "12",
                "lumen_output": "1080-1536 lm",
                "lumen_output_value": "1536",
                "cct_k": "3000K / 4000K",
                "switch_power_min_value": "9",
                "switch_power_max_value": "12",
                "switch_lumen_min_value": "1080",
                "switch_lumen_max_value": "1536",
                "switch_cct_options": "3000,4000",
            }
        ])

        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "products.db")
            db = ProductDatabase(db_path=db_path, database_url="")
            try:
                self.assertEqual(db.init_db("switch-release.xlsx", df=df), 1)
                self.assertEqual({r["product_code"] for r in db.search_products({"power_max_w": "<=10"})}, {"SW1"})
                self.assertEqual({r["product_code"] for r in db.search_products({"lumen_output": ">=1500"})}, {"SW1"})
                self.assertEqual({r["product_code"] for r in db.search_products({"cct_k": "4000"})}, {"SW1"})
            finally:
                db.close()

    def test_scoring_switch_capability_matches_any_valid_setting(self):
        product = {
            "product_code": "SW1",
            "product_name": "Switch",
            "power_max_w": "9-12 W",
            "lumen_output": "1080-1536 lm",
            "cct_k": "3000K / 4000K",
            "switch_power_min_value": "9",
            "switch_power_max_value": "12",
            "switch_lumen_min_value": "1080",
            "switch_lumen_max_value": "1536",
            "switch_cct_options": "3000,4000",
        }

        score, matched, deviations, missing = score_product(
            product,
            {"power_max_w": "<=10", "lumen_output": ">=1500", "cct_k": "4000"},
            {},
        )
        self.assertEqual(score, 1.0)
        self.assertIn("power_max_w", matched)
        self.assertEqual(deviations, [])
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
