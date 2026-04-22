# Release Checklist

## Before Deploy

- Confirm backend dependencies are installed from `requirements.txt`.
- Confirm the live environment has the latest frontend assets and backend code together.
- Confirm `OPENAI_API_KEY`, auth settings, SMTP settings, and database settings are correct in admin settings or environment variables.
- Confirm the latest logo asset is present for quote PDF export:
  - `frontend/laiting-logo-ai.png`

## After Deploy

- Open `/frontend/` and verify search still loads.
- Open `/frontend/tools.html` and verify the top bar, logout area, and privacy button placement.
- Open `/frontend/quote.html` and verify:
  - project fields load correctly
  - contractor and consultant are required
  - add-by-code field is slim
  - row move arrows render correctly
- Open `/frontend/admin.html` and verify:
  - user list loads
  - visible quotes table loads
  - analytics visibility respects role rules

## Role Smoke Tests

- `manager`
  - can see only assigned-country users
  - can see only assigned-country quotes in the visible quotes table
  - cannot access analytics
- `director`
  - can see all users and all quotes
  - can access analytics
  - cannot access admin-only technical settings
- `admin`
  - can access everything, including technical settings

## Quote Smoke Tests

- Save a quote with:
  - project name
  - status
  - contractor
  - consultant
- Reload the saved quote and verify all fields persist.
- Export quote PDF and verify:
  - Laiting logo appears in the header
  - contractor and consultant appear in the summary

## Search Smoke Tests

- Verify `street` and `road` behavior against the current family naming in production data.
- Verify zero-result recovery actions still work.
- Verify similar results are capped correctly.
- Verify empty search does not return the whole catalog.

## Compliance / Policy

- Update privacy notice text to reflect first-party consented analytics.
- Update cookie policy text to reflect analytics consent choices.
- Verify refusal is as easy as acceptance in the consent UI.

## Monitoring

- Watch backend logs after deploy for:
  - auth errors
  - quote export failures
  - PDF generation errors
  - catalog load failures
  - rate-limit spikes
