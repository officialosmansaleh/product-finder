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
from app.pim_loader import _extract_ugr_op, _extract_ugr_value


class PimLoaderUgrTests(unittest.TestCase):
    def test_extract_ugr_from_explicit_marker(self):
        text = "Beam 80 / CRI90 / UGR<lt/>19 / 3000K"
        self.assertEqual(_extract_ugr_value(text), 19)
        self.assertEqual(_extract_ugr_op(text), "<")

    def test_ignore_numbers_without_ugr_marker(self):
        text = "Beam 80 / CRI90 / 3000K"
        self.assertIsNone(_extract_ugr_value(text))
        self.assertIsNone(_extract_ugr_op(text))

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


if __name__ == "__main__":
    unittest.main()
