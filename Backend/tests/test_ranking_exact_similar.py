import os
import sys
import unittest


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.ranking import select_exact_and_similar


def _mk_row(code: str):
    return {"product_code": code, "product_name": code}


def _mk_scored(code: str, score: float, rel: float, deviations=None, missing=None):
    return {
        "row": _mk_row(code),
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


if __name__ == "__main__":
    unittest.main()
