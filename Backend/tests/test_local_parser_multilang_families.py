import os
import sys
import unittest


# Allow running from either repo root or Backend/ as a standalone script.
_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.local_parser import local_text_to_filters


class LocalParserMultilangFamilyTests(unittest.TestCase):
    def test_single_token_product_name_does_not_trigger_fuzzy_family(self):
        parsed = local_text_to_filters("rubin")
        self.assertNotIn("product_family", parsed, msg=f"Unexpected family inferred: {parsed}")

    def test_single_token_family_typos_are_tolerated(self):
        cases = {
            "bollrad": "bollard",
            "warehous": "highbay",
            "downligt": "downlight",
            "highbaay": "highbay",
            "waterprrof": "waterproof",
        }
        for query, expected_family in cases.items():
            parsed = local_text_to_filters(query)
            self.assertEqual(
                parsed.get("product_family"),
                expected_family,
                msg=f"Expected {expected_family!r} for typo query {query!r}, got {parsed}",
            )

    def test_vapour_word_does_not_force_waterproof_family(self):
        query = (
            "REFLECTOR VACUUM-METALLISED WITH ALUMINIUM VAPOURS "
            "WITH AN ANTI-SCRATCH PROTECTIVE LAYER. IP40"
        )
        parsed = local_text_to_filters(query)
        self.assertNotEqual(parsed.get("product_family"), "waterproof", msg=f"Unexpected family inferred: {parsed}")

    def test_ground_recessed_is_uplight(self):
        query = "48W LED fixture recessed installed in ground with IP68"
        parsed = local_text_to_filters(query)
        self.assertEqual(parsed.get("product_family"), "uplight", msg=f"Expected uplight, got: {parsed}")

    def test_recessed_alone_is_ambiguous_not_forced_to_downlight(self):
        query = "recessed fixture 48W"
        parsed = local_text_to_filters(query)
        self.assertNotEqual(parsed.get("product_family"), "downlight", msg=f"Unexpected downlight inference: {parsed}")

    def test_multilingual_application_family_inference(self):
        cases = [
            # English
            ("office lighting for classroom corridor", "linear"),
            ("facade lighting", "floodlight"),
            ("warehouse logistics hall lighting", "highbay"),
            # Italian
            ("illuminazione corridoio ospedale", "wall"),
            ("illuminazione facciata", "floodlight"),
            ("magazzino logistica capannone", "highbay"),
            # French
            ("eclairage facade", "floodlight"),
            ("couloir hopital", "wall"),
            ("entrepot logistique", "highbay"),
            # Spanish
            ("pasillo hospital", "wall"),
            ("fachada edificio", "floodlight"),
            ("almacen logistica", "highbay"),
            # Portuguese
            ("corredor hospital", "wall"),
            ("fachada arquitetonica", "floodlight"),
            ("armazem logistica", "highbay"),
            # Polish (ASCII-safe spellings also supported)
            ("korytarz szpitalny oswietlenie", "wall"),
            ("elewacja oswietlenie", "floodlight"),
            ("hala magazynowa logistyka", "highbay"),
            # Czech (ASCII-safe spellings to avoid terminal/codepage issues)
            ("skolni chodba osvetleni", "ceiling/wall"),
            ("fasada osvetleni", "floodlight"),
            ("skladovy logisticky sklad", "highbay"),
            # Croatian
            ("bolnicki hodnik rasvjeta", "wall"),
            ("fasada rasvjeta", "floodlight"),
            ("skladisna hala logisticki", "highbay"),
            # Slovenian
            ("bolnisnicni hodnik razsvetljava", "wall"),
            ("fasada razsvetljava", "floodlight"),
            ("skladiscna hala logisticni", "highbay"),
        ]

        failures = []
        for query, expected_family in cases:
            parsed = local_text_to_filters(query)
            got = parsed.get("product_family")
            if got != expected_family:
                failures.append((query, expected_family, got, parsed))

        if failures:
            lines = ["Multilingual family inference regressions:"]
            for q, exp, got, parsed in failures:
                lines.append(f"- {q!r}: expected {exp!r}, got {got!r}, parsed={parsed}")
            self.fail("\n".join(lines))

    def test_business_rule_application_queries_map_to_expected_families(self):
        cases = [
            ("office panel 600x600", "panels"),
            ("suspended linear office lighting", "linear"),
            ("garden path light", "bollard"),
            ("tree spike light", "spike"),
            ("facade projector", "floodlight"),
            ("parking garage lighting", "ceiling/wall"),
        ]

        failures = []
        for query, expected_family in cases:
            parsed = local_text_to_filters(query)
            got = parsed.get("product_family")
            if got != expected_family:
                failures.append((query, expected_family, got, parsed))

        if failures:
            lines = ["Business rule family inference regressions:"]
            for q, exp, got, parsed in failures:
                lines.append(f"- {q!r}: expected {exp!r}, got {got!r}, parsed={parsed}")
            self.fail("\n".join(lines))


if __name__ == "__main__":
    unittest.main()
