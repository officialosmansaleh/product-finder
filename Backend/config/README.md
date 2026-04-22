# Runtime Config Guide

This folder contains runtime tunables for the backend.

- Main file: `runtime_config.txt`
- Format: `key=value`
- Comments: lines starting with `#`
- Unknown keys: ignored
- Missing keys: backend uses code defaults
- Missing/broken file: backend still runs with defaults

## How It Works

The backend reads config through `app/runtime_config.py`.

- If `RUNTIME_CONFIG_PATH` is set, that file is used.
- Otherwise default path is `Backend/config/runtime_config.txt`.

This means config changes do not require Python code changes.

## Edit Rules

- Keep values numeric for numeric keys.
- Use `true/false` for boolean-like keys.
- Use comma-separated values for list keys.
- Do not remove keys unless you want default fallback behavior.

## High-Impact Keys

These are the safest and most useful keys to tune first.

- `main.dimension_tolerance`
  - Purpose: tolerance on dimension comparisons
  - Typical range: `0.02` to `0.10`
  - Current default: `0.05`

- `main.spec_mode_exact_threshold`
  - Purpose: strictness for spec-like exact matches
  - Typical range: `0.60` to `0.85`
  - Current default: `0.72`

- `main.spec_mode_fallback_floor`
  - Purpose: fallback floor when no exact results
  - Typical range: `0.45` to `0.70`
  - Current default: `0.55`

- `main.similar_text_boost`
  - Purpose: text relevance boost in similarity ranking
  - Typical range: `0.10` to `0.50`
  - Current default: `0.35`

- `main.search_candidate_multiplier`, `main.search_candidate_min`, `main.search_candidate_max`
  - Purpose: search candidate pool size and performance
  - Effect: larger values can improve recall but increase latency

- `main.http_timeout_image_extract_sec`, `main.http_timeout_gql_sec`, `main.http_timeout_datasheet_sec`
  - Purpose: outbound request timeout control
  - Effect: too low may fail often, too high may slow requests

- `scoring.weight.*`
  - Purpose: relative importance of fields in scoring
  - Effect: directly changes ranking behavior

## Safety Recommendations

- Change only a few keys at once.
- Keep a copy of known-good `runtime_config.txt`.
- After changes, run backend smoke tests and one real query set.
- If results degrade, revert file or remove the edited key lines to use defaults.

## Quick Recovery

If something goes wrong:

1. Restore `runtime_config.txt` from backup.
2. Or delete problematic lines.
3. Or remove/rename the whole file and rely on code defaults.

