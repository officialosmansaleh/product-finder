import importlib
import os
import sys
import unittest
from unittest.mock import patch


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class LLMIntentNormalizationTests(unittest.TestCase):
    def test_text_intent_normalizes_and_filters_llm_output(self):
        import app.llm_intent as llm_intent

        fake_result = {
            "status": "ok",
            "provider": "openai",
            "model": "test-model",
            "used_retry": False,
            "message": "",
            "content": {
                "product_family": "road lighting",
                "ip_rating": "ip65",
                "ik_rating": "ik8",
                "ugr": "19",
                "cri": "80",
                "power_max_w": "40 W",
                "efficacy_lm_w": "140 lm/W",
                "lifetime_hours": "50.000 h",
                "cct_k": "4000 K",
                "shape": "circular",
                "emergency_present": "si",
                "unknown_field": "ignored",
                "confidence": "high",
                "notes": "ignored",
            },
        }

        with patch.object(llm_intent, "infer_text_filters", return_value=fake_result):
            result = llm_intent.llm_intent_to_filters_with_meta(
                "stradale ip65 ik08 ugr 19 cri 80",
                allowed_families=["street lighting", "floodlight"],
            )

        filters = result["filters"]
        self.assertEqual(filters["product_family"], "street lighting")
        self.assertEqual(filters["ip_rating"], ">=IP65")
        self.assertEqual(filters["ik_rating"], ">=IK08")
        self.assertEqual(filters["ugr"], "<=19")
        self.assertEqual(filters["cri"], ">=80")
        self.assertEqual(filters["power_max_w"], "<=40")
        self.assertEqual(filters["efficacy_lm_w"], ">=140")
        self.assertEqual(filters["lifetime_hours"], ">=50000")
        self.assertEqual(filters["cct_k"], "4000")
        self.assertEqual(filters["shape"], "round")
        self.assertEqual(filters["emergency_present"], "yes")
        self.assertNotIn("unknown_field", filters)
        self.assertNotIn("confidence", filters)

    def test_invalid_llm_family_is_dropped_when_allowed_families_are_known(self):
        import app.llm_intent as llm_intent

        fake_result = {
            "status": "ok",
            "provider": "openai",
            "model": "test-model",
            "used_retry": False,
            "message": "",
            "content": {"product_family": "decorative chandelier", "ip_rating": "IP44"},
        }

        with patch.object(llm_intent, "infer_text_filters", return_value=fake_result):
            filters = llm_intent.llm_intent_to_filters(
                "decorative chandelier ip44",
                allowed_families=["street lighting", "floodlight"],
            )

        self.assertNotIn("product_family", filters)
        self.assertEqual(filters["ip_rating"], ">=IP44")

    def test_faro_is_not_promoted_to_floodlight_by_llm(self):
        import app.llm_intent as llm_intent

        fake_result = {
            "status": "ok",
            "provider": "openai",
            "model": "test-model",
            "used_retry": False,
            "message": "",
            "content": {"product_family": "floodlight", "ip_rating": "IP66"},
        }

        with patch.object(llm_intent, "infer_text_filters", return_value=fake_result):
            filters = llm_intent.llm_intent_to_filters(
                "faro esterno IP66 DALI 4000K 54000 lumen",
                allowed_families=["Street lighting", "floodlight"],
            )

        self.assertNotIn("product_family", filters)
        self.assertEqual(filters["ip_rating"], ">=IP66")

    def test_model_candidates_can_be_configured_from_environment(self):
        import app.ai_service as ai_service

        old_value = os.environ.get("OPENAI_TEXT_MODELS")
        os.environ["OPENAI_TEXT_MODELS"] = "model-a, model-b"
        try:
            ai_service = importlib.reload(ai_service)
            self.assertEqual(
                ai_service._model_candidates_from_env("OPENAI_TEXT_MODELS", ("default-model",)),
                ["model-a", "model-b"],
            )
        finally:
            if old_value is None:
                os.environ.pop("OPENAI_TEXT_MODELS", None)
            else:
                os.environ["OPENAI_TEXT_MODELS"] = old_value
            importlib.reload(ai_service)


if __name__ == "__main__":
    unittest.main()
