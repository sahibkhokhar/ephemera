"""Curated example artifacts used to showcase the viewer on the landing page.

Each :class:`Example` is a real, representative payload — the kind of output an
agent or CI job actually produces — so the gallery demonstrates the product
instead of showing filler. Visiting ``/examples/{slug}`` materialises one as a
normal, expiring artifact, so examples exercise exactly the same code path as
anything posted through the API.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Example", "EXAMPLES", "EXAMPLES_BY_SLUG"]


@dataclass(frozen=True, slots=True)
class Example:
    slug: str
    kind: str
    title: str
    summary: str  # one-line blurb shown on the gallery card
    content: Any
    metadata: dict[str, Any] = field(default_factory=dict)


# --- individual payloads --------------------------------------------------

_CI_LOG = """\
[09:24:01] ▶ pipeline start · commit a3f9c2e · branch main
[09:24:01]   runner: ubuntu-22.04 · 4 vCPU · 16 GB
[09:24:02] ── stage: install ─────────────────────────────
[09:24:02]   $ npm ci --no-audit
[09:24:19]   added 1,284 packages in 17s
[09:24:19] ✓ install finished in 17.2s
[09:24:19] ── stage: lint ────────────────────────────────
[09:24:19]   $ npm run lint
[09:24:27]   ✓ eslint: 0 errors, 0 warnings (412 files)
[09:24:27] ✓ lint finished in 7.9s
[09:24:27] ── stage: test ────────────────────────────────
[09:24:27]   $ npm run test -- --coverage
[09:24:51]   PASS  src/auth/token.test.ts (38 tests)
[09:24:58]   PASS  src/billing/invoice.test.ts (54 tests)
[09:25:06]   WARN  src/legacy/parser.test.ts: 1 test marked todo
[09:25:11]   PASS  src/api/routes.test.ts (71 tests)
[09:25:11]   Tests: 411 passed, 1 todo, 412 total
[09:25:11]   Coverage: 92.4% statements · 88.1% branches
[09:25:11] ✓ test finished in 44.0s
[09:25:11] ── stage: build ───────────────────────────────
[09:25:11]   $ npm run build
[09:25:39]   compiled client (2.1 MB → 684 KB gzip)
[09:25:44]   compiled server (1.4 MB)
[09:25:44] ✓ build finished in 33.1s
[09:25:44] ── stage: deploy ──────────────────────────────
[09:25:44]   pushing image registry.internal/web:a3f9c2e
[09:26:02]   rollout web-7c9d → 3/3 replicas ready
[09:26:08] ✓ deploy finished in 24.0s
[09:26:08] ◼ pipeline succeeded in 2m07s
"""

_K8S_JSON = {
    "apiVersion": "v1",
    "kind": "Pod",
    "metadata": {
        "name": "web-7c9d4f8b6-q2xkv",
        "namespace": "production",
        "labels": {"app": "web", "version": "a3f9c2e", "tier": "frontend"},
    },
    "status": {
        "phase": "Running",
        "hostIP": "10.0.4.17",
        "podIP": "10.244.2.31",
        "startTime": "2026-06-09T09:26:02Z",
        "containerStatuses": [
            {
                "name": "web",
                "ready": True,
                "restartCount": 0,
                "image": "registry.internal/web:a3f9c2e",
                "state": {"running": {"startedAt": "2026-06-09T09:26:05Z"}},
                "resources": {
                    "requests": {"cpu": "250m", "memory": "256Mi"},
                    "limits": {"cpu": "1", "memory": "512Mi"},
                },
            }
        ],
        "conditions": [
            {"type": "Ready", "status": "True"},
            {"type": "ContainersReady", "status": "True"},
        ],
    },
}

_POSTMORTEM = """\
# Incident 2026-06-04 · Checkout latency spike

**Severity:** SEV-2 &nbsp;·&nbsp; **Duration:** 23 min &nbsp;·&nbsp; **Customer impact:** ~4% of checkouts delayed

## Summary

A connection-pool exhaustion in the payments service caused p95 checkout
latency to climb from **240 ms** to **6.8 s** for 23 minutes. No orders were
lost; affected requests eventually succeeded on retry.

## Timeline (UTC)

| Time  | Event |
| ----- | ----- |
| 14:02 | Deploy `payments@v3.8.1` rolls out to production |
| 14:09 | p95 latency alert fires for `/checkout` |
| 14:13 | On-call confirms healthy pods but saturated DB pool |
| 14:21 | Pool size raised 20 → 60; latency begins recovering |
| 14:25 | p95 back under 300 ms; incident resolved |

## Root cause

