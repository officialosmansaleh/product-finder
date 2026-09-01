import json
import math
import os
import sys
import unittest


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class CompareLogicTests(unittest.TestCase):
    def test_compare_products_response_is_json_safe_with_nan_values(self):
        from app.compare_logic import handle_compare_products

        class Req:
            codes = ["15023200", "150232-00412264"]

        rows = {
            "15023200": {
                "product_code": "150232-00",
                "product_name": "Rodi UGR<lt/>22",
                "manufacturer": "Disano Illuminazione",
                "beam_angle_deg": math.nan,
                "lumen_maintenance_pct": 90.0,
            },
            "150232-00412264": {
                "product_code": "150232-00412264",
                "product_name": "Rodi IP65 - UGR<lt/>19",
                "manufacturer": "Disano Illuminazione",
                "beam_angle_deg": math.nan,
                "lumen_maintenance_pct": 90.0,
            },
        }

        payload = handle_compare_products(
            Req(),
            find_product_by_code_any=lambda code: rows.get(code),
            manufacturer_label=lambda value: str(value or ""),
            build_website_url=lambda code, manufacturer: f"https://example.test/{code}",
            build_datasheet_url=lambda code, manufacturer: f"https://example.test/{code}.pdf",
            collect_compare_fields=lambda compare_rows, include_empty=False, reference_only=True: [
                "product_name",
                "beam_angle_deg",
                "lumen_maintenance_pct",
            ],
            cmp_norm_value=lambda value: "" if value is None else str(value).strip().lower(),
            quote_plus=lambda value: value,
        )

        self.assertIsNone(payload["items"][0]["beam_angle_deg"])
        json.dumps(payload, allow_nan=False)

    def test_alternatives_response_is_json_safe_with_nan_values(self):
        from app.alternatives_logic import handle_alternatives

        class Req:
            code = "326966-00"
            limit = 1
            min_score = None

        base = {
            "product_code": "326966-00",
            "product_name": "Base",
            "manufacturer": "Disano Illuminazione",
            "product_family": "Accessories",
            "beam_angle_deg": math.nan,
            "price": math.nan,
        }
        candidate = {
            "product_code": "326967-00",
            "product_name": math.nan,
            "manufacturer": "Disano Illuminazione",
            "product_family": "Accessories",
            "price": math.nan,
        }

        payload = handle_alternatives(
            Req(),
            find_product_by_code_any=lambda _code: base,
            cfg_int=lambda _key, default: default,
            product_db=None,
            db_dataframe=None,
            row_to_public_dict=lambda row: dict(row),
            alt_similarity=lambda _base, _candidate: 0.8,
            manufacturer_label=lambda value: str(value or ""),
            build_website_url=lambda code, manufacturer: f"https://example.test/{code}",
            build_datasheet_url=lambda code, manufacturer: f"https://example.test/{code}.pdf",
            quote_plus=lambda value: value,
            include_price=True,
        )
        self.assertIsNone(payload["base"]["beam_angle_deg"])
        self.assertIsNone(payload["base"]["price"])
        json.dumps(payload, allow_nan=False)

        class FakeConn:
            def execute(self, *_args):
                return self

            def fetchall(self):
                return [candidate]

        class FakeDb:
            conn = FakeConn()

        payload = handle_alternatives(
            Req(),
            find_product_by_code_any=lambda _code: base,
            cfg_int=lambda _key, default: default,
            product_db=FakeDb(),
            db_dataframe=None,
            row_to_public_dict=lambda row: dict(row),
            alt_similarity=lambda _base, _candidate: 0.8,
            manufacturer_label=lambda value: str(value or ""),
            build_website_url=lambda code, manufacturer: f"https://example.test/{code}",
            build_datasheet_url=lambda code, manufacturer: f"https://example.test/{code}.pdf",
            quote_plus=lambda value: value,
            include_price=True,
        )
        self.assertIsNone(payload["alternatives"][0]["product_name"])
        self.assertIsNone(payload["alternatives"][0]["price"])
        json.dumps(payload, allow_nan=False)

    def test_alternatives_from_spec_response_is_json_safe_with_nan_values(self):
        from app.alternatives_logic import handle_alternatives_from_spec

        class Req:
            ideal_spec = {"product_family": "Accessories"}
            limit = 1
            sort = "score_desc"
            min_score = None

        candidate = {
            "product_code": "326967-00",
            "product_name": math.nan,
            "manufacturer": "Disano Illuminazione",
            "product_family": "Accessories",
            "price": math.nan,
        }

        class FakeDb:
            conn = object()

            def search_products(self, *_args, **_kwargs):
                return [candidate]

        payload = handle_alternatives_from_spec(
            Req(),
            sanitize_filters=lambda filters: dict(filters),
            normalize_ui_filters=lambda filters: dict(filters),
            cfg_int=lambda _key, default: default,
            map_filters_to_sql=lambda filters: dict(filters),
            product_db=FakeDb(),
            db_dataframe=None,
            row_to_public_dict=lambda row: dict(row),
            score_product=lambda _candidate, _hard, _soft: (0.7, {}, {}, []),
            manufacturer_label=lambda value: str(value or ""),
            build_website_url=lambda code, manufacturer: f"https://example.test/{code}",
            build_datasheet_url=lambda code, manufacturer: f"https://example.test/{code}.pdf",
            quote_plus=lambda value: value,
            to_num=lambda value: value if isinstance(value, (int, float)) else None,
            include_price=True,
        )

        self.assertIsNone(payload["alternatives"][0]["product_name"])
        self.assertIsNone(payload["alternatives"][0]["price"])
        json.dumps(payload, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
