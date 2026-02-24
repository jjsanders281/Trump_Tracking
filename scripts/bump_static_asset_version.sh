#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INDEX_HTML="${ROOT_DIR}/backend/app/static/index.html"
VERSION="${1:-$(date -u +%Y%m%d%H%M%S)}"

if [[ ! -f "${INDEX_HTML}" ]]; then
  echo "index.html not found at ${INDEX_HTML}" >&2
  exit 1
fi

if [[ ! "${VERSION}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid version '${VERSION}'. Use letters, numbers, dot, underscore, or dash." >&2
  exit 1
fi

perl -0pi -e "s#/static/styles\\.css(?:\\?v=[^\"'>]+)?#/static/styles.css?v=${VERSION}#g; s#/static/app\\.js(?:\\?v=[^\"'>]+)?#/static/app.js?v=${VERSION}#g;" "${INDEX_HTML}"

echo "Updated static asset version to '${VERSION}' in ${INDEX_HTML}"
