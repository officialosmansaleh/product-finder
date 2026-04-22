# Stability Checks (Low-Risk Baseline)

This is a no-behavior-change validation runner to quickly confirm the current app baseline is still stable after small edits.

## Run

From repo root:

```bash
python Backend/tests/run_stability_checks.py
```

## What it runs

1. Multilingual parser/API regression suite
   - `Backend/tests/run_parser_regressions.py`
2. Python syntax compile checks for critical backend files
   - `Backend/app/main.py`
   - `Backend/app/local_parser.py`
   - `Backend/app/llm_intent.py`

## When to use

- Before a demo/meeting
- After small UI/backend edits
- Before committing "safe cleanup" changes

## Scope

These checks are intentionally lightweight and do **not** replace:
- end-to-end UI testing
- production environment validation
- deployment smoke tests
