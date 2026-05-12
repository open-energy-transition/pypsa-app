#!/usr/bin/env bash
# E2E test harness driver with cleanup trap.
#
# When LLM_API_KEY is unset (empty), the harness starts a stub-LLM container
# alongside the app so tests can run without a live LLM provider.
#
# Usage:
#   LLM_API_KEY= bash tests/e2e/run.sh          # stub-LLM path
#   LLM_API_KEY=sk-... bash tests/e2e/run.sh    # live LLM path

set -euo pipefail

cd "$(dirname "$0")"

if [ -z "${LLM_API_KEY:-}" ]; then
    COMPOSE_FILES=(-f compose.yaml -f compose.stub.yaml)
    echo "[e2e] LLM_API_KEY unset — using stub-LLM override"
else
    COMPOSE_FILES=(-f compose.yaml)
    echo "[e2e] LLM_API_KEY provided — using live LLM"
fi

cleanup() { docker compose "${COMPOSE_FILES[@]}" down -v --remove-orphans; }
trap cleanup EXIT

echo "[e2e] building + starting services…"
docker compose "${COMPOSE_FILES[@]}" up -d --build --wait

PASS=0
FAIL=0
for t in tests/*.sh; do
    echo "--- ${t}"
    if bash "$t"; then
        PASS=$((PASS + 1))
        echo "    PASS"
    else
        FAIL=$((FAIL + 1))
        echo "    FAIL"
    fi
done
echo "[e2e] passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]