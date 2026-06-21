# Ephemera API reference

Base URL: `$EPHEMERA_URL` · Instance docs: `$EPHEMERA_URL/api/docs`

## Authentication

When writes require a key:

```bash
-H "x-api-key: $EPHEMERA_API_KEY"
# or
-H "Authorization: Bearer $EPHEMERA_API_KEY"
```

Reads (viewing artifact URLs) stay public.

## Upload a file (preferred)

```http
POST /api/artifacts/upload?kind=log&title=CI%20log&ttl_minutes=120
Content-Type: text/plain

<raw file bytes>
```

Query params: `kind` (required), optional `title`, `filename`, `ttl_minutes`.

| kind | Body |
| --- | --- |
| `text`, `log`, `markdown`, `report` | UTF-8 text |
| `json` | Valid JSON document |
| `image` | Image bytes + matching `image/*` content-type |

```bash
curl -s "$EPHEMERA_URL/api/artifacts/upload?kind=log&title=Pytest%20failure&ttl_minutes=120" \
  -H "content-type: text/plain" \
  "${AUTH_HEADER[@]}" \
  --data-binary @./pytest-output.log
```

Or use `scripts/post.sh log ./pytest-output.log "Pytest failure" 120`.

## JSON create (small inline payloads)

```http
POST /api/artifacts
Content-Type: application/json
```

```json
{
  "title": "Human readable title",
  "kind": "log",
  "content": "artifact content",
  "ttl_minutes": 60
}
```

Fields: `kind` (required), `content` (required), `title`, `ttl_minutes`, `metadata`.

## Successful response

```json
{
  "id": "9f2c1a7b3e4d",
  "kind": "log",
  "title": "Demo log",
  "created_at": "2026-06-20T12:00:00Z",
  "expires_at": "2026-06-20T12:30:00Z",
  "url": "http://192.168.1.50:8000/a/9f2c1a7b3e4d"
}
```

Agents care about: `id`, `url`, `expires_at`.

## Examples by kind

### Log (upload)

```bash
scripts/post.sh log ./build.log "CI pipeline" 120
```

### JSON (inline)

```bash
curl -s "$EPHEMERA_URL/api/artifacts" \
  -H "content-type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{"title":"Deploy metadata","kind":"json","ttl_minutes":240,"content":{"service":"api","status":"ready"}}'
```

### Markdown (inline)

```bash
curl -s "$EPHEMERA_URL/api/artifacts" \
  -H "content-type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{"title":"Incident notes","kind":"markdown","ttl_minutes":1440,"content":"# Notes\n\n- Impact: …"}'
```

### Image (URL in JSON — prefer for large images)

```bash
curl -s "$EPHEMERA_URL/api/artifacts" \
  -H "content-type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{"title":"Chart","kind":"image","content":{"src":"https://…","alt":"Latency chart"}}'
```

### Report (HTML)

Upload with `kind=report` or JSON create with HTML string (sanitized on render).

## Errors

```json
{"error": "message describing the problem", "status": 400}
```

| Status | Meaning |
| --- | --- |
| `400` | Invalid content for kind |
| `401` | Missing or invalid API key |
| `404` | Artifact not found or expired (API read) |
| `410` | Browser page or download expired |
| `413` | Over `MAX_CONTENT_BYTES` (default 5 MiB) |
| `422` | Validation failed (bad kind, missing field) |

## Tips

- TTL default commonly 60 min; send `ttl_minutes` explicitly when needed.
- `MAX_TTL_MINUTES` caps requests above limit → `400`.
- Parse create response; return only `.url` to humans when appropriate.
- Treat URLs as bearer links until expiry.
