#!/usr/bin/env bash
# Build the find-anything-demo Docker image with content from /mnt/data.
# Usage: ./build.sh [image-tag]
set -euo pipefail

IMAGE="${1:-ghcr.io/outsharked/find-anything-demo:latest}"
CONTENT_DIR="/mnt/data/code/find-anything-demo/content"

if [ ! -d "$CONTENT_DIR" ]; then
  echo "ERROR: content not found at $CONTENT_DIR"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

docker build \
  --build-context content="$CONTENT_DIR" \
  -t "$IMAGE" "$SCRIPT_DIR"
echo "Built: $IMAGE"
