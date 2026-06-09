# Artifact Viewer

A self-hosted ephemeral artifact viewer for data that is annoying to inspect in chat.

## What it does

- Accepts a POSTed payload and returns a temporary URL
- Renders clean pages for:
  - text / logs
  - JSON
  - markdown
  - images
  - safe HTML-style reports
- Expires artifacts automatically with TTL cleanup
- Ships with Docker Compose for easy LAN hosting

## Quick start

```bash
uv venv
uv pip install -r requirements-dev.txt
uv run uvicorn artifact_viewer.main:app --host 0.0.0.0 --port 8000
```

Open:

- http://127.0.0.1:8000
- or `http://<your-lan-ip>:8000` from another device on the network

## Create an artifact

```bash
curl -s http://127.0.0.1:8000/api/artifacts \
  -H 'content-type: application/json' \
  -d '{
    "title": "Demo log",
    "kind": "log",
    "ttl_minutes": 30,
    "content": "line 1\nline 2\nline 3"
  }' | jq
```

The response includes `url` for the temporary page.

## Docker

```bash
docker compose up --build
```

## Tests

```bash
uv run pytest -q
```

## Config

Environment variables:

- `ARTIFACT_DB_PATH` — SQLite database path
- `BASE_URL` — optional canonical public URL to include in API responses
- `DEFAULT_TTL_MINUTES` — default TTL
- `MAX_TTL_MINUTES` — maximum allowed TTL
- `CLEANUP_INTERVAL_SECONDS` — background cleanup interval

## Design philosophy

See `DESIGN.md` for the visual system and UI rules.
