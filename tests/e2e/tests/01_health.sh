#!/usr/bin/env bash
# Health-check E2E test.
#
# Verifies:
#   1. GET /api/v1/health  returns 2xx
#   2. GET /api/v1/version/ returns JSON with chat_enabled:true

set -euo pipefail

curl -fs "http://127.0.0.1:8765/api/v1/health" >/dev/null
curl -fs "http://127.0.0.1:8765/api/v1/version/" | grep -q '"chat_enabled":true'
