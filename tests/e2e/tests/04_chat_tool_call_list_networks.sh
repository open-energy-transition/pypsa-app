#!/usr/bin/env bash
# Stream a message that triggers a list_networks tool call and validate
# the SSE events.
set -euo pipefail

EVENTS=$(curl -fsN -X POST "http://127.0.0.1:8765/api/v1/chat/stream" \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"id":"m1","role":"user","content":"List my networks please","timestamp":"2026-05-04T00:00:00Z"}],
        "context": {"active_network_id": null, "active_network_name": null, "pinned_network_ids": []}
    }' | python3 lib/sse_parse.py)

echo "$EVENTS" | jq -se 'map(select(.event == "ToolCallStart" and .data.tool_name == "list_networks")) | length > 0' >/dev/null \
    || ( echo "expected at least one ToolCallStart with tool_name list_networks"; exit 1 )

echo "$EVENTS" | jq -se 'map(select(.event == "ToolCallEnd")) | length > 0' >/dev/null \
    || ( echo "expected at least one ToolCallEnd"; exit 1 )

echo "$EVENTS" | jq -se 'map(select(.event == "ToolCallResult" and .data.is_error == false)) | length > 0' >/dev/null \
    || ( echo "expected at least one ToolCallResult with is_error false"; exit 1 )