`v3.8.1` introduced a synchronous fraud-check call that held a database
connection for the full request. Under peak load the fixed pool of 20
connections was exhausted, so new requests queued:

```python
# before — connection held across the network call
with pool.acquire() as conn:
    record = conn.fetch(order_id)
    score = fraud_api.check(record)   # ~400ms, blocking
    conn.update(order_id, score)
```

## Action items

- [x] Raise pool size and add saturation alerting
- [ ] Move fraud check outside the connection scope
- [ ] Add a load test that holds connections under concurrency

> **Lesson:** never hold a pooled resource across an external network call.
"""

_COVERAGE_REPORT = """\
<h1>Coverage report</h1>
<p class="muted">Generated for <code>web@a3f9c2e</code> on 2026-06-09 · 411 tests, 44.0s</p>
<table>
  <thead>
    <tr><th>Module</th><th align="right">Statements</th><th align="right">Branches</th><th align="right">Functions</th></tr>
  </thead>
  <tbody>
    <tr><td><code>src/api</code></td><td align="right">96.2%</td><td align="right">91.4%</td><td align="right">98.0%</td></tr>
    <tr><td><code>src/auth</code></td><td align="right">99.1%</td><td align="right">95.7%</td><td align="right">100%</td></tr>
    <tr><td><code>src/billing</code></td><td align="right">93.8%</td><td align="right">88.0%</td><td align="right">94.5%</td></tr>
    <tr><td><code>src/legacy</code></td><td align="right">71.3%</td><td align="right">58.9%</td><td align="right">66.7%</td></tr>
    <tr><td><strong>Total</strong></td><td align="right"><strong>92.4%</strong></td><td align="right"><strong>88.1%</strong></td><td align="right"><strong>94.0%</strong></td></tr>
  </tbody>
</table>
<h2>Files needing attention</h2>
<ul>
  <li><code>src/legacy/parser.ts</code> — 58.9% branches; 3 untested error paths</li>
  <li><code>src/billing/proration.ts</code> — 1 uncovered edge case (annual → monthly)</li>
</ul>
<p>Full HTML and lcov output are attached to the pipeline run. This report is
rendered through the same allow-list sanitizer used for every rich artifact, so
inline scripts and event handlers are stripped before display.</p>
"""

# A genuinely long file so the line-numbered preview has something to show off.
_NGINX_CONF = """\
# /etc/nginx/conf.d/edge.conf — reverse proxy for the artifact viewer
# Managed by Ansible. Do not edit by hand; changes will be overwritten.

user                nginx;
worker_processes    auto;
worker_rlimit_nofile 65535;

events {
    worker_connections  4096;
    multi_accept        on;
}

