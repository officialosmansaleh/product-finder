# Admin Panel Documentation

This document describes the implemented Admin Panel in `Backend/frontend/admin.html`, the backend endpoints it uses, and the access rules enforced by the application.

## Purpose

The Admin Panel is the internal workspace for:

- reviewing and approving access requests
- managing users and roles
- viewing saved quotes inside the viewer's allowed scope
- checking consent-based usage analytics
- monitoring catalog health
- exporting catalog release differences
- tuning scoring weights
- updating runtime/admin settings

Frontend entry point:

- `/frontend/admin.html`

Main backend sources:

- `Backend/frontend/admin.html`
- `Backend/frontend/assets/auth.js`
- `Backend/app/auth_router.py`
- `Backend/app/auth.py`
- `Backend/app/admin_settings.py`
- `Backend/app/main.py`

## Access Model

The panel is available only to approved staff users:

- `admin`
- `director`
- `manager`

Regular `user` accounts cannot open the admin workspace.

### Role Matrix

| Area | Admin | Director | Manager |
|---|---:|---:|---:|
| Open Admin Panel | Yes | Yes | Yes |
| View pending users | Yes | Yes | No |
| Approve/reject users | Yes | Yes | No |
| Edit users | Yes | Yes | No |
| Assign `admin` role | Yes | No | No |
| View visible users | Yes | Yes | Yes, country-scoped |
| View visible quotes | Yes | Yes | Yes, country-scoped |
| View analytics | Yes | Yes | No |
| View catalog health | Yes | Yes | Yes |
| Export catalog release diff | Yes | Yes | No |
| Edit scoring controls | Yes | No | No |
| Edit settings | Yes | No | No |

### Scope Rules

- `admin` sees the full workspace.
- `director` sees the full workspace, but cannot access admin-only settings/scoring.
- `manager` is limited to users and quotes in `assigned_countries`.
- If a manager has no assigned countries, their visible user/quote scope is empty.

## Authentication And Approval Flow

The panel depends on the same auth system used by the main frontend.

### Sign Up

Users can request access from the header auth modal:

- `email`
- `password`
- `full_name`
- `company_name`
- `country`

Behavior:

- new accounts are created with status `pending`
- password rule is at least 10 characters with at least 1 letter and 1 number
- pending users cannot log in until approved

### Login Session

Session behavior:

- cookie-based auth is used for the browser
- access and refresh cookies are issued on login
- frontend session state is mirrored in `sessionStorage`
- idle timeout is 30 minutes in the frontend
- on `401`, the frontend tries `/auth/refresh` automatically

### Approval Lifecycle

Possible account statuses:

- `pending`
- `approved`
- `rejected`

Leadership users can:

- approve a pending user
- reject/block a user
- edit a user's profile and role
- permanently delete a rejected user

Important constraints:

- only admins can manage admin accounts
- directors can assign `user`, `manager`, and `director`
- managers cannot manage users
- a user cannot delete their own account from the admin table
- a rejected user must be rejected/blocked before deletion

## Panel Sections

### 1. Overview

The page loads as a multi-section workspace. Navigation is handled client-side through anchors and role-based visibility.

Visible sections by role:

- `admin`: overview, users, quotes, analytics, catalog health, release changes, scoring, settings
- `director`: overview, users, quotes, analytics, catalog health, release changes
- `manager`: overview, users, quotes, catalog health

### 2. Pending Access Requests

Leadership-only section used to review new signups.

Actions:

- approve a user
- choose role on approval
- assign countries when role is `manager`
- reject a request

Backend endpoint:

- `GET /admin/users/pending`
- `POST /admin/users/{user_id}/approve`
- `POST /admin/users/{user_id}/reject`

Approval notes:

- assigned countries are meaningful only for managers
- if role is not `manager`, assigned countries are cleared

### 3. User Management

Staff can open the user table, but behavior differs by role.

What the table supports:

- search by name/email/company/country
- filter by company, country, and status
- inspect saved quotes for a user
- edit user details
- change role
- block/reject a user
- re-approve a rejected user
- delete a rejected user permanently

Backend endpoints:

- `GET /admin/users`
- `PUT /admin/users/{user_id}`
- `POST /admin/users/{user_id}/approve`
- `POST /admin/users/{user_id}/reject`
- `DELETE /admin/users/{user_id}`
- `GET /admin/users/{user_id}/quotes`
- `GET /admin/users/{user_id}/quotes/{quote_id}`

Key behavior:

- directors and admins can view all users
- managers can only view users from their assigned countries
- managers can open quotes only for users inside their country scope

### 4. Visible Quotes

This section shows project quotes visible to the logged-in staff user.

Displayed fields include:

- project
- customer/company
- country
- project status
- contractor
- consultant
- quote owner
- item count
- timestamps

Features:

- text filtering
- country filtering
- status filtering
- CSV export

Backend endpoint:

