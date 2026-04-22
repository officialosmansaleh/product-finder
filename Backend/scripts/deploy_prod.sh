#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-$(pwd)}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-180}"
HEALTH_POLL_SECONDS="${HEALTH_POLL_SECONDS:-5}"

cd "$APP_DIR"

if [[ ! -f ".env" ]]; then
  echo "Missing .env in $APP_DIR" >&2
  exit 1
fi

if [[ ! -f "docker-compose.prod.yml" ]]; then
  echo "Missing docker-compose.prod.yml in $APP_DIR" >&2
  exit 1
fi

echo "Starting production deployment from $APP_DIR"
docker compose -f docker-compose.prod.yml pull --ignore-buildable
docker compose -f docker-compose.prod.yml up -d --build

deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
health_url="http://127.0.0.1/health"

while (( SECONDS < deadline )); do
  if python3 scripts/check_health.py "$health_url" --expect-backend postgres >/tmp/productfinder-health.log 2>/tmp/productfinder-health.err; then
    echo "Healthcheck passed:"
    cat /tmp/productfinder-health.log
    exit 0
  fi
  sleep "$HEALTH_POLL_SECONDS"
done

echo "Deployment failed healthcheck. Recent app logs:" >&2
docker compose -f docker-compose.prod.yml logs app --tail=100 >&2 || true
echo "Recent caddy logs:" >&2
docker compose -f docker-compose.prod.yml logs caddy --tail=100 >&2 || true
if [[ -f /tmp/productfinder-health.err ]]; then
  cat /tmp/productfinder-health.err >&2
fi
exit 1
