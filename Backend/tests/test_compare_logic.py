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


if __name__ == "__main__":
    unittest.main()
