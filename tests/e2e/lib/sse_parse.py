"""SSE → JSON-lines parser.

Reads SSE (Server-Sent Events) from stdin and emits one JSON object per
event block on stdout. Used by E2E test scripts to parse `curl --no-buffer`
SSE streams before piping into `jq` for assertions.
"""

import json
import sys


def main() -> None:
    """Parse SSE from stdin, write JSON-lines to stdout."""
    buf = ""
    for line in sys.stdin:
        if line == "\n":
            _emit_block(buf)
            buf = ""
        else:
            buf += line
    if buf.strip():
        _emit_block(buf)


def _emit_block(buf: str) -> None:
    """Parse one completed SSE block and emit a JSON line."""
    ev_name = ""
    data = ""
    for raw in buf.splitlines():
        if raw.startswith(":"):
            continue
        if raw.startswith("event:"):
            ev_name = raw[6:].strip()
        elif raw.startswith("data:"):
            data += raw[5:].strip()
    if not ev_name:
        return
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        payload = {"_raw": data}
    print(json.dumps({"event": ev_name, "data": payload}), flush=True)


if __name__ == "__main__":
    main()
