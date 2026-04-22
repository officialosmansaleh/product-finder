import os
import sys
import unittest
from unittest.mock import patch

import pandas as pd


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class CatalogHealthTests(unittest.TestCase):
    def test_family_name_alias_normalization(self):
        from app.pim_loader import (
            _normalize_cct_value,
            _normalize_family_name,
            _normalize_ik_value,
            _normalize_ip_value,
            _normalize_numeric_measure,
        )

        self.assertEqual(_normalize_family_name("road lighting"), "Street lighting")
        self.assertEqual(_normalize_family_name(" Street lighting "), "Street lighting")
        self.assertEqual(_normalize_ip_value("ipx8"), "IP08")
        self.assertEqual(_normalize_ik_value("ik8"), "IK08")
        self.assertEqual(_normalize_cct_value("4000 k"), "4000K")
        self.assertEqual(_normalize_numeric_measure("15.0", "W"), "15 W")

    def test_catalog_health_detects_duplicates_and_legacy_alias(self):
        from app import main as main_mod

        fake_df = pd.DataFrame(
            [
                {
                    "product_code": "A1",
                    "product_family": "Street lighting",
                    "manufacturer": "Disano",
                    "product_name": "Street Alpha",
                    "price": 10,
                },
                {
                    "product_code": "A1",
                    "product_family": "road lighting",
                    "manufacturer": "Disano",
                    "product_name": "Street Beta",
                    "price": None,
                },
            ]
        )

        with patch.object(main_mod, "DB", fake_df):
            report = main_mod.catalog_health_impl()

        self.assertEqual(report["summary"]["rows"], 2)
        self.assertEqual(report["summary"]["duplicate_product_codes"], 2)
        self.assertEqual(report["summary"]["legacy_road_lighting_rows"], 1)
        issue_keys = {item["key"] for item in report["issues"]}
        self.assertIn("duplicate_product_codes", issue_keys)
        self.assertIn("legacy_family_alias", issue_keys)

    def test_catalog_health_detects_bad_spec_formats(self):
        from app import main as main_mod

        fake_df = pd.DataFrame(
            [
                {
                    "product_code": "B1",
                    "product_family": "Street lighting",
                    "manufacturer": "Disano",
                    "product_name": "Bad IP",
                    "ip_rating": "sixty five",
                    "ik_rating": "impact high",
                    "cct_k": "1234K",
                    "power_max_w": "0 W",
                    "lumen_output": "-10 lm",
                    "efficacy_lm_w": "0 lm/W",
                    "warranty_years": "-2",
                    "price": 100,
                }
            ]
        )

        with patch.object(main_mod, "DB", fake_df):
            report = main_mod.catalog_health_impl()

        issue_keys = {item["key"] for item in report["issues"]}
        self.assertIn("invalid_ip_format", issue_keys)
        self.assertIn("invalid_ik_format", issue_keys)
        self.assertIn("unexpected_cct_values", issue_keys)
        self.assertIn("non_positive_power", issue_keys)
        self.assertIn("non_positive_lumen", issue_keys)
        self.assertIn("non_positive_efficacy", issue_keys)
        self.assertIn("negative_warranty", issue_keys)


if __name__ == "__main__":
    unittest.main()
