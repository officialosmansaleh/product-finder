import os
import sys
import unittest


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.local_parser import local_text_to_filters


class LocalParserMultilangSpecsTests(unittest.TestCase):
    def test_multilingual_non_family_specs(self):
        cases = [
            ("outdoor ip65 ik08", {"ip_rating": ">=IP65", "ik_rating": ">=IK08"}),
            ("esterno ip66 ik10", {"ip_rating": ">=IP66", "ik_rating": ">=IK10"}),
            ("exterieur ip65", {"ip_rating": ">=IP65"}),  # ASCII-safe French
            ("exterior ip65", {"ip_rating": ">=IP65"}),
            ("externo ip65", {"ip_rating": ">=IP65"}),
            ("наружный ip65", {"ip_rating": ">=IP65"}),
            ("خارجي ip65", {"ip_rating": ">=IP65"}),
            ("zewnetrzny ip65", {"ip_rating": ">=IP65"}),
            ("venkovni ip65", {"ip_rating": ">=IP65"}),
            ("vanjski ip65", {"ip_rating": ">=IP65"}),
            ("zunanji ip65", {"ip_rating": ">=IP65"}),
            ("ugr<19", {"ugr": "<=19"}),
            ("cri 80", {"cri": ">=80"}),
            ("ra 90", {"cri": ">=90"}),
            ("4000k", {"cct_k": "4000"}),
            ("54000 lm", {"lumen_output": ">=54000"}),
            ("54.000 lm", {"lumen_output": ">=54000"}),
            ("54,000 lm", {"lumen_output": ">=54000"}),
            ("54k lm", {"lumen_output": ">=54000"}),
            ("0-10V", {"interface": "0-10v"}),
            ("dali", {"interface": "dali"}),
            ("classe isolamento II", {"insulation_class": "Class II"}),
            ("class 2", {"insulation_class": "Class II"}),
            ("double insulation", {"insulation_class": "Class II"}),
            ("surge common mode 6kV", {"surge_common_mode": "6 kV"}),
            ("sovratensione modo comune 10 kV", {"surge_common_mode": "10 kV"}),
            ("surge 6kV", {"surge_common_mode": "6 kV"}),
            ("surge differential mode 4kV", {"surge_differential_mode": "4 kV"}),
            ("modo differenziale 8 kV", {"surge_differential_mode": "8 kV"}),
            ("warranty 5 years", {"warranty_years": ">=5"}),
            ("5 years warranty", {"warranty_years": ">=5"}),
            ("emergency", {"emergency_present": "yes"}),
            ("emergenza", {"emergency_present": "yes"}),
            ("urgence", {"emergency_present": "yes"}),
            ("emergencia", {"emergency_present": "yes"}),
            ("аварийный", {"emergency_present": "yes"}),
            ("طوارئ", {"emergency_present": "yes"}),
            ("awaryjne", {"emergency_present": "yes"}),
            ("nouzove", {"emergency_present": "yes"}),
            ("hitna", {"emergency_present": "yes"}),
            ("nujna", {"emergency_present": "yes"}),
            ("asymmetric", {"asymmetry": "asymmetric"}),
            ("asimmetrico", {"asymmetry": "asymmetric"}),
            ("asymetrique", {"asymmetry": "asymmetric"}),
            ("asimetrico", {"asymmetry": "asymmetric"}),
            ("assimetrico", {"asymmetry": "asymmetric"}),
            ("асимметричный", {"asymmetry": "asymmetric"}),
            ("غير متماثل", {"asymmetry": "asymmetric"}),
            ("asymetryczny", {"asymmetry": "asymmetric"}),
            ("asymetricky", {"asymmetry": "asymmetric"}),
            ("asimetričan", {"asymmetry": "asymmetric"}),
            ("asimetrican", {"asymmetry": "asymmetric"}),
            ("asimetricen", {"asymmetry": "asymmetric"}),
            ("round panel", {"shape": "round"}),
            ("quadrato", {"shape": "square"}),
            ("rectangulaire", {"shape": "rectangular"}),
            ("cuadrado", {"shape": "square"}),
            ("круглый", {"shape": "round"}),
            ("مربع", {"shape": "square"}),
            ("prostokatny", {"shape": "rectangular"}),
            ("ctvercovy", {"shape": "square"}),
            ("pravokutan", {"shape": "rectangular"}),
            ("kvadraten", {"shape": "square"}),
        ]

        failures = []
        for query, expected_subset in cases:
            parsed = local_text_to_filters(query)
            for k, expected_v in expected_subset.items():
                got = parsed.get(k)
                if got != expected_v:
                    failures.append((query, k, expected_v, got, parsed))

        if failures:
            lines = ["Multilingual non-family spec regressions:"]
            for q, k, exp, got, parsed in failures:
                lines.append(f"- {q!r} key={k!r}: expected {exp!r}, got {got!r}, parsed={parsed}")
            self.fail("\n".join(lines))

    def test_technical_warranty_words_are_not_product_name_filters(self):
        parsed = local_text_to_filters("road lighting with warranty 5 years lifetime 50000 h round shape")
        self.assertEqual(parsed.get("warranty_years"), ">=5")
        self.assertEqual(parsed.get("lifetime_hours"), ">=50000")
        self.assertNotIn("product_name_contains", parsed)
        self.assertNotIn("product_name_short", parsed)

    def test_outdoor_lumen_query_does_not_create_product_name_filter(self):
        parsed = local_text_to_filters("faro esterno IP66 DALI 4000K 54000 lumen")
        self.assertNotIn("product_family", parsed)
        self.assertEqual(parsed.get("ip_rating"), ">=IP66")
        self.assertEqual(parsed.get("interface"), "dali")
        self.assertEqual(parsed.get("cct_k"), "4000")
        self.assertEqual(parsed.get("lumen_output"), ">=54000")
        self.assertEqual(parsed.get("product_name_contains"), "faro")

    def test_efficacy_word_is_not_product_name_filter(self):
        parsed = local_text_to_filters("efficienza > 100lm/w")
        self.assertEqual(parsed.get("efficacy_lm_w"), ">100")
        self.assertNotIn("product_name_contains", parsed)
        self.assertNotIn("product_name_short", parsed)

    def test_lifetime_exact_and_range_queries(self):
        self.assertEqual(local_text_to_filters("9000 hr").get("lifetime_hours"), ">=9000")
        self.assertEqual(local_text_to_filters("=9000 hr").get("lifetime_hours"), "=9000")
        self.assertEqual(local_text_to_filters("==9000 hr").get("lifetime_hours"), "=9000")
        self.assertEqual(local_text_to_filters("8000<hr<10000").get("lifetime_hours"), "8000-10000")
        self.assertEqual(local_text_to_filters("8000-10000 hr").get("lifetime_hours"), "8000-10000")

    def test_ambient_temperature_capability_directions(self):
        parsed = local_text_to_filters("-20C to 50C")
        self.assertEqual(parsed.get("ambient_temp_min_c"), "<=-20")
        self.assertEqual(parsed.get("ambient_temp_max_c"), ">=50")

        parsed = local_text_to_filters("temp max 45C")
        self.assertEqual(parsed.get("ambient_temp_max_c"), ">=45")


if __name__ == "__main__":
    unittest.main()
