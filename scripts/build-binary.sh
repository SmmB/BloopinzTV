#!/usr/bin/env bash
# Build a standalone FreeFlix executable (no Python needed) into ./dist/.
# Requires uv. Bundles curl_cffi's native lib + package metadata.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run --with . --with pyinstaller --with lxml \
  pyinstaller --onefile --name freeflix \
  --collect-all curl_cffi \
  --collect-submodules freeflix_cli \
  --hidden-import readchar \
  --copy-metadata readchar --copy-metadata freeflix-cli --copy-metadata curl_cffi \
  src/freeflix_cli/__main__.py
echo "Built: dist/freeflix"