- `GET /admin/quotes`

Scope:

- admin/director: all quotes
- manager: only quotes belonging to users in assigned countries

### 5. Analytics

This is a leadership-only section and is explicitly described in the UI as consent-based, first-party analytics.

Backend endpoint:

- `GET /admin/analytics/summary?days=<1..365>&top_n=<1..50>`

The summary aggregates activity such as:

- total events
- searches
- sessions
- active users
- top queries
- top countries
- product interactions
- compare usage
- quote funnel activity
- journey progression
- no-result and no-exact-result signals

Important note:

- analytics events are recorded only when the user has explicitly consented to analytics cookies

### 6. Catalog Health

This section gives a quality snapshot of the currently loaded catalog dataset.

Backend endpoint:

- `GET /admin/catalog-health`

Current checks include:

- total rows
- unique families
- unique manufacturers
- priced rows
- duplicate product codes
- legacy `road lighting` family values
- key field coverage
- missing family values
- missing prices
- invalid IP / IK formats
- unusual CCT values
- non-positive power, lumen, efficacy
- negative warranty values

This is intended as an operational quality gate before search or quoting issues appear.

### 7. Catalog Release Changes

This section is leadership-only and shows the latest release delta exported from the product database.

Backend endpoints:

- `GET /admin/catalog-release-diff`
- `GET /admin/catalog-release-diff/export`

Behavior:

- reads the latest release snapshot from the product database
- exposes a CSV export
- is unavailable if the product database is not active

### 8. Scoring Controls

This section is admin-only.

It exposes runtime tuning controls for the match percentage and ranking behavior used by search scoring.

Backend endpoints:

- `GET /admin/settings`
- `PUT /admin/settings/{setting_key}`

Supported control types include:

- per-field scoring weights such as `scoring_weight_product_family`
- penalty settings such as `scoring_missing_penalty`
- family multipliers such as `scoring_family_mismatch_multiplier`

Important implementation detail:

- scoring values are hot-applied through environment overrides
- tests confirm that changing scoring settings affects scoring live without restart for immediate-apply settings

Validation rules:

- `scoring_weight_*`: `0` to `20`
- `scoring_missing_penalty` and `scoring_deviation_penalty`: `0` to `5`
- `scoring_family_missing_multiplier` and `scoring_family_mismatch_multiplier`: `0` to `10`

### 9. Settings

This section is admin-only and covers non-scoring application settings.

Examples:

- AI configuration
- email/SMTP configuration
- security settings
- bootstrap admin settings
- catalog import paths
- deployment settings
- rate limit settings

Behavior:

- secret values stay masked in the UI
- non-secret values are shown directly
- some settings are immediate-apply
- some settings are stored but require restart/redeploy for full effect

Detailed setting catalog:

- see `Backend/ADMIN_SETTINGS_REFERENCE.md`

### Immediate-Apply Vs Restart-Required

If `immediate_apply` is enabled for a setting:

- the new value is written into stored settings
- the related environment override is updated immediately
- runtime auth/settings refresh logic is re-applied

If `restart_required` is enabled:

- the value can still be saved from the panel
- a restart or redeploy is needed for full effect

## Admin API Summary

### Auth

- `POST /auth/signup`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/refresh`
- `GET /auth/me`
- `POST /auth/password-reset/request`
- `POST /auth/password-reset/confirm`
- `GET /auth/consent`
- `POST /auth/consent`
- `POST /auth/analytics/event`

### User And Workspace Operations

- `GET /admin/users`
- `GET /admin/users/pending`
- `POST /admin/users/{user_id}/approve`
- `POST /admin/users/{user_id}/reject`
- `PUT /admin/users/{user_id}`
- `DELETE /admin/users/{user_id}`
- `GET /admin/users/{user_id}/quotes`
- `GET /admin/users/{user_id}/quotes/{quote_id}`
- `GET /admin/quotes`

### Insights And Catalog Operations

- `GET /admin/analytics/summary`
- `GET /admin/catalog-health`
- `GET /admin/catalog-release-diff`
- `GET /admin/catalog-release-diff/export`
- `GET /admin/access-matrix`

### Settings

- `GET /admin/settings`
- `PUT /admin/settings/{setting_key}`

## Operational Notes

- The admin frontend is served as a static page and calls same-origin backend APIs.
- The browser auth helper automatically redirects staff users to `/frontend/admin.html` from the account menu.
- Asset files under `/frontend/` get long-lived cache headers, but the main admin page still depends on live API calls.
- If the product database is unavailable, release diff features fail with `503`.
- If the catalog dataset is empty, catalog health returns an empty summary instead of failing.

## Recommended Future Additions

Good next documentation additions would be:

- screenshots for each panel section
- a short runbook for common admin tasks
- a field-by-field explanation of analytics metrics
- a release-diff CSV column reference
- a manager onboarding section focused on country-scoped usage
