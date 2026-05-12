#!/usr/bin/env bash
# Abort mid-stream and verify server health.
#
# Starts a long-running chat stream in the background, kills curl mid-stream
# after a short wait, then queries /api/v1/health to confirm the server
# remained healthy (no leaked tasks, no 500s).

set -euo pipefail

CURL_PID=""
cleanup() {
    if [ -n "${CURL_PID:-}" ] && kill -0 "$CURL_PID" 2>/dev/null; then
        kill "$CURL_PID" 2>/dev/null || true
        wait "$CURL_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

echo "[05] starting long chat stream in background…"
curl -fsN -X POST "http://127.0.0.1:8765/api/v1/chat/stream" \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"id":"m1","role":"user","content":"Write a very long story about wind energy. Go into great detail.","timestamp":"2026-05-04T00:00:00Z"}],
        "context": {"active_network_id": null, "active_network_name": null, "pinned_network_ids": []}
    }' >/dev/null 2>&1 &
CURL_PID=$!

echo "[05] waiting 1s then aborting (pid=${CURL_PID})…"
sleep 1

echo "[05] killing stream…"
kill "$CURL_PID" 2>/dev/null || true
wait "$CURL_PID" 2>/dev/null || true
CURL_PID=""

echo "[05] verifying server is still healthy…"
curl -fs "http://127.0.0.1:8765/api/v1/health" >/dev/null
echo "[05] server healthy after abort"
