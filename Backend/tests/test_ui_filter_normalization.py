import os
import sys
import unittest


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("PF_SKIP_RUNTIME_INIT", "1")

from app.main import _normalize_ui_filters


class UiFilterNormalizationTests(unittest.TestCase):
    def test_preserves_range_filters_sent_as_lists(self):
        got = _normalize_ui_filters({
            "power_max_w": ["30-32"],
            "lumen_output": ["1000-2000"],
            "efficacy_lm_w": ["110-130"],
        })
        self.assertEqual(got["power_max_w"], ["30-32"])
        self.assertEqual(got["lumen_output"], ["1000-2000"])
        self.assertEqual(got["efficacy_lm_w"], ["110-130"])

    def test_normalizes_single_numeric_list_values_with_expected_direction(self):
        got = _normalize_ui_filters({
            "power_max_w": ["32"],
            "lumen_output": ["1000"],
            "warranty_years": ["5"],
            "lumen_maintenance_pct": ["70"],
        })
        self.assertEqual(got["power_max_w"], ["<=32"])
        self.assertEqual(got["lumen_output"], [">=1000"])
        self.assertEqual(got["warranty_years"], [">=5"])
        self.assertEqual(got["lumen_maintenance_pct"], [">=70"])

    def test_preserves_explicit_operators_for_list_values(self):
        got = _normalize_ui_filters({
            "ugr": ["<19"],
            "cri": [">80"],
            "ambient_temp_min_c": [">=-20"],
            "ambient_temp_max_c": ["<=45"],
        })
        self.assertEqual(got["ugr"], ["<=19"])
        self.assertEqual(got["cri"], [">=80"])
        self.assertEqual(got["ambient_temp_min_c"], ["<=-20"])
        self.assertEqual(got["ambient_temp_max_c"], ["<=45"])


if __name__ == "__main__":
    unittest.main()
