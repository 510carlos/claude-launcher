#!/usr/bin/env bash
set -euo pipefail

LAUNCHER_URL="${CLAUDE_LAUNCHER_URL:-http://127.0.0.1:8765/api/hooks/session-start}"
SESSION_ID="${CLAUDE_LAUNCHER_SESSION_ID:-}"
WORKSPOT="${CLAUDE_LAUNCHER_WORKSPOT:-}"
LABEL="${CLAUDE_LAUNCHER_LABEL:-}"
BRANCH="${CLAUDE_LAUNCHER_BRANCH:-}"
PAYLOAD_FILE="${1:-}"
URL="${CLAUDE_REMOTE_CONTROL_URL:-${CLAUDE_CODE_REMOTE_CONTROL_URL:-}}"

if [[ -n "$PAYLOAD_FILE" && -f "$PAYLOAD_FILE" && $(command -v python3 >/dev/null 2>&1; echo $?) -eq 0 ]]; then
  mapfile -t PARSED < <(python3 - "$PAYLOAD_FILE" <<'PY'
import json, sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text())
print(payload.get('url') or payload.get('remoteControlUrl') or payload.get('remote_control_url') or '')
print(payload.get('branch') or '')
print(payload.get('label') or payload.get('session_name') or '')
PY
)
  [[ -n "${PARSED[0]:-}" ]] && URL="${PARSED[0]}"
  [[ -n "${PARSED[1]:-}" ]] && BRANCH="${PARSED[1]}"
  [[ -n "${PARSED[2]:-}" ]] && LABEL="${PARSED[2]}"
fi

BODY=$(python3 - <<'PY' "$SESSION_ID" "$WORKSPOT" "$LABEL" "$BRANCH" "$URL"
import json, sys
print(json.dumps({
    'session_id': sys.argv[1] or None,
    'workspot': sys.argv[2] or None,
    'label': sys.argv[3] or None,
    'branch': sys.argv[4] or None,
    'url': sys.argv[5] or None,
    'status': 'running',
    'source': 'session_start_hook',
}))
PY
)

curl -fsS -X POST "$LAUNCHER_URL" \
  -H 'Content-Type: application/json' \
  -d "$BODY"
