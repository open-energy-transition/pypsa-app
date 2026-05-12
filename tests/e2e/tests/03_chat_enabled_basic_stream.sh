#!/usr/bin/env bash
# Stream a message and validate the core SSE event sequence.
set -euo pipefail

EVENTS=$(curl -fsN -X POST "http://127.0.0.1:8765/api/v1/chat/stream" \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"id":"m1","role":"user","content":"Say hello in one word.","timestamp":"2026-05-04T00:00:00Z"}],
        "context": {"active_network_id": null, "active_network_name": null, "pinned_network_ids": []}
    }' | python3 lib/sse_parse.py)

echo "$EVENTS" | jq -se '.[0] | select(.event == "RunStarted")' >/dev/null \
    || ( echo "expected first event RunStarted"; exit 1 )

echo "$EVENTS" | jq -se 'map(select(.event == "TextMessageContent")) | length > 0' >/dev/null \
    || ( echo "expected at least one TextMessageContent"; exit 1 )

echo "$EVENTS" | jq -se 'map(select(.event == "RunFinished")) | length == 1' >/dev/null \
    || ( echo "expected exactly one RunFinished"; exit 1 )
