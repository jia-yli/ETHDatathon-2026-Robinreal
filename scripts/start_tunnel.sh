#!/usr/bin/env bash
#
# Start a Cloudflare quick tunnel to the local FastAPI harness and write the
# resulting public URL to `.api_base` at the repo root.  The demo notebook
# reads that file, so a restart here auto-refreshes the notebook's API_BASE.
#
# Usage:
#   scripts/start_tunnel.sh          # tunnels to http://localhost:8000
#   scripts/start_tunnel.sh 8001     # tunnels to http://localhost:8001
#
# Leave this command running during judging; Ctrl-C kills the tunnel.

set -euo pipefail

PORT="${1:-8000}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${REPO_ROOT}/.api_base"

# Clear any stale URL so callers can tell when the new one appears.
: > "$OUT"

echo "[start_tunnel] launching cloudflared → http://localhost:${PORT}"
echo "[start_tunnel] will write the public URL to ${OUT}"

# Stream cloudflared output to the terminal AND capture the first
# trycloudflare.com URL into .api_base.  `grep -m1` exits after the first
# match, but `tee` keeps the tunnel alive.
npx cloudflared tunnel --url "http://localhost:${PORT}" 2>&1 \
  | tee >(
      grep -m1 -oE 'https://[a-z0-9-]+\.trycloudflare\.com' > "$OUT"
      URL="$(tr -d '[:space:]' < "$OUT")"
      printf '\n[start_tunnel] public URL: %s\n[start_tunnel] wrote to %s\n\n' \
        "$URL" "$OUT" >&2
    )
