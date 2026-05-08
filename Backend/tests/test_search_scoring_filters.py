import os
import sqlite3
import sys
import unittest
from unittest.mock import patch

import pandas as pd


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class SearchScoringFiltersTests(unittest.TestCase):
    def _request_with_role(self, role):
        class _State:
            pass

        class _Request:
            headers = {}
            cookies = {}
            state = _State()

        req = _Request()
        req.state.current_user = {"role": role}
        return req

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

    def test_authenticated_non_admin_search_redacts_price_preview(self):
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
            resp = main_mod.search(req, self._request_with_role("user"))

        self.assertTrue(resp.exact)
        self.assertIsNone(resp.exact[0].preview.get("price"))

    def test_admin_search_keeps_price_preview(self):
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
            resp = main_mod.search(req, self._request_with_role("admin"))

        self.assertTrue(resp.exact)
        self.assertEqual(resp.exact[0].preview.get("price"), 123.45)

    def test_text_only_search_tolerates_adjacent_name_typo(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        fake_rows_df = pd.DataFrame(
            [
                {
                    "product_code": "22150313-00",
                    "product_name": "Toledo HP - UGR<lt/>19",
                    "manufacturer": "Fosnova",
                    "product_family": "Panels",
                },
                {
                    "product_code": "999",
                    "product_name": "Other Product",
                    "manufacturer": "Fosnova",
                    "product_family": "Panels",
                },
            ]
        )

        req = SearchRequest(
            text="toeldo",
            filters={},
            limit=5,
            include_similar=True,
            debug=False,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value={}), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(main_mod, "DB", fake_rows_df):
            resp = main_mod.search(req)

        self.assertIn("22150313-00", {hit.product_code for hit in resp.exact})

    def test_text_relevance_matches_compact_order_code(self):
        from app import main as main_mod

        row = {
            "product_code": "22150313-00",
            "short_product_code": "",
            "product_name": "Toledo HP - UGR<lt/>19",
        }

        self.assertGreater(main_mod._text_relevance(row, "2215031300"), 0)

    def test_code_search_similar_stays_on_anchored_product_line(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        fake_rows_df = pd.DataFrame(
            [
                {
                    "product_code": "150232-00",
                    "short_product_code": "832",
                    "product_name": "Rodi UGR<lt/>22",
                    "manufacturer": "Disano Illuminazione",
                    "product_family": "Panels",
                },
                {
                    "product_code": "150232-00412264",
                    "short_product_code": "",
                    "product_name": "Rodi IP65 - UGR<lt/>19",
                    "manufacturer": "Disano Illuminazione",
                    "product_family": "Panels",
                },
                {
                    "product_code": "170000-00",
                    "short_product_code": "",
                    "product_name": "Rodi Emergency",
                    "manufacturer": "Disano Illuminazione",
                    "product_family": "Panels",
                },
                {
                    "product_code": "164731-00",
                    "short_product_code": "",
                    "product_name": "Thema - LED",
                    "manufacturer": "Disano Illuminazione",
                    "product_family": "Waterproof",
                },
            ]
        )

        req = SearchRequest(
            text="15023200",
            filters={},
            limit=10,
            include_similar=True,
            allow_ai=False,
            debug=False,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value={}), patch.object(
            main_mod, "llm_intent_to_filters", return_value={}
        ), patch.object(main_mod, "PRODUCT_DB", None), patch.object(main_mod, "DB", fake_rows_df):
            resp = main_mod.search(req)

        similar_names = [hit.product_name for hit in resp.similar]
        self.assertIn("Rodi Emergency", similar_names)
        self.assertNotIn("Thema - LED", similar_names)

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
                {
                    "product_code": "E1",
                    "product_name": "Exact Product",
                    "manufacturer": "DISANO",
                    "diameter": "165 mm",
                    "luminaire_length": "200 mm",
                    "luminaire_width": "120 mm",
                    "luminaire_height": "80 mm",
                },
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
        self.assertEqual((resp.exact[0].preview or {}).get("diameter"), "165 mm")
        self.assertEqual((resp.exact[0].preview or {}).get("luminaire_length"), "200 mm")
        self.assertEqual((resp.exact[0].preview or {}).get("luminaire_width"), "120 mm")
        self.assertEqual((resp.exact[0].preview or {}).get("luminaire_height"), "80 mm")

    def test_search_excludes_accessories_unless_requested(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        fake_rows_df = pd.DataFrame(
            [
                {"product_code": "F1", "product_name": "Fixture", "product_family": "downlight", "manufacturer": "DISANO"},
                {"product_code": "A1", "product_name": "Accessory", "product_family": "Accessories", "manufacturer": "DISANO"},
            ]
        )
        seen_rows = []

        def capture_select(**kwargs):
            seen_rows.append([row.get("product_code") for row in kwargs.get("rows", [])])
            return [], []

        base_kwargs = dict(
            text="fixture",
            filters={},
            limit=5,
            include_similar=True,
            allow_ai=False,
            debug=False,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value={}), patch.object(
            main_mod, "PRODUCT_DB", None
        ), patch.object(main_mod, "DB", fake_rows_df), patch.object(
            main_mod, "select_exact_and_similar", side_effect=capture_select
        ):
            main_mod.search(SearchRequest(**base_kwargs))
            main_mod.search(SearchRequest(**base_kwargs, include_accessories=True))

        self.assertEqual(seen_rows[0], ["F1"])
        self.assertEqual(seen_rows[1], ["F1", "A1"])

    def test_recessed_downlight_uses_etim_as_hard_constraint(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        fake_rows_df = pd.DataFrame(
            [
                {
                    "product_code": "D1",
                    "product_name": "Recessed Downlight",
                    "product_family": "downlight",
                    "etim_search_key": "Recessed downlights",
                    "manufacturer": "DISANO",
                },
                {
                    "product_code": "D2",
                    "product_name": "Surface Downlight",
                    "product_family": "downlight",
                    "etim_search_key": "Interior floodlights",
                    "manufacturer": "DISANO",
                },
            ]
        )

        parsed_filters = {"product_family": "downlight", "etim_search_key": "recessed"}
        req = SearchRequest(
            text="downlight recessed",
            filters={},
            limit=5,
            include_similar=True,
            allow_ai=False,
            debug=True,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value=parsed_filters), patch.object(
            main_mod, "PRODUCT_DB", None
        ), patch.object(main_mod, "DB", fake_rows_df):
            resp = main_mod.search(req)

        self.assertEqual([hit.product_code for hit in resp.exact], ["D1"])
        self.assertEqual(resp.similar, [])
        self.assertEqual((resp.backend_debug_filters or {}).get("hard_filters"), parsed_filters)

    def test_text_db_search_matches_plural_accessory_poles(self):
        from app import main as main_mod

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE products (
                product_code TEXT,
                short_product_code TEXT,
                product_name TEXT,
                manufacturer TEXT,
                product_family TEXT,
                etim_search_key TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)",
            ("991906-00", "5", "Fibreglass pole", "DISANO", "Accessories", "pole"),
        )

        class FakeProductDb:
            def connect(self):
                return None

        fake_db = FakeProductDb()
        fake_db.conn = conn

        with patch.object(main_mod, "PRODUCT_DB", fake_db):
            rows = main_mod._search_rows_by_text_db("poles", limit=5)

        self.assertEqual([row.get("product_code") for row in rows], ["991906-00"])
        self.assertGreater(main_mod._text_relevance(rows[0], "poles"), 0.0)

    def test_single_token_text_search_does_not_match_inside_words(self):
        from app import main as main_mod

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE products (
                product_code TEXT,
                short_product_code TEXT,
                product_name TEXT,
                manufacturer TEXT,
                product_family TEXT,
                etim_search_key TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("S1", "1", "Street High Performance", "DISANO", "Street lighting", "Street lighting"),
                ("F1", "997", "Forma LED - transparent glass", "DISANO", "Waterproof", "Waterproof"),
            ],
        )

        class FakeProductDb:
            def connect(self):
                return None

        fake_db = FakeProductDb()
        fake_db.conn = conn

        with patch.object(main_mod, "PRODUCT_DB", fake_db):
            rows = main_mod._search_rows_by_text_db("forma", limit=5)

        self.assertEqual([row.get("product_code") for row in rows], ["F1"])
        self.assertEqual(main_mod._text_relevance({"product_name": "High Performance"}, "forma"), 0.0)

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

    def test_soft_lumen_query_seeds_database_candidates(self):
        from app import main as main_mod
        from app.schema import SearchRequest

        high_lumen = {
            "product_code": "HIGH1",
            "product_name": "High Output",
            "manufacturer": "DISANO",
            "product_family": "floodlight",
            "lumen_output": "68900 lm",
            "lumen_output_value": "68900",
        }
        low_lumen = {
            "product_code": "LOW1",
            "product_name": "Low Output",
            "manufacturer": "DISANO",
            "product_family": "floodlight",
            "lumen_output": "53000 lm",
            "lumen_output_value": "53000",
        }

        class FakeProductDb:
            backend = "sqlite"

            def search_products(self, filters, limit=100):
                if filters and filters.get("lumen_output") == ">=54000":
                    return [high_lumen]
                return [low_lumen]

        req = SearchRequest(
            text="54000 lm",
            filters={},
            limit=5,
            include_similar=True,
            allow_ai=False,
            debug=True,
        )

        with patch.object(main_mod, "local_text_to_filters", return_value={"lumen_output": ">=54000"}), patch.object(
            main_mod, "PRODUCT_DB", FakeProductDb()
        ), patch.object(main_mod, "DB", pd.DataFrame()), patch.object(
            main_mod, "_search_rows_by_text_db", return_value=[]
        ):
            resp = main_mod.search(req)

        self.assertEqual([hit.product_code for hit in resp.exact], ["HIGH1"])


if __name__ == "__main__":
    unittest.main()
