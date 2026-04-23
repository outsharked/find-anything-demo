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

# Symlink content into repo root for the build context, clean up after
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ln -sfn "$CONTENT_DIR" "$SCRIPT_DIR/content"
trap 'rm -f "$SCRIPT_DIR/content"' EXIT

docker build -t "$IMAGE" "$SCRIPT_DIR"
echo "Built: $IMAGE"
