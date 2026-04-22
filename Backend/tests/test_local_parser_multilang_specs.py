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
            ("dali", {"interface": "dali"}),
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


if __name__ == "__main__":
    unittest.main()
