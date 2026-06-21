---
name: ephemera
description: >-
  Post logs, JSON, markdown, images, and HTML reports to a self-hosted Ephemera
  instance and return short-lived share links. Use when output is long,
  formatted, or already a file on disk — not for short chat answers. Keywords:
  logs, CI, test failures, stack traces, pytest, build output, reports, curl
  upload, share link.
license: MIT
compatibility: Requires curl and jq. Network access to the operator's self-hosted Ephemera instance (EPHEMERA_URL).
metadata:
  author: sahibkhokhar
  version: "1.0"
  repository: https://github.com/sahibkhokhar/ephemera
---

# Ephemera

Self-hosted **ephemeral artifact viewer**. POST output over HTTP; get a
**short-lived browser URL**. Works in any harness with shell access (Hermes,
Cursor, OpenClaw, Claude Code, etc.) — no plugins required.

Human install: https://github.com/sahibkhokhar/ephemera#quick-start

## Installing

| Harness | How to load |
| --- | --- |
| **Agent Skills** | Copy or clone the `skills/ephemera/` directory |
| **Hermes** | `hermes skills install <owner>/ephemera` when published, or copy `skills/ephemera/` |
| **Cursor** | Copy to `~/.cursor/skills/ephemera/` or `.cursor/skills/ephemera/` |
| **Paste / fetch** | Raw URL: `https://raw.githubusercontent.com/sahibkhokhar/ephemera/main/skills/ephemera/SKILL.md` |

Hermes-specific env setup: [references/hermes.md](references/hermes.md)

## Setup

```bash
EPHEMERA_URL="${EPHEMERA_URL:-http://localhost:8000}"

AUTH_HEADER=()
if [ -n "${EPHEMERA_API_KEY:-}" ]; then
  AUTH_HEADER=(-H "x-api-key: $EPHEMERA_API_KEY")
fi
```

| Variable | Purpose |
| --- | --- |
| `EPHEMERA_URL` | Instance base URL, e.g. `http://192.168.1.50:8000` |
| `EPHEMERA_API_KEY` | Write key when required. Omit when writes are open. |

## When to Use

**Chat** = conversation (Discord, Telegram, WhatsApp, IDE chat, etc.).
**Ephemera** = inspection — long or formatted output, files, shareable links.

**Stay in chat:** short answers (~under 50 lines), in-thread debugging, human
says "just tell me in chat".

**Use Ephemera:** long logs/traces, formatted dumps, file on disk, chat would
flood, human asks for a link, output will be opened in a browser or shared.

**Summary + link:** 2–5 lines in chat **and** the `.url`. Not a bare link.

```
Short answer?              → chat only
File or ~50+ lines?        → Ephemera + summary
Human asked for a link?    → Ephemera
When in doubt: short→chat, long→Ephemera + one-line summary
```

## Rules

1. **Prefer upload** — `scripts/post.sh` or `curl --data-binary @file`. Do not
   read large files into the prompt.
2. **Summary in chat + `.url` in Ephemera.**
3. **Default TTL** — `ttl_minutes=120` for debug output.
4. **Bearer links** — anyone with the URL can read until expiry. No secrets
   unless explicitly asked.

## Quick Reference

| Task | Command |
| --- | --- |
| Health check | `curl -fsS "$EPHEMERA_URL/healthz"` |
| Upload file | `scripts/post.sh log ./output.log "CI log"` |
| JSON create | See [references/api.md](references/api.md) |
| Get share URL | `… \| jq -r .url` |

**Kinds:** `text`, `log`, `json`, `markdown`, `image`, `report` · **Max:** 5 MiB

## Procedure

1. `curl -fsS "$EPHEMERA_URL/healthz"` — instance up?
2. Chat or Ephemera? (see **When to Use**)
3. File on disk → `scripts/post.sh <kind> <file> [title] [ttl]`
4. Small inline → JSON create ([references/api.md](references/api.md))
5. Reply with **summary + `.url`**. Mention `expires_at` when relevant.

## Pitfalls

| Issue | Fix |
| --- | --- |
| **413** | `tail -n 5000 file` then upload; or summarize |
| **401** | Set `EPHEMERA_API_KEY` |
| **400** | Match `kind` to body (JSON parses; image needs `image/*`) |
| Bare URL | Add summary unless asked otherwise |

## Verification

```bash
curl -fsS "$EPHEMERA_URL/healthz"
scripts/post.sh log ./test.log smoke-test 60 | jq -r .url
```

Open the URL — artifact renders until TTL expiry.

Further API detail: [references/api.md](references/api.md)