http {
    include             /etc/nginx/mime.types;
    default_type        application/octet-stream;
    charset             utf-8;

    sendfile            on;
    tcp_nopush          on;
    tcp_nodelay         on;
    keepalive_timeout   65;
    server_tokens       off;

    # ---- logging ---------------------------------------------------------
    log_format  main  '$remote_addr - $remote_user [$time_local] '
                      '"$request" $status $body_bytes_sent '
                      '"$http_referer" "$http_user_agent" rt=$request_time';
    access_log  /var/log/nginx/access.log  main  buffer=32k  flush=5s;
    error_log   /var/log/nginx/error.log   warn;

    # ---- tuning ----------------------------------------------------------
    client_max_body_size        8m;
    client_body_buffer_size     128k;
    proxy_read_timeout          30s;
    proxy_connect_timeout       5s;

    gzip                on;
    gzip_comp_level     5;
    gzip_min_length     256;
    gzip_proxied        any;
    gzip_types          text/plain text/css application/json
                        application/javascript image/svg+xml;

    # ---- upstream --------------------------------------------------------
    upstream artifact_viewer {
        least_conn;
        server 10.0.4.17:8000 max_fails=3 fail_timeout=15s;
        server 10.0.4.18:8000 max_fails=3 fail_timeout=15s;
        keepalive 32;
    }

    # ---- redirect http → https ------------------------------------------
    server {
        listen      80;
        listen      [::]:80;
        server_name artifacts.example.com;
        return      301 https://$host$request_uri;
    }

    # ---- tls termination -------------------------------------------------
    server {
        listen              443 ssl http2;
        listen              [::]:443 ssl http2;
        server_name         artifacts.example.com;

        ssl_certificate     /etc/letsencrypt/live/artifacts/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/artifacts/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;
        ssl_session_cache   shared:SSL:10m;
        ssl_session_timeout 1d;

        add_header Strict-Transport-Security "max-age=63072000" always;

        location /static/ {
            proxy_pass         http://artifact_viewer;
            proxy_cache_valid  200 1h;
            expires            1h;
            add_header         Cache-Control "public";
        }

        location / {
            proxy_pass          http://artifact_viewer;
            proxy_http_version  1.1;
            proxy_set_header    Host              $host;
            proxy_set_header    X-Real-IP         $remote_addr;
            proxy_set_header    X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header    X-Forwarded-Proto $scheme;
            proxy_set_header    Connection        "";
        }

        location = /healthz {
            proxy_pass    http://artifact_viewer;
            access_log    off;
        }
    }
}
"""


def _latency_chart_svg() -> str:
    """A self-contained SVG bar chart (no external assets, CSP-safe as data:)."""
    bars = [
        ("Mon", 212), ("Tue", 198), ("Wed", 240), ("Thu", 226),
        ("Fri", 690), ("Sat", 254), ("Sun", 231),
    ]
    peak = max(v for _, v in bars)
    # top_y leaves headroom below the title so the tallest bar's value label
    # never crowds the heading.
    base_y, top_y = 250, 70
    span = base_y - top_y
    cols = []
    for i, (label, value) in enumerate(bars):
        x = 70 + i * 64
        h = round(span * value / peak)
        y = base_y - h
        fill = "#3a5bd9" if value < 400 else "#b4322a"
        cols.append(
            f'<rect x="{x}" y="{y}" width="38" height="{h}" rx="4" fill="{fill}"/>'
            f'<text x="{x + 19}" y="{base_y + 20}" text-anchor="middle" '
            f'font-size="13" fill="#5a616e">{label}</text>'
            f'<text x="{x + 19}" y="{y - 8}" text-anchor="middle" '
            f'font-size="12" fill="#1a1d24">{value}</text>'
        )
    grid = "".join(
        f'<line x1="64" y1="{top_y + span * f}" x2="520" y2="{top_y + span * f}" '
        f'stroke="#e3e6ec"/>'
        for f in (0, 0.25, 0.5, 0.75, 1)
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="300" '
        'viewBox="0 0 560 300" font-family="system-ui, sans-serif">'
        '<rect width="560" height="300" fill="#ffffff"/>'
        '<text x="32" y="30" font-size="16" font-weight="600" fill="#1a1d24">'
        'Checkout p95 latency</text>'
        '<text x="32" y="48" font-size="12" fill="#5a616e">last 7 days</text>'
        f'{grid}{"".join(cols)}'
        f'<line x1="64" y1="{base_y}" x2="520" y2="{base_y}" stroke="#d2d6df"/>'
        '</svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return "data:image/svg+xml;base64," + encoded


EXAMPLES: list[Example] = [
    Example(
        slug="ci-log",
        kind="log",
        title="CI pipeline run · web@a3f9c2e",
        summary="A full build log — install, lint, test, build, deploy — with timing and a warning.",
        content=_CI_LOG,
        metadata={"source": "example"},
    ),
    Example(
        slug="pod-json",
        kind="json",
        title="Pod status · kubectl -o json",
        summary="A nested Kubernetes pod status, pretty-printed and key-sorted for scanning.",
        content=_K8S_JSON,
        metadata={"source": "example"},
    ),
    Example(
        slug="postmortem",
        kind="markdown",
        title="Incident postmortem · checkout latency",
        summary="Markdown with a timeline table, fenced code, task list, and a callout.",
        content=_POSTMORTEM,
        metadata={"source": "example"},
    ),
    Example(
        slug="latency-chart",
        kind="image",
        title="Checkout latency · last 7 days",
        summary="An inline SVG chart served as a self-contained data URL — no external assets.",
        content={
            "src": _latency_chart_svg(),
            "alt": "Bar chart of daily p95 checkout latency, with Friday spiking to 690ms",
            "caption": "Friday's deploy spiked p95 to 690 ms before the pool fix landed.",
        },
        metadata={"source": "example"},
    ),
    Example(
        slug="coverage-report",
        kind="report",
        title="Coverage report · web@a3f9c2e",
        summary="A rich HTML report with tables, run through the allow-list sanitizer.",
        content=_COVERAGE_REPORT,
        metadata={"source": "example"},
    ),
    Example(
        slug="nginx-conf",
        kind="text",
        title="edge.conf · nginx reverse proxy",
        summary="A long config file — the line-numbered viewer keeps it easy to reference.",
        content=_NGINX_CONF,
        metadata={"source": "example"},
    ),
]

EXAMPLES_BY_SLUG: dict[str, Example] = {ex.slug: ex for ex in EXAMPLES}
