# Browser E2E Smoke Tests

This suite uses Playwright to cover the main browser flows:

- anonymous catalog search
- signup request
- admin approval
- approved-user login
- add to quote
- save and reload saved quote

## Prerequisites

1. The local app must already be reachable, usually at `http://127.0.0.1:8000`.
2. Install the test dependencies:

```bash
npm install
npm run test:e2e:install
```

3. If your admin bootstrap credentials differ from the defaults, export:

```bash
E2E_ADMIN_EMAIL=your-admin-email
E2E_ADMIN_PASSWORD=your-admin-password
```

## Run

```bash
npm run test:e2e
```

Optional:

```bash
npm run test:e2e:headed
```
