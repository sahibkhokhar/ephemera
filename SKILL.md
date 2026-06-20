# Ephemera Agent Skill

Ephemera is a self-hosted, short-lived artifact viewer for agent output. Agents can POST logs, JSON payloads, markdown notes, images, and HTML-style reports to Ephemera and receive a temporary browser URL that can be shared with humans or other systems. Artifacts expire automatically by TTL, making Ephemera useful for debugging output, CI results, analysis reports, and transient collaboration without turning scratch files into permanent storage.

## Base URL

Use the `EPHEMERA_URL` environment variable when it is set. Otherwise default to `http://localhost:8000`.

```bash
EPHEMERA_URL="${EPHEMERA_URL:-http://localhost:8000}"
```

## Create an Artifact

Create artifacts with:

```http
POST /api/artifacts
Content-Type: application/json
```

Request body:

```json
{
  "title": "Human readable title",
  "kind": "log",
  "content": "artifact content",
  "ttl_minutes": 60
}
```

Fields:

- `title`: short display title. Optional; defaults to `Untitled artifact`.
- `kind`: one of `log`, `json`, `markdown`, `image`, or `report`.
- `content`: artifact payload. The expected shape depends on `kind`.
- `ttl_minutes`: lifetime in minutes. Optional; the server default is commonly 60 minutes.

Successful response:

```json
{
  "id": "9f2c1a7b3e4d",
  "kind": "log",
  "title": "Demo log",
  "created_at": "2026-06-20T12:00:00Z",
  "expires_at": "2026-06-20T13:00:00Z",
  "url": "http://localhost:8000/a/9f2c1a7b3e4d"
}
```

The most important fields for agents are:

- `id`: artifact identifier for later API calls.
- `url`: browser URL to share.
- `expires_at`: UTC expiration timestamp.

## Optional Authentication

Some Ephemera instances require an API key for writes. Reads remain public to anyone with the artifact link.

Use either header:

```bash
-H "x-api-key: $EPHEMERA_API_KEY"
```

or:

```bash
-H "Authorization: Bearer $EPHEMERA_API_KEY"
```

When auth may be enabled, build a reusable header:

```bash
AUTH_HEADER=()
if [ -n "${EPHEMERA_API_KEY:-}" ]; then
  AUTH_HEADER=(-H "x-api-key: $EPHEMERA_API_KEY")
fi
```

## Examples

### Log

Use `log` for plain text logs, command output, test failures, and stack traces.

```bash
EPHEMERA_URL="${EPHEMERA_URL:-http://localhost:8000}"

curl -s "$EPHEMERA_URL/api/artifacts" \
  -H "content-type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{
    "title": "Pytest failure",
    "kind": "log",
    "ttl_minutes": 120,
    "content": "FAILED tests/test_api.py::test_create\nAssertionError: expected 201, got 500"
  }'
```

### JSON

Use `json` for structured payloads. `content` can be an object, array, or a valid JSON string.

```bash
EPHEMERA_URL="${EPHEMERA_URL:-http://localhost:8000}"

curl -s "$EPHEMERA_URL/api/artifacts" \
  -H "content-type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{
    "title": "Deploy metadata",
    "kind": "json",
    "ttl_minutes": 240,
    "content": {
      "service": "api",
      "version": "2026.06.20",
      "status": "ready",
      "checks": ["unit", "integration", "smoke"]
    }
  }'
```

### Markdown

Use `markdown` for notes, summaries, investigation writeups, and task reports.

```bash
EPHEMERA_URL="${EPHEMERA_URL:-http://localhost:8000}"

curl -s "$EPHEMERA_URL/api/artifacts" \
  -H "content-type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{
    "title": "Incident notes",
    "kind": "markdown",
    "ttl_minutes": 1440,
    "content": "# Incident notes\n\n- Impact: elevated 500s\n- Cause: missing config\n- Fix: restored secret and restarted workers\n"
  }'
```

### Image

Use `image` for screenshots, charts, diagrams, and other visual output. `content` can be a URL/data URL string or an object with `src`, `alt`, and optional `caption`.

```bash
EPHEMERA_URL="${EPHEMERA_URL:-http://localhost:8000}"

curl -s "$EPHEMERA_URL/api/artifacts" \
  -H "content-type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{
    "title": "Latency chart",
    "kind": "image",
    "ttl_minutes": 360,
    "content": {
      "src": "https://example.com/charts/latency.png",
      "alt": "Latency chart for the API service",
      "caption": "P95 latency during the deploy window"
    }
  }'
```

### Report

Use `report` for sanitized HTML reports. Scripts, unsafe attributes, and unsafe URLs are removed before rendering.

```bash
EPHEMERA_URL="${EPHEMERA_URL:-http://localhost:8000}"

curl -s "$EPHEMERA_URL/api/artifacts" \
  -H "content-type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{
    "title": "CI report",
    "kind": "report",
    "ttl_minutes": 720,
    "content": "<h1>CI report</h1><p>Unit tests passed.</p><table><tr><th>Suite</th><th>Status</th></tr><tr><td>api</td><td>pass</td></tr></table>"
  }'
```

## Error Responses

Ephemera returns JSON errors for API requests:

```json
{
  "error": "message describing the problem",
  "status": 400
}
```

Common statuses:

- `400`: invalid content for the selected kind, such as malformed JSON string content or image content without `src`.
- `401`: missing or invalid API key when write authentication is enabled.
- `404`: artifact was not found or has expired on API read endpoints.
- `410`: artifact browser page or download has expired or was removed.
- `413`: artifact content exceeds the server's maximum payload size.
- `422`: request validation failed, such as an unsupported `kind`, missing required field, or invalid `ttl_minutes`.

Validation errors include a `detail` array from the API framework:

```json
{
  "error": "invalid request",
  "status": 422,
  "detail": []
}
```

## Tips

- TTL defaults are controlled by the server, commonly 60 minutes. Send `ttl_minutes` explicitly when the artifact must live longer or shorter.
- Server operators can cap TTL with `MAX_TTL_MINUTES`; requests above that cap return `400`.
- Maximum content size is controlled by `MAX_CONTENT_BYTES`, defaulting to 5 MiB. Large screenshots should usually be linked as image URLs rather than embedded as huge data URLs.
- The returned `url` is the share link. Anyone who has it can view the artifact until it expires.
- Treat artifact URLs as bearer links. Do not post secrets unless the Ephemera instance and sharing channel are trusted.
- For automation, parse the create response and print or store only `.url` when a human needs to inspect the artifact.
