#!/usr/bin/env bash
# Verifies that POST /api/v1/chat/stream returns 404 when CHAT_ENABLED=false.
# Brings up its own compose stack with compose.disabled.yaml on port 8766.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
E2E_DIR="$(dirname "$SCRIPT_DIR")"

COMPOSE_FILES=(-f "$E2E_DIR/compose.yaml" -f "$E2E_DIR/compose.disabled.yaml")

cleanup() {
    docker compose "${COMPOSE_FILES[@]}" down -v --remove-orphans
}
trap cleanup EXIT

echo "[02] building + starting app with CHAT_ENABLED=false…"
docker compose "${COMPOSE_FILES[@]}" up -d --build --wait

echo "[02] POST /api/v1/chat/stream → expecting 404…"
STATUS=$(curl -o /dev/null -s -w "%{http_code}" -X POST \
    "http://127.0.0.1:8766/api/v1/chat/stream" \
    -H "Content-Type: application/json" \
    -d '{"messages":[],"context":{"active_network_id":null,"active_network_name":null,"pinned_network_ids":[]}}')

echo "[02] status=${STATUS}"
[ "$STATUS" = "404" ]
