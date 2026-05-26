import os
import sys
import unittest


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.ranking import select_exact_and_similar


def _mk_row(code: str, name: str | None = None):
    return {"product_code": code, "product_name": name or code}


def _mk_scored(code: str, score: float, rel: float, deviations=None, missing=None, name: str | None = None):
    return {
        "row": _mk_row(code, name),
        "score": score,
        "text_relevance": rel,
        "matched": {},
        "deviations": deviations or [],
        "missing": missing or [],
    }


class RankingSelectionTests(unittest.TestCase):
    def test_text_only_query_keeps_only_text_hits_in_exact(self):
        exact_pool = [
            _mk_scored("A", 1.0, 1.0),
            _mk_scored("B", 1.0, 0.0),
        ]
        similar_pool = []
        rows = [_mk_row("A"), _mk_row("B")]

        exact, similar = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=similar_pool,
            rows=rows,
            text_query="giovi",
            hard_filters={},
            soft_filters={},
            limit=20,
            include_similar=True,
            text_relevance_fn=lambda _row, _q: 0.0,
        )
        exact_codes = [x["row"]["product_code"] for x in exact]
        self.assertEqual(exact_codes, ["A"])
        self.assertTrue(any(x["row"]["product_code"] == "B" for x in similar))

    def test_with_filters_exact_can_include_non_text_hit(self):
        exact_pool = [
            _mk_scored("A", 1.0, 0.0),
        ]
        exact, _ = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=[],
            rows=[_mk_row("A")],
            text_query="giovi",
            hard_filters={"product_family": "downlight"},
            soft_filters={},
            limit=20,
            include_similar=False,
            text_relevance_fn=lambda _row, _q: 0.0,
        )
        self.assertEqual([x["row"]["product_code"] for x in exact], ["A"])

    def test_below_hundred_percent_moves_to_similar(self):
        exact_pool = [
            _mk_scored("A", 0.88, 0.9),
        ]
        exact, similar = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=[],
            rows=[_mk_row("A")],
            text_query="office",
            hard_filters={"shape": "round"},
            soft_filters={"product_family": "panel"},
            limit=20,
            include_similar=True,
            text_relevance_fn=lambda _row, _q: 0.9,
        )
        self.assertEqual(exact, [])
        self.assertEqual([x["row"]["product_code"] for x in similar], ["A"])
        self.assertEqual(similar[0]["match_tier"], "close")

    def test_similar_fallback_populates_when_empty(self):
        rows = [_mk_row("A"), _mk_row("B")]
        exact, similar = select_exact_and_similar(
            exact_pool=[],
            similar_pool=[],
            rows=rows,
            text_query="",
            hard_filters={},
            soft_filters={},
            limit=20,
            include_similar=True,
            text_relevance_fn=lambda _row, _q: 0.0,
        )
        self.assertEqual(exact, [])
        self.assertGreaterEqual(len(similar), 1)
        self.assertIn("fallback: strict constraints relaxed", similar[0]["deviations"])
        self.assertEqual(similar[0]["match_tier"], "broader")

    def test_text_mismatch_promotion_is_marked_broader(self):
        exact_pool = [
            _mk_scored("A", 1.0, 0.0),
        ]
        exact, similar = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=[],
            rows=[_mk_row("A")],
            text_query="street",
            hard_filters={},
            soft_filters={},
            limit=20,
            include_similar=True,
            text_relevance_fn=lambda _row, _q: 0.0,
        )
        self.assertEqual(exact, [])
        self.assertTrue(similar)
        self.assertEqual(similar[0]["match_tier"], "broader")

    def test_family_only_query_diversifies_exact_product_lines(self):
        exact_pool = [
            _mk_scored("999", 1.0, 0.0, name="Rodio HE asymmetric"),
            _mk_scored("998", 1.0, 0.0, name="Rodio HE wide beam"),
            _mk_scored("997", 1.0, 0.0, name="Rodio LED asymmetric"),
            _mk_scored("100", 1.0, 0.0, name="Astro HP"),
            _mk_scored("090", 1.0, 0.0, name="Sevilla 1"),
        ]
        exact, _ = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=[],
            rows=[],
            text_query="floodlights",
            hard_filters={},
            soft_filters={"product_family": "floodlight"},
            limit=3,
            include_similar=False,
            text_relevance_fn=lambda _row, _q: 0.0,
        )
        self.assertEqual(
            [x["row"]["product_name"].split()[0] for x in exact],
            ["Rodio", "Astro", "Sevilla"],
        )

    def test_family_only_query_drops_text_relevant_wrong_family_from_similar(self):
        exact_pool = [
            {**_mk_scored("D1", 1.0, 0.4, name="Recessed downlight"), "row": {"product_code": "D1", "product_name": "Recessed downlight", "product_family": "downlight"}},
        ]
        similar_pool = [
            {**_mk_scored("P1", 0.0, 0.4, name="Recessed panel"), "row": {"product_code": "P1", "product_name": "Recessed panel", "product_family": "Panels"}},
        ]
        exact, similar = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=similar_pool,
            rows=[],
            text_query="downlight recessed",
            hard_filters={},
            soft_filters={"product_family": "downlight"},
            limit=5,
            include_similar=True,
            text_relevance_fn=lambda _row, _q: 0.0,
        )

        self.assertEqual([x["row"]["product_code"] for x in exact], ["D1"])
        self.assertEqual(similar, [])

    def test_power_sort_applies_before_limit(self):
        exact_pool = [
            {**_mk_scored("A", 1.0, 0.0), "row": {"product_code": "A", "product_name": "A", "power_max_w": "100 W"}},
            {**_mk_scored("B", 1.0, 0.0), "row": {"product_code": "B", "product_name": "B", "power_max_w": "5 W"}},
            {**_mk_scored("C", 1.0, 0.0), "row": {"product_code": "C", "product_name": "C", "power_max_w": "20 W"}},
        ]
        exact, _ = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=[],
            rows=[],
            text_query="floodlights",
            hard_filters={},
            soft_filters={"product_family": "floodlight"},
            limit=1,
            include_similar=False,
            text_relevance_fn=lambda _row, _q: 0.0,
            sort_mode="power_asc",
        )
        self.assertEqual([x["row"]["product_code"] for x in exact], ["B"])

    def test_lumen_sort_applies_before_limit(self):
        exact_pool = [
            {**_mk_scored("A", 1.0, 0.0), "row": {"product_code": "A", "product_name": "A", "lumen_output": "54000 lm"}},
            {**_mk_scored("B", 1.0, 0.0), "row": {"product_code": "B", "product_name": "B", "lumen_output": "12000 lm"}},
            {**_mk_scored("C", 1.0, 0.0), "row": {"product_code": "C", "product_name": "C", "lumen_output": "30000 lm"}},
        ]
        exact, _ = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=[],
            rows=[],
            text_query="floodlights",
            hard_filters={},
            soft_filters={"product_family": "floodlight"},
            limit=1,
            include_similar=False,
            text_relevance_fn=lambda _row, _q: 0.0,
            sort_mode="lumen_asc",
        )
        self.assertEqual([x["row"]["product_code"] for x in exact], ["B"])

    def test_default_ranking_prefers_power_closest_to_requested_ceiling(self):
        exact_pool = [
            {**_mk_scored("A", 1.0, 0.0), "row": {"product_code": "A", "product_name": "Rodio", "power_max_w": "40 W"}},
            {**_mk_scored("B", 1.0, 0.0), "row": {"product_code": "B", "product_name": "Rodio", "power_max_w": "98 W"}},
            {**_mk_scored("C", 1.0, 0.0), "row": {"product_code": "C", "product_name": "Rodio", "power_max_w": "75 W"}},
        ]
        exact, _ = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=[],
            rows=[],
            text_query="rodio 100w",
            hard_filters={},
            soft_filters={"power_max_w": "<=100"},
            limit=20,
            include_similar=True,
            text_relevance_fn=lambda _row, _q: 0.0,
        )
        self.assertEqual([x["row"]["product_code"] for x in exact], ["B", "C", "A"])

    def test_default_ranking_prefers_lumen_closest_to_requested_minimum(self):
        exact_pool = [
            {**_mk_scored("A", 1.0, 0.0), "row": {"product_code": "A", "product_name": "Rodio", "lumen_output": "9000 lm"}},
            {**_mk_scored("B", 1.0, 0.0), "row": {"product_code": "B", "product_name": "Rodio", "lumen_output": "5200 lm"}},
            {**_mk_scored("C", 1.0, 0.0), "row": {"product_code": "C", "product_name": "Rodio", "lumen_output": "6500 lm"}},
        ]
        exact, _ = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=[],
            rows=[],
            text_query="rodio 5000 lm",
            hard_filters={},
            soft_filters={"lumen_output": ">=5000"},
            limit=20,
            include_similar=True,
            text_relevance_fn=lambda _row, _q: 0.0,
        )
        self.assertEqual([x["row"]["product_code"] for x in exact], ["B", "C", "A"])

    def test_name_match_outranks_photometric_only_match_in_similar(self):
        similar_pool = [
            {
                **_mk_scored("LUMEN", 0.95, 0.0, name="Other High Output"),
                "matched": {"lumen_output": "54000 lm", "ip_rating": "IP66"},
                "row": {"product_code": "LUMEN", "product_name": "Other High Output", "lumen_output": "54000 lm", "ip_rating": "IP66"},
            },
            {
                **_mk_scored("FARO", 0.62, 0.1, name="Faro 200"),
                "matched": {"product_name_contains": "Faro 200", "ip_rating": "IP66"},
                "row": {"product_code": "FARO", "product_name": "Faro 200", "lumen_output": "30000 lm", "ip_rating": "IP66"},
            },
        ]
        _exact, similar = select_exact_and_similar(
            exact_pool=[],
            similar_pool=similar_pool,
            rows=[],
            text_query="faro esterno IP66 54000 lumen",
            hard_filters={},
            soft_filters={"product_name_contains": "faro", "ip_rating": ">=IP66", "lumen_output": ">=54000"},
            limit=20,
            include_similar=True,
            text_relevance_fn=lambda _row, _q: 0.0,
        )
        self.assertEqual([x["row"]["product_code"] for x in similar], ["FARO", "LUMEN"])

    def test_default_ranking_prefers_efficacy_closest_to_requested_minimum(self):
        exact_pool = [
            {**_mk_scored("A", 1.0, 0.0), "row": {"product_code": "A", "product_name": "Rodio", "efficacy_lm_w": "180 lm/W"}},
            {**_mk_scored("B", 1.0, 0.0), "row": {"product_code": "B", "product_name": "Rodio", "efficacy_lm_w": "122 lm/W"}},
            {**_mk_scored("C", 1.0, 0.0), "row": {"product_code": "C", "product_name": "Rodio", "efficacy_lm_w": "145 lm/W"}},
        ]
        exact, _ = select_exact_and_similar(
            exact_pool=exact_pool,
            similar_pool=[],
            rows=[],
            text_query="rodio 120 lm/w",
            hard_filters={},
            soft_filters={"efficacy_lm_w": ">=120"},
            limit=20,
            include_similar=True,
            text_relevance_fn=lambda _row, _q: 0.0,
        )
        self.assertEqual([x["row"]["product_code"] for x in exact], ["B", "C", "A"])


if __name__ == "__main__":
    unittest.main()
