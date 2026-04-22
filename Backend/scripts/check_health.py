#!/usr/bin/env python3
"""Simple healthcheck probe for Product Finder deployments."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a Product Finder /health endpoint.")
    parser.add_argument("url", help="Health endpoint URL, for example https://example.com/health")
    parser.add_argument(
        "--expect-backend",
        default=None,
        help="Optional expected database backend, for example postgres",
    )
    args = parser.parse_args()

    try:
        with urllib.request.urlopen(args.url, timeout=15) as response:
            body = response.read().decode("utf-8")
            status_code = response.getcode()
    except urllib.error.URLError as exc:
        print(f"HEALTHCHECK_ERROR unable to reach {args.url}: {exc}", file=sys.stderr)
        return 1

    if status_code != 200:
        print(f"HEALTHCHECK_ERROR unexpected status code {status_code}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        print(f"HEALTHCHECK_ERROR invalid JSON body: {exc}", file=sys.stderr)
        return 1

    app_status = payload.get("status")
    if app_status != "ok":
        print(f"HEALTHCHECK_ERROR unexpected app status {app_status!r}", file=sys.stderr)
        return 1

    db_active = payload.get("database_active")
    if db_active is False:
        print("HEALTHCHECK_ERROR database_active is false", file=sys.stderr)
        return 1

    if args.expect_backend:
        backend = payload.get("database_backend")
        if backend != args.expect_backend:
            print(
                f"HEALTHCHECK_ERROR expected backend {args.expect_backend!r} but got {backend!r}",
                file=sys.stderr,
            )
            return 1

    print(
        json.dumps(
            {
                "url": args.url,
                "status": app_status,
                "database_active": db_active,
                "database_backend": payload.get("database_backend"),
                "products_loaded": payload.get("product_count"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
