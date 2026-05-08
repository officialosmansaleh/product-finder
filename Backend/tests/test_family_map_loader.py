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

    def test_pim_taxonomy_assigns_fixture_families_before_accessory_rules(self):
        with tempfile.TemporaryDirectory() as td:
            pim_path = os.path.join(td, "pim.xlsx")
            family_path = os.path.join(td, "family_map.xlsx")
            pd.DataFrame(
                [
                    {
                        "Order code": "H1",
                        "Short product code": "",
                        "Product name": "Hydro LED - HP - AC/DC driver",
                        "Etim Search Key": "Waterproof",
                        "Hierarchy": "Primary Product Hierarchy/Prodotti/APPARECCHI PER ILLUMINAZIONE/Armatura stagna ADVANCE/Hydro LED",
                        "Manufacturer": "DISANO",
                    },
                    {
                        "Order code": "M1",
                        "Short product code": "",
                        "Product name": "Mini Pastilla",
                        "Etim Search Key": "Civil and Commercial Interiors",
                        "Hierarchy": "Primary Product Hierarchy/Prodotti/APPARECCHI PER ILLUMINAZIONE/Downlight/Mini Pastilla",
                        "Manufacturer": "Fosnova",
                    },
                    {
                        "Order code": "A1",
                        "Short product code": "",
                        "Product name": "3500 Argon 3.6",
                        "Etim Search Key": "Commercial and industrial suspensions",
                        "Hierarchy": "Primary Product Hierarchy/Prodotti/APPARECCHI PER ILLUMINAZIONE/Riflettore industriali BASIC/3500 Argon",
                        "Manufacturer": "Fosnova",
                    },
                    {
                        "Order code": "L1",
                        "Short product code": "",
                        "Product name": "Micro Liset - cylindrical Professional",
                        "Etim Search Key": "Architectural systems",
                        "Hierarchy": "Primary Product Hierarchy/Prodotti/APPARECCHI PER ILLUMINAZIONE/Sistemi/Micro Liset",
                        "Manufacturer": "Fosnova",
                    },
                    {
                        "Order code": "B1",
                        "Short product code": "",
                        "Product name": "Fixed bracket for Micro Liset",
                        "Etim Search Key": "Mechanical accessory",
                        "Hierarchy": "Primary Product Hierarchy/Prodotti/ACCESSORI/Accessori meccanici e per fissaggio",
                        "Manufacturer": "Fosnova",
                    },
                ]
            ).to_excel(pim_path, index=False)
            pd.DataFrame(
                [
                    {
                        "Product name": "Placeholder",
                        "Product family": "Street lighting",
                        "Short product code": "9999",
                    }
                ]
            ).to_excel(family_path, index=False)

            loaded = load_products(pim_path, family_map_path=family_path, verbose=False)

        by_code = dict(zip(loaded["product_code"], loaded["product_family"]))
        self.assertEqual(by_code["H1"], "Waterproof")
        self.assertEqual(by_code["M1"], "downlight")
        self.assertEqual(by_code["A1"], "Highbay")
        self.assertEqual(by_code["L1"], "Linear")
        self.assertEqual(by_code["B1"], "Accessories")


if __name__ == "__main__":
    unittest.main()
