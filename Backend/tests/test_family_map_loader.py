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

    def test_duplicate_short_code_uses_product_name_composite_key(self):
        with tempfile.TemporaryDirectory() as td:
            pim_path = os.path.join(td, "pim.xlsx")
            family_path = os.path.join(td, "family_map.xlsx")
            pd.DataFrame(
                [
                    {
                        "Order code": "A1",
                        "Short product code": "1782",
                        "Product name": "Astro HP",
                        "Manufacturer": "DISANO",
                    },
                    {
                        "Order code": "R1",
                        "Short product code": "1782",
                        "Product name": "Roda 50",
                        "Manufacturer": "DISANO",
                    },
                ]
            ).to_excel(pim_path, index=False)
            pd.DataFrame(
                [
                    {
                        "Product name": "Astro",
                        "Product family": "floodlight",
                        "Short product code": "1782",
                    },
                    {
                        "Product name": "Roda",
                        "Product family": "Waterproof",
                        "Short product code": "1782",
                    },
                ]
            ).to_excel(family_path, index=False)

            loaded = load_products(pim_path, family_map_path=family_path, verbose=False)

        by_code = dict(zip(loaded["product_code"], loaded["product_family"]))
        self.assertEqual(by_code["A1"], "floodlight")
        self.assertEqual(by_code["R1"], "Waterproof")

    def test_unmapped_and_accessory_rows_are_grouped_as_accessories(self):
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
                    },
                    {
                        "Order code": "993990-00",
                        "Short product code": "539",
                        "Product name": "539 Skirt - 320 mm",
                        "Manufacturer": "DISANO",
                        "Product family": "Lighting accessory",
                    },
                    {
                        "Order code": "U1",
                        "Short product code": "9999",
                        "Product name": "Unmapped item",
                        "Manufacturer": "DISANO",
                    },
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

        by_code = dict(zip(loaded["product_code"], loaded["product_family"]))
        self.assertEqual(by_code["A1"], "Street lighting")
        self.assertEqual(by_code["993990-00"], "Accessories")
        self.assertEqual(by_code["U1"], "Accessories")

    def test_etim_downlight_taxonomy_overrides_broad_family_map(self):
        with tempfile.TemporaryDirectory() as td:
            pim_path = os.path.join(td, "pim.xlsx")
            family_path = os.path.join(td, "family_map.xlsx")
            pd.DataFrame(
                [
                    {
                        "Order code": "22163013-00",
                        "Short product code": "",
                        "Product name": "Techno B 114 - CCT - DIP SWITCH",
                        "Etim Search Key": "Recessed downlights",
                        "Manufacturer": "Fosnova",
                    },
                    {
                        "Order code": "22093030-00",
                        "Short product code": "",
                        "Product name": "Ring - Techno B 114",
                        "Etim Search Key": "Mechanical accessory",
                        "Manufacturer": "Fosnova",
                    },
                ]
            ).to_excel(pim_path, index=False)
            pd.DataFrame(
                [
                    {
                        "Product name": "Techno",
                        "Product family": "Linear",
                        "Short product code": "",
                    }
                ]
            ).to_excel(family_path, index=False)

            loaded = load_products(pim_path, family_map_path=family_path, verbose=False)

        by_code = dict(zip(loaded["product_code"], loaded["product_family"]))
        self.assertEqual(by_code["22163013-00"], "downlight")
        self.assertEqual(by_code["22093030-00"], "Accessories")


if __name__ == "__main__":
    unittest.main()
