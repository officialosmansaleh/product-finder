import os
import sys
import unittest


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.scoring import score_product
from app.admin_settings import SETTINGS_BY_KEY
from app.schema import ALLOWED_FILTER_KEYS


class ScoringAdminSettingsTests(unittest.TestCase):
    def setUp(self):
        self._old_env = {
            "SCORING_WEIGHT_POWER_MAX_W": os.environ.get("SCORING_WEIGHT_POWER_MAX_W"),
            "SCORING_DEVIATION_PENALTY": os.environ.get("SCORING_DEVIATION_PENALTY"),
        }

    def tearDown(self):
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_field_weight_can_be_changed_live(self):
        product = {"power_max_w": "28", "cri": "80"}
        soft_filters = {"power_max_w": "<=20", "cri": ">=80"}

        default_score, *_ = score_product(product, {}, soft_filters)

        os.environ["SCORING_WEIGHT_POWER_MAX_W"] = "10"
        boosted_score, *_ = score_product(product, {}, soft_filters)

        self.assertLess(boosted_score, default_score)

    def test_deviation_penalty_can_be_changed_live(self):
        product = {"cri": "70"}
        soft_filters = {"cri": ">=80"}

        default_score, *_ = score_product(product, {}, soft_filters)

        os.environ["SCORING_DEVIATION_PENALTY"] = "0.2"
        relaxed_score, *_ = score_product(product, {}, soft_filters)

        self.assertGreater(relaxed_score, default_score)

    def test_all_filter_keys_have_scoring_settings(self):
        missing = [
            key for key in sorted(ALLOWED_FILTER_KEYS)
            if f"scoring_weight_{key}" not in SETTINGS_BY_KEY
        ]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
