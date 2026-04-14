#!/bin/bash
# One-time SearXNG installation via pip (no Docker needed)
set -e

echo "Installing SearXNG..."

pip3 install searxng --break-system-packages 2>/dev/null || pip3 install searxng

echo "SearXNG installed."
echo "Settings file: $(dirname "$0")/searxng/settings.yml"
