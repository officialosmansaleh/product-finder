# Parser Regression Tests

These tests protect multilingual parsing behavior in `app/local_parser.py` and the `/debug/parse` endpoint.

## What is covered

- `test_local_parser_multilang_families.py`
  - Family inference from application words (office, school, hospital, corridor, facade, warehouse/logistics)
  - Coverage across supported UI/parser languages

- `test_local_parser_multilang_dimensions.py`
  - Multilingual dimension aliases (`diameter`, `length`, `width`, `height`)
  - Comparator parsing (`>=`, `<=`, min/max, "at least", "at most", etc.)
  - `AxB` shorthand
  - Regression check for `IP65` not being misread as a diameter

- `test_local_parser_multilang_specs.py`
  - `IP`, `IK`, `UGR`, `CRI`, `CCT`
  - `DALI`, emergency, asymmetry, shape aliases

- `test_debug_parse_api_regression.py`
  - Lightweight API regression for `/debug/parse`
  - Skips automatically if app import/test client setup is unavailable in the environment

## Run all parser regressions

From repo root:

```bash
python Backend/tests/run_parser_regressions.py
```

Or with unittest directly:

```bash
python -m unittest \
  Backend/tests/test_local_parser_multilang_families.py \
  Backend/tests/test_local_parser_multilang_dimensions.py \
  Backend/tests/test_local_parser_multilang_specs.py \
  Backend/tests/test_debug_parse_api_regression.py
```

## How to extend

When adding synonyms or parser rules:

1. Add at least one positive test case for the new behavior.
2. Add one edge case if the rule could collide with another field (for example, `IP65` vs dimensions).
3. Prefer ASCII-safe variants in tests when terminal/codepage issues may corrupt accented text.
4. Keep expected assertions focused on a small subset of keys (only the keys relevant to the scenario).

## Encoding note

`app/local_parser.py` contains multilingual literals and should remain UTF-8 encoded.
