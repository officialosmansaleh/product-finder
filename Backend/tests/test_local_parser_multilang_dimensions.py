import os
import sys
import unittest


# Allow running from either repo root or Backend/ as a standalone script.
_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.local_parser import local_text_to_filters


class LocalParserMultilangDimensionTests(unittest.TestCase):
    def test_multilingual_dimension_and_comparator_parsing(self):
        cases = [
            # diameter
            ("diameter <=220 mm", {"diameter": "<=220"}),
            ("diametro massimo 220", {"diameter": "<=220"}),
            ("diametre 180", {"diameter": ">=180"}),
            ("diametro 180", {"diameter": ">=180"}),
            ("diametro 180 mm", {"diameter": ">=180"}),
            ("diametro min 120", {"diameter": ">=120"}),
            ("diâmetro máximo 150", {"diameter": "<=150"}),
            ("диаметр 180", {"diameter": ">=180"}),
            ("قطر 180", {"diameter": ">=180"}),
            ("średnica 180", {"diameter": ">=180"}),
            ("prumer 180", {"diameter": ">=180"}),   # Czech ASCII-safe
            ("promjer 180", {"diameter": ">=180"}),  # Croatian
            ("premer 180", {"diameter": ">=180"}),   # Slovenian
            # length / width / height aliases
            ("length >=1200 mm", {"luminaire_length": ">=1200"}),
            ("lunghezza 1200", {"luminaire_length": ">=1200"}),
            ("longueur max 1500", {"luminaire_length": "<=1500"}),
            ("largo 600", {"luminaire_length": ">=600"}),  # Spanish
            ("comprimento minimo 900", {"luminaire_length": ">=900"}),  # Portuguese
            ("длина 1200", {"luminaire_length": ">=1200"}),
            ("طول 1200", {"luminaire_length": ">=1200"}),
            ("dlugosc 1200", {"luminaire_length": ">=1200"}),  # Polish ASCII-safe
            ("delka 1200", {"luminaire_length": ">=1200"}),    # Czech ASCII-safe
            ("duzina 1200", {"luminaire_length": ">=1200"}),   # Croatian ASCII-safe
            ("dolzina 1200", {"luminaire_length": ">=1200"}),  # Slovenian ASCII-safe
            ("width <=300", {"luminaire_width": "<=300"}),
            ("larghezza 300", {"luminaire_width": ">=300"}),
            ("largeur max 300", {"luminaire_width": "<=300"}),
            ("ancho 300", {"luminaire_width": ">=300"}),
            ("largura 300", {"luminaire_width": ">=300"}),
            ("ширина 300", {"luminaire_width": ">=300"}),
            ("عرض 300", {"luminaire_width": ">=300"}),
            ("szerokosc 300", {"luminaire_width": ">=300"}),  # Polish ASCII-safe
            ("sirka 300", {"luminaire_width": ">=300"}),      # Czech/Croatian ASCII-safe
            ("height max 120", {"luminaire_height": "<=120"}),
            ("altezza minimo 80", {"luminaire_height": ">=80"}),
            ("hauteur <=120", {"luminaire_height": "<=120"}),
            ("altura 120", {"luminaire_height": ">=120"}),  # ES/PT shared
            ("высота 120", {"luminaire_height": ">=120"}),
            ("ارتفاع 120", {"luminaire_height": ">=120"}),
            ("wysokosc 120", {"luminaire_height": ">=120"}),  # Polish ASCII-safe
            ("vyska 120", {"luminaire_height": ">=120"}),     # Czech ASCII-safe
            ("visina 120", {"luminaire_height": ">=120"}),    # HR/SL
            ("globina 120", {"luminaire_height": ">=120"}),   # Slovenian depth alias
            # comparator phrases (language normalization) + dimensions
            ("diameter at least 200", {"diameter": ">=200"}),
            ("diametro almeno 200", {"diameter": ">=200"}),
            ("diametre au moins 200", {"diameter": ">=200"}),
            ("diametro al menos 200", {"diameter": ">=200"}),
            ("diametro pelo menos 200", {"diameter": ">=200"}),
            ("диаметр не менее 200", {"diameter": ">=200"}),
            ("قطر على الأقل 200", {"diameter": ">=200"}),
            ("średnica co najmniej 200", {"diameter": ">=200"}),
            ("prumer alespon 200", {"diameter": ">=200"}),
            ("promjer najmanje 200", {"diameter": ">=200"}),
            ("premer vsaj 200", {"diameter": ">=200"}),
            ("diameter at most 220", {"diameter": "<=220"}),
            ("diametro massimo 220", {"diameter": "<=220"}),
            ("diametre au plus 220", {"diameter": "<=220"}),
            ("diametro como maximo 220", {"diameter": "<=220"}),
            ("diametro no maximo 220", {"diameter": "<=220"}),
            ("диаметр не более 220", {"diameter": "<=220"}),
            ("قطر على الأكثر 220", {"diameter": "<=220"}),
            ("średnica maksymalnie 220", {"diameter": "<=220"}),
            ("prumer nejvyse 220", {"diameter": "<=220"}),
            ("promjer najvise 220", {"diameter": "<=220"}),
            ("premer najvec 220", {"diameter": "<=220"}),
            # ensure IP number is not misread as diameter
            ("proyector exterior al menos ip65 diametro 180", {"diameter": ">=180", "ip_rating": ">=IP65"}),
            ("floodlight IP65 diameter 180", {"diameter": ">=180", "ip_rating": ">=IP65"}),
            # size AxB shorthand should still work
            ("panel cuadrado 600x600", {"luminaire_width": ">=600", "luminaire_length": ">=600"}),
            ("panel 60x60", {"luminaire_width": ">=600", "luminaire_length": ">=600"}),
        ]

        failures = []
        for query, expected_subset in cases:
            parsed = local_text_to_filters(query)
            for k, expected_v in expected_subset.items():
                got = parsed.get(k)
                if got != expected_v:
                    failures.append((query, k, expected_v, got, parsed))

        if failures:
            lines = ["Multilingual dimension/comparator regressions:"]
            for q, k, exp, got, parsed in failures:
                lines.append(f"- {q!r} key={k!r}: expected {exp!r}, got {got!r}, parsed={parsed}")
            self.fail("\n".join(lines))


if __name__ == "__main__":
    unittest.main()
