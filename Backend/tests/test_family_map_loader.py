import os
import sys
import tempfile
import unittest

import pandas as pd


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.pim_loader import load_products


class FamilyMapLoaderTests(unittest.TestCase):
    def test_product_family_column_variant_is_used_from_family_map(self):
        with tempfile.TemporaryDirectory() as td:
            pim_path = os.path.join(td, "pim.xlsx")
            family_path = os.path.join(td, "family_map.xlsx")
            pd.DataFrame(
                [
                    {
                        "Order code": "A1",
                        "Short product code": "1252",
                        "Product name": "Alpha 100",
                        "Manufacturer": "DISANO",
                    }
                ]
            ).to_excel(pim_path, index=False)
            pd.DataFrame(
                [
                    {
                        "Product name": "Alpha",
                        "Product family": "Street lighting",
                        "Short product code": "1252",
                    }
                ]
            ).to_excel(family_path, index=False)

            loaded = load_products(pim_path, family_map_path=family_path, verbose=False)

        self.assertEqual(loaded["product_family"].tolist(), ["Street lighting"])

    def test_missing_family_map_does_not_use_short_code_as_family(self):
        with tempfile.TemporaryDirectory() as td:
            pim_path = os.path.join(td, "pim.xlsx")
            pd.DataFrame(
                [
                    {
                        "Order code": "A1",
                        "Short product code": "1252",
                        "Product name": "Alpha 100",
                        "Manufacturer": "DISANO",
                    }
                ]
            ).to_excel(pim_path, index=False)

            with self.assertRaisesRegex(ValueError, "No valid family map"):
                load_products(pim_path, family_map_path=os.path.join(td, "missing.xlsx"), verbose=False)


if __name__ == "__main__":
    unittest.main()
