import os
import sys
import unittest
from unittest.mock import patch

import pandas as pd


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class SearchScoringFiltersTests(unittest.TestCase):
    def test_all_active_filters_are_passed_into_scoring(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        parsed_filters = {
            "product_family": "uplight",
            "ip_rating": ">=IP68",
            "ik_rating": ">=IK10",
            "interface": "dmx",
            "cri": ">=80",
            "power_max_w": "<=48",
        }
        user_filters = {
            "manufacturer": "disano",
            "shape": "round",
        }
        expected_filters = {**parsed_filters, **user_filters}

        fake_rows_df = pd.DataFrame(
            [
                {
                    "product_code": "X1",
                    "product_name": "Test Product",
                    "manufacturer": "DISANO",
                }
            ]
        )

        calls = []

        def fake_score_product(_row, hard, soft):
            calls.append((dict(hard or {}), dict(soft or {})))
            return 1.0, {}, [], []

        req = SearchRequest(
            text="dummy query",
            filters=user_filters,
            limit=5,
            include_similar=True,
            debug=False,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value=parsed_filters), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(main_mod, "DB", fake_rows_df), patch.object(
            main_mod, "score_product", side_effect=fake_score_product
        ):
            _ = main_mod.search(req)

        self.assertGreaterEqual(len(calls), 2, msg=f"Expected scoring calls, got: {calls}")
        exact_calls = [c for c in calls if c[0] and not c[1]]
        similar_calls = [c for c in calls if not c[0] and c[1]]
        self.assertTrue(exact_calls, msg=f"No exact scoring call captured: {calls}")
        self.assertTrue(similar_calls, msg=f"No similar scoring call captured: {calls}")

        self.assertEqual(exact_calls[0][0], {**user_filters, "product_family": "uplight"})
        self.assertEqual(similar_calls[0][1], expected_filters)

    def test_generic_ai_family_query_stays_soft_without_user_family_filter(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        parsed_filters = {
            "product_family": "floodlight",
        }

        fake_rows_df = pd.DataFrame(
            [
                {
                    "product_code": "X1",
                    "product_name": "Flood Sample",
                    "manufacturer": "DISANO",
                    "product_family": "post top",
                }
            ]
        )

        calls = []

        def fake_score_product(_row, hard, soft):
            calls.append((dict(hard or {}), dict(soft or {})))
            return 1.0, {}, [], []

        req = SearchRequest(
            text="floodlight",
            filters={},
            limit=5,
            include_similar=True,
            debug=False,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value=parsed_filters), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(main_mod, "DB", fake_rows_df), patch.object(
            main_mod, "score_product", side_effect=fake_score_product
        ):
            _ = main_mod.search(req)

        self.assertGreaterEqual(len(calls), 2, msg=f"Expected scoring calls, got: {calls}")
        exact_calls = [c for c in calls if c[0] and not c[1]]
        similar_calls = [c for c in calls if not c[0] and c[1]]

        self.assertFalse(exact_calls, msg=f"Generic family-only query should not become a hard filter: {calls}")
        self.assertTrue(similar_calls, msg=f"Expected similar scoring call, got: {calls}")
        self.assertEqual(similar_calls[0][1], {"product_family": "floodlight"})

    def test_user_selected_family_filter_remains_hard(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        parsed_filters = {
            "product_family": "floodlight",
        }

        fake_rows_df = pd.DataFrame(
            [
                {
                    "product_code": "X1",
                    "product_name": "Flood Sample",
                    "manufacturer": "DISANO",
                    "product_family": "floodlight",
                }
            ]
        )

        calls = []

        def fake_score_product(_row, hard, soft):
            calls.append((dict(hard or {}), dict(soft or {})))
            return 1.0, {}, [], []

        req = SearchRequest(
            text="floodlight",
            filters={"product_family": "floodlight"},
            limit=5,
            include_similar=True,
            debug=False,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value=parsed_filters), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(main_mod, "DB", fake_rows_df), patch.object(
            main_mod, "score_product", side_effect=fake_score_product
        ):
            _ = main_mod.search(req)

        exact_calls = [c for c in calls if c[0] and not c[1]]
        similar_calls = [c for c in calls if not c[0] and c[1]]

        self.assertTrue(exact_calls, msg=f"User family filter must remain hard: {calls}")
        self.assertEqual(exact_calls[0][0], {"product_family": "floodlight"})
        self.assertTrue(similar_calls, msg=f"Expected similar scoring call, got: {calls}")
        self.assertEqual(similar_calls[0][1], {"product_family": "floodlight"})

    def test_manual_filters_remain_on_off_for_similar_results(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        fake_rows_df = pd.DataFrame(
            [
                {"product_code": "A1", "product_name": "Inside filter", "manufacturer": "DISANO", "shape": "round"},
                {"product_code": "B1", "product_name": "Outside filter", "manufacturer": "DISANO", "shape": "square"},
            ]
        )

        req = SearchRequest(
            text="office light",
            filters={"shape": "round"},
            limit=10,
            include_similar=True,
            debug=False,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value={}), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(main_mod, "DB", fake_rows_df):
            resp = main_mod.search(req)

        exact_codes = {hit.product_code for hit in resp.exact}
        similar_codes = {hit.product_code for hit in resp.similar}
        self.assertIn("A1", exact_codes | similar_codes)
        self.assertNotIn("B1", exact_codes | similar_codes)

    def test_empty_search_without_filters_returns_no_results(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        req = SearchRequest(
            text="",
            filters={},
            limit=5,
            include_similar=True,
            debug=False,
        )

        with patch.object(main_mod, "score_product") as score_mock:
            resp = main_mod.search(req)

        self.assertEqual(resp.exact, [])
        self.assertEqual(resp.similar, [])
        self.assertEqual((resp.interpreted or {}).get("empty_search"), True)
        score_mock.assert_not_called()

    def test_public_search_redacts_price_preview(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        fake_rows_df = pd.DataFrame(
            [
                {
                    "product_code": "X1",
                    "product_name": "Street Sample",
                    "manufacturer": "DISANO",
                    "product_family": "Street lighting",
                    "price": 123.45,
                }
            ]
        )

        req = SearchRequest(
            text="street",
            filters={},
            limit=5,
            include_similar=True,
            debug=False,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value={}), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(main_mod, "DB", fake_rows_df):
            resp = main_mod.search(req)

        self.assertTrue(resp.exact)
        self.assertIsNone(resp.exact[0].preview.get("price"))

    def test_search_limit_is_capped_to_100(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        req = SearchRequest(
            text="street",
            filters={},
            limit=5000,
            include_similar=True,
            debug=False,
        )

        captured_limits = []

        def fake_select_exact_and_similar(**kwargs):
            captured_limits.append(kwargs.get("limit"))
            return [], []

        with patch.object(main_mod, "local_text_to_filters", return_value={}), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(
            main_mod, "DB", pd.DataFrame([{"product_code": "X1", "product_name": "Sample"}])
        ), patch.object(main_mod, "select_exact_and_similar", side_effect=fake_select_exact_and_similar):
            _ = main_mod.search(req)

        self.assertEqual(captured_limits, [100])

    def test_similar_results_are_capped_to_limit(self):
        from app.ranking import select_exact_and_similar

        similar_pool = []
        for idx in range(250):
            similar_pool.append(
                {
                    "row": {"product_code": f"P{idx:04d}"},
                    "score": 0.8,
                    "text_relevance": 0.7,
                    "matched": {},
                    "deviations": [],
                    "missing": [],
                }
            )

        exact, similar = select_exact_and_similar(
            exact_pool=[],
            similar_pool=similar_pool,
            rows=[],
            text_query="street",
            hard_filters={},
            soft_filters={},
            limit=100,
            include_similar=True,
            text_relevance_fn=lambda _row, _text: 0.0,
        )

        self.assertEqual(exact, [])
        self.assertEqual(len(similar), 100)

    def test_search_reports_result_tiers_from_ranked_hits(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        fake_rows_df = pd.DataFrame(
            [
                {"product_code": "E1", "product_name": "Exact Product", "manufacturer": "DISANO"},
                {"product_code": "C1", "product_name": "Close Product", "manufacturer": "DISANO"},
                {"product_code": "B1", "product_name": "Broader Product", "manufacturer": "DISANO"},
            ]
        )

        req = SearchRequest(
            text="office downlight",
            filters={},
            limit=5,
            include_similar=True,
            debug=False,
        )

        ranked_exact = [
            {
                "row": fake_rows_df.iloc[0].to_dict(),
                "score": 0.98,
                "text_relevance": 0.9,
                "matched": {},
                "deviations": [],
                "missing": [],
                "match_tier": "exact",
            }
        ]
        ranked_similar = [
            {
                "row": fake_rows_df.iloc[1].to_dict(),
                "score": 0.81,
                "text_relevance": 0.7,
                "matched": {},
                "deviations": [],
                "missing": [],
                "match_tier": "close",
            },
            {
                "row": fake_rows_df.iloc[2].to_dict(),
                "score": 0.66,
                "text_relevance": 0.4,
                "matched": {},
                "deviations": ["fallback: strict constraints relaxed"],
                "missing": [],
                "match_tier": "broader",
            },
        ]

        with patch.object(main_mod, "local_text_to_filters", return_value={}), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(
            main_mod, "DB", fake_rows_df
        ), patch.object(
            main_mod, "select_exact_and_similar", return_value=(ranked_exact, ranked_similar)
        ):
            resp = main_mod.search(req)

        self.assertEqual((resp.interpreted or {}).get("result_tiers"), {"exact": 1, "close": 1, "broader": 1})

    def test_search_reports_user_friendly_recovery_actions(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        fake_rows_df = pd.DataFrame(
            [
                {
                    "product_code": "X1",
                    "product_name": "Strict Match",
                    "manufacturer": "DISANO",
                }
            ]
        )

        parsed_filters = {
            "ip_rating": "IP66",
            "ik_rating": "IK08",
            "ugr": "<19",
            "power_max_w": "<=40",
        }
        user_filters = {"manufacturer": "DISANO"}

        req = SearchRequest(
            text="outdoor street lighting",
            filters=user_filters,
            limit=5,
            include_similar=True,
            debug=False,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value=parsed_filters), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(main_mod, "DB", fake_rows_df), patch.object(
            main_mod, "select_exact_and_similar", return_value=([], [])
        ):
            resp = main_mod.search(req)

        actions = (resp.interpreted or {}).get("recovery_actions") or []
        self.assertEqual(
            [action.get("id") for action in actions],
            ["relax_ugr", "relax_ip", "relax_ik", "widen_power"],
        )
        self.assertTrue(all(str(action.get("label") or "").strip() for action in actions))

    def test_product_name_short_hard_filter_matches_prefix_exactly(self):
        from app.scoring import score_product

        product = {
            "product_code": "R1",
            "product_name": "Rodi 100 LED",
        }

        for filter_key in ("product_name_short", "name_prefix"):
            score, matched, deviations, missing = score_product(product, {filter_key: "rodi"}, {})
            self.assertEqual(score, 1.0, msg=f"{filter_key} should match product_name prefix")
            self.assertEqual(matched.get(filter_key), "Rodi 100 LED")
            self.assertEqual(deviations, [])
            self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
