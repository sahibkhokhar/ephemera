# Ephemera

Ephemera is a self-hosted, ephemeral artifact viewer for agent output, CI logs, JSON payloads, markdown notes, images, and sanitized HTML reports.

Post a payload, get back a short-lived URL, and open it in a clean browser view. Artifacts expire automatically, so scratch output stays useful without becoming permanent storage.

## Features

- Temporary share URLs for logs, text, JSON, markdown, images, and HTML-style reports
- JSON API plus a raw file-upload endpoint, so agents and CI can stream a file straight in without JSON-wrapping it
- Server-rendered instance dashboard with recent artifacts, copy buttons, downloads, and mobile-friendly pages
- Log viewer with line numbers, wrapping, issue highlighting, live text or `/regex/` filtering, and match navigation
- Pretty JSON rendering and raw JSON endpoints for automation
- Markdown rendering with tables, fenced code blocks, and task lists
- Sanitized report HTML with a strict Content Security Policy
- Self-hosted API docs at `/api/docs` and an OpenAPI schema at `/api/openapi.json`
- Optional write authentication with `API_KEY`; artifact reads stay public
- SQLite storage, background TTL cleanup, Docker support, and no CDN/runtime network dependency

## Quick Start

```bash
uv venv
uv pip install -r requirements-dev.txt
uv run uvicorn artifact_viewer.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`, or use `http://<your-lan-ip>:8000` from another device on the same network.

The home page is your instance dashboard: live stats, recent artifacts, and an API quickstart for creating payloads.

## Docker

Quick start with the pre-built GHCR image:

```bash
docker compose up
```

Build locally from the Dockerfile instead:

```bash
docker compose build
docker compose up
```

By default the Compose setup stores data in `./data` and serves Ephemera on port `8000`.

To require an API key for artifact creation, create a `.env` file:

```bash
cp .env.example .env
```

Then set:

```env
API_KEY=change-me
BASE_URL=http://localhost:8000
```

Restart the container after changing environment variables.

## API Examples

Create a log artifact:

```bash
curl -s http://127.0.0.1:8000/api/artifacts \
  -H 'content-type: application/json' \
  -d '{
    "title": "Demo log",
    "kind": "log",
    "ttl_minutes": 30,
    "content": "line 1\nWARN slow request\nERROR failed job"
  }' | jq
```

Create a JSON artifact:

```bash
curl -s http://127.0.0.1:8000/api/artifacts \
  -H 'content-type: application/json' \
  -d '{
    "title": "Deploy metadata",
    "kind": "json",
    "ttl_minutes": 120,
    "content": {
      "service": "api",
      "version": "2026.06.20",
      "status": "ready"
    }
  }' | jq
```

Upload a file directly (the raw body becomes the content, no JSON wrapping):

```bash
curl -s "http://127.0.0.1:8000/api/artifacts/upload?kind=log&title=CI+log&ttl_minutes=120" \
  -H 'content-type: text/plain' \
  --data-binary @build.log | jq
```

Pass `kind` (required) and optional `title`, `filename`, and `ttl_minutes` as query
parameters. `json` bodies must be valid JSON; `image` uploads need a matching
`image/*` content type. The response matches `POST /api/artifacts`.

When `API_KEY` is set, include one of these headers on write requests:

```bash
-H 'x-api-key: your-key-here'
# or
-H 'authorization: Bearer your-key-here'
```

A successful create response includes a browser URL:

```json
{
  "id": "9f2c1a7b3e4d",
  "kind": "log",
  "title": "Demo log",
  "created_at": "2026-06-20T12:00:00Z",
  "expires_at": "2026-06-20T12:30:00Z",
  "url": "http://127.0.0.1:8000/a/9f2c1a7b3e4d"
}
```

Fetch artifact detail as JSON:

```bash
curl -s http://127.0.0.1:8000/api/artifacts/9f2c1a7b3e4d | jq
```

Download the original artifact content:

```bash
curl -OJ http://127.0.0.1:8000/a/9f2c1a7b3e4d/download
```

See `/api/docs` on a running instance for the full endpoint reference.

## Self-Hosting Notes

Ephemera is intended for small teams, local networks, homelabs, and private agent workflows. It works without external services once installed.

Set `BASE_URL` to the URL other people or agents should use when opening returned artifact links. If Ephemera sits behind a reverse proxy, point `BASE_URL` at the public proxy URL.

Viewing artifacts is public to anyone with the link. Set `API_KEY` when the instance is reachable by people or systems that should not be allowed to create artifacts.

Ephemera is a temporary artifact viewer, not long-term object storage. Use TTLs that match your workflow and mount `ARTIFACT_DB_PATH` on persistent storage if you want artifacts to survive container restarts until they expire.

## Configuration

All settings come from environment variables. See `.env.example` for a ready-to-edit template.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Ephemera` | Display name in the UI and page titles |
| `ARTIFACT_DB_PATH` | `./data/artifacts.db` | SQLite database path; parent directories are created automatically |
| `BASE_URL` | request host | Canonical URL used in API responses and copy-link buttons |
| `API_KEY` | unset | Optional key required for artifact creation |
| `DEFAULT_TTL_MINUTES` | `60` | TTL used when a request omits `ttl_minutes` |
| `MAX_TTL_MINUTES` | `10080` | Maximum accepted TTL, in minutes |
| `MAX_CONTENT_BYTES` | `5242880` | Maximum accepted request content size |
| `CLEANUP_INTERVAL_SECONDS` | `60` | How often expired artifacts are deleted |

## Security Model

Ephemera is designed to display untrusted artifact content with a conservative browser surface:

- Markdown and report HTML are sanitized with an allow-list before rendering.
- Script, style, iframe, event-handler, and `javascript:` URL content is removed from rich artifacts.
- Responses include a strict Content Security Policy, `X-Content-Type-Options`, `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer`.
- The UI uses first-party static assets only; no CDN or third-party script is required.

Authentication only protects writes. Treat every artifact URL as a bearer link that can be opened by anyone who has it.

## Connect an agent

If you run a local agent (Hermes, OpenClaw, Claude Code, Cursor, etc.), paste the
block below into its system prompt, skills folder, or project instructions.
Replace the instance URL and API key with your values.

```
Load the Ephemera skill (Agent Skills format):
https://raw.githubusercontent.com/sahibkhokhar/ephemera/main/skills/ephemera/SKILL.md

Or copy the skills/ephemera/ directory into your agent's skills path.

My instance:
  EPHEMERA_URL=http://192.168.1.50:8000
  EPHEMERA_API_KEY=                    # leave blank if writes are open
```

Works in Hermes, Cursor, OpenClaw, Claude Code, and other [Agent Skills](https://agentskills.io)-compatible harnesses. See [`skills/ephemera/SKILL.md`](skills/ephemera/SKILL.md).

## Development

In log views, enter a case-sensitive substring or a JavaScript regex enclosed in
slashes (for example, `/WARN|ERROR/`). The count shows visible lines out of the
original total; severity chips narrow the results further. Previous and Next
visit each highlighted match and wrap at either end. The `n` and `N` shortcuts
do the same outside text fields. Clear resets both text and severity filters.
Invalid regexes show a message and leave lines visible under the severity filter.

Run the test suite:

```bash
uv run pytest -q
```

Run the app locally:

```bash
uv run uvicorn artifact_viewer.main:app --reload --host 0.0.0.0 --port 8000
```

## License

MIT. See [LICENSE](LICENSE).
