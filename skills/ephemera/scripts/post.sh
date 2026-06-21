#!/usr/bin/env bash
# Post a file to Ephemera via the upload endpoint.
# Usage: post.sh <kind> <file> [title] [ttl_minutes]
# Prints the JSON response to stdout.
set -euo pipefail

kind="${1:?kind required (log, json, markdown, text, image, report)}"
file="${2:?file path required}"
title="${3:-}"
ttl="${4:-120}"

EPHEMERA_URL="${EPHEMERA_URL:-http://localhost:8000}"

if [[ ! -f "$file" ]]; then
  echo "post.sh: file not found: $file" >&2
  exit 1
fi

AUTH=()
if [[ -n "${EPHEMERA_API_KEY:-}" ]]; then
  AUTH=(-H "x-api-key: $EPHEMERA_API_KEY")
fi

url="$EPHEMERA_URL/api/artifacts/upload?kind=$(printf '%s' "$kind" | jq -sRr @uri)&ttl_minutes=$ttl"
if [[ -n "$title" ]]; then
  url="${url}&title=$(printf '%s' "$title" | jq -sRr @uri)"
else
  url="${url}&filename=$(printf '%s' "$(basename "$file")" | jq -sRr @uri)"
fi

ctype="text/plain"
case "$kind" in
  json) ctype="application/json" ;;
  image)
    case "${file##*.}" in
      png|PNG) ctype="image/png" ;;
      jpg|jpeg|JPG|JPEG) ctype="image/jpeg" ;;
      gif|GIF) ctype="image/gif" ;;
      webp|WEBP) ctype="image/webp" ;;
      svg|SVG) ctype="image/svg+xml" ;;
      *) ctype="application/octet-stream" ;;
    esac
    ;;
  report) ctype="text/html" ;;
esac

curl -s "$url" \
  -H "content-type: $ctype" \
  "${AUTH[@]}" \
  --data-binary "@$file"
