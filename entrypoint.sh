#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
CONFIG_FILE="$DATA_DIR/server.toml"
CLIENT_CONFIG="$DATA_DIR/client.toml"
INDEX_DONE="$DATA_DIR/.indexed"
LIVE_DIR="/content/live"

mkdir -p "$DATA_DIR"
mkdir -p "/content/live/wikinews" "/content/live/arxiv"

# Write server config (empty token = no authentication required)
cat > "$CONFIG_FILE" <<EOF
[server]
data_dir = "$DATA_DIR"
token    = "${TOKEN:-}"
bind     = "0.0.0.0:${PORT:-8765}"

[sources.wikipedia]
path = "/content/wikipedia"

[sources.github]
path = "/content/github"

[sources.gutenberg]
path = "/content/gutenberg"

[sources.archive]
path = "/content/archive"

[sources.wikinews]
path = "/content/live/wikinews"

[sources.arxiv]
path = "/content/live/arxiv"

[sources.zips]
path = "/content/zips"
EOF

# Write client config (used by find-scan for indexing)
cat > "$CLIENT_CONFIG" <<EOF
[server]
url   = "http://localhost:${PORT:-8765}"
token = "${TOKEN:-}"

[[sources]]
name = "wikipedia"
path = "/content/wikipedia"
include = ["**"]

[[sources]]
name = "github"
path = "/content/github"
include = ["**"]

[[sources]]
name = "gutenberg"
path = "/content/gutenberg"
include = ["**"]

[[sources]]
name = "archive"
path = "/content/archive"
include = ["**"]

[[sources]]
name = "wikinews"
path = "/content/live/wikinews"
include = ["**"]

[[sources]]
name = "arxiv"
path = "/content/live/arxiv"
include = ["**"]

[[sources]]
name = "zips"
path = "/content/zips"
include = ["**"]
EOF

# Start find-server in the background
find-server --config "$CONFIG_FILE" &
SERVER_PID=$!

# Wait for server to be ready
echo "Waiting for find-server..."
for i in $(seq 1 30); do
  if curl -sf "http://localhost:${PORT:-8765}/api/v1/settings" > /dev/null 2>&1; then
    echo "Server ready."
    break
  fi
  sleep 1
done

# Index pre-seeded content on first run
if [ ! -f "$INDEX_DONE" ]; then
  echo "Indexing pre-seeded content..."
  find-scan --config "$CLIENT_CONFIG"
  touch "$INDEX_DONE"
  echo "Indexing complete."
else
  echo "Already indexed — skipping."
fi

# Backfill live content on first run (last 30 days of Wikinews + arXiv)
LIVE_DONE="$DATA_DIR/.live_seeded"
if [ ! -f "$LIVE_DONE" ]; then
  echo "Backfilling live content (last 30 days)..."
  python3 /scripts/fetch_live.py --backfill "$LIVE_DIR"
  find-scan --config "$CLIENT_CONFIG"
  touch "$LIVE_DONE"
  echo "Live backfill complete."
fi

# Background loop: refresh live content hourly
(
  while true; do
    sleep 3600
    echo "Refreshing live content..."
    python3 /scripts/fetch_live.py "$LIVE_DIR" && \
      find-scan --config "$CLIENT_CONFIG" && \
      echo "Live refresh complete."
  done
) &

trap 'kill "$SERVER_PID"' INT TERM
wait "$SERVER_PID"
