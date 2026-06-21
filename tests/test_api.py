from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from artifact_viewer.config import Settings
from artifact_viewer.examples import EXAMPLES
from artifact_viewer.main import create_app


def make_client(tmp_path: Path, **overrides) -> TestClient:
    settings = Settings(db_path=tmp_path / "artifacts.db", base_url="http://lan-test", **overrides)
    return TestClient(create_app(settings))


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return make_client(tmp_path)


def create(client: TestClient, **payload):
    body = {"title": "t", "kind": "text", "content": "x", "ttl_minutes": 10}
    body.update(payload)
    return client.post("/api/artifacts", json=body)


# ---- core lifecycle ------------------------------------------------------


def test_create_returns_canonical_url(client: TestClient):
    res = create(client, kind="log", content="hello\nworld")
    assert res.status_code == 201
    body = res.json()
    assert body["id"]
    assert body["url"] == f"http://lan-test/a/{body['id']}"
    assert body["kind"] == "log"


def test_view_text_artifact_shows_content(client: TestClient):
    artifact_id = create(client, kind="log", content="hello\nworld").json()["id"]
    view = client.get(f"/a/{artifact_id}")
    assert view.status_code == 200
    assert "text/html" in view.headers["content-type"]
    assert "hello" in view.text and "world" in view.text


def test_raw_and_detail_endpoints(client: TestClient):
    artifact_id = create(client, kind="text", content="payload").json()["id"]
    raw = client.get(f"/a/{artifact_id}/raw")
    detail = client.get(f"/api/artifacts/{artifact_id}")
    assert raw.status_code == detail.status_code == 200
    assert raw.json()["content"] == "payload"
    assert detail.json()["content"] == "payload"


def test_json_string_content_is_parsed(client: TestClient):
    artifact_id = create(client, kind="json", content='{"b": 2, "a": 1}').json()["id"]
    view = client.get(f"/a/{artifact_id}")
    # rendered in the page (HTML-escaped by autoescape), pretty-printed and key-sorted
    assert "&#34;a&#34;: 1" in view.text
    assert view.text.index("&#34;a&#34;: 1") < view.text.index("&#34;b&#34;: 2")
    # and available un-escaped via the raw API
    assert client.get(f"/api/artifacts/{artifact_id}").json()["content"] == {"a": 1, "b": 2}


def test_json_invalid_string_rejected(client: TestClient):
    res = create(client, kind="json", content="{not json}")
    assert res.status_code == 400


def test_markdown_is_rendered(client: TestClient):
    artifact_id = create(client, kind="markdown", content="# Title\n\n- one\n- two").json()["id"]
    view = client.get(f"/a/{artifact_id}")
    assert "<h1" in view.text and "Title" in view.text
    assert "<li>one</li>" in view.text or "<li>one" in view.text


# ---- images --------------------------------------------------------------


def test_image_data_url_string(client: TestClient):
    data_url = "data:image/png;base64," + base64.b64encode(b"img").decode()
    artifact_id = create(client, kind="image", content=data_url).json()["id"]
    view = client.get(f"/a/{artifact_id}")
    assert data_url in view.text


def test_image_dict_requires_src(client: TestClient):
    assert create(client, kind="image", content={"alt": "x"}).status_code == 400


def test_image_dict_caption(client: TestClient):
    res = create(client, kind="image", content={"src": "https://x/y.png", "caption": "a chart"})
    view = client.get(f"/a/{res.json()['id']}")
    assert "a chart" in view.text


# ---- security ------------------------------------------------------------


def test_report_html_is_sanitized(client: TestClient):
    malicious = '<h1>Safe</h1><script>alert(1)</script><a href="javascript:alert(1)">x</a><p>kept</p>'
    artifact_id = create(client, kind="report", content=malicious).json()["id"]
    view = client.get(f"/a/{artifact_id}")
    assert "<script>" not in view.text
    assert "javascript:" not in view.text
    assert "Safe" in view.text and "kept" in view.text


def test_security_headers_present(client: TestClient):
    res = client.get("/")
    csp = res.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"


# ---- limits & validation -------------------------------------------------


def test_ttl_over_max_rejected(tmp_path: Path):
    client = make_client(tmp_path, max_ttl_minutes=60)
    assert create(client, ttl_minutes=120).status_code == 400


def test_ttl_defaults_when_omitted(tmp_path: Path):
    client = make_client(tmp_path, default_ttl_minutes=42)
    res = client.post("/api/artifacts", json={"kind": "text", "content": "x"})
    assert res.status_code == 201


def test_content_too_large_rejected(tmp_path: Path):
    client = make_client(tmp_path, max_content_bytes=64)
    assert create(client, content="x" * 200).status_code == 413


def test_unknown_kind_rejected(client: TestClient):
    assert create(client, kind="pdf").status_code == 422


# ---- auth ----------------------------------------------------------------


def test_api_key_required_when_set(tmp_path: Path):
    client = make_client(tmp_path, api_key="secret")
    assert create(client).status_code == 401
    wrong = client.post("/api/artifacts", json={"kind": "text", "content": "x"}, headers={"x-api-key": "nope"})
    assert wrong.status_code == 401


def test_api_key_accepts_valid_key(tmp_path: Path):
    client = make_client(tmp_path, api_key="secret")
    res = client.post(
        "/api/artifacts",
        json={"kind": "text", "content": "x"},
        headers={"x-api-key": "secret"},
    )
    assert res.status_code == 201
    bearer = client.post(
        "/api/artifacts",
        json={"kind": "text", "content": "x"},
        headers={"authorization": "Bearer secret"},
    )
    assert bearer.status_code == 201


def test_api_key_does_not_block_public_view(tmp_path: Path):
    client = make_client(tmp_path, api_key="secret")
    artifact_id = client.post(
        "/api/artifacts", json={"kind": "text", "content": "x"}, headers={"x-api-key": "secret"}
    ).json()["id"]
    assert client.get(f"/a/{artifact_id}").status_code == 200


# ---- expiry & errors -----------------------------------------------------


def test_expired_artifact_is_gone(client: TestClient):
    artifact_id = create(client, ttl_minutes=1).json()["id"]
    store = client.app.state.store
    with store._connect() as conn:
        conn.execute("UPDATE artifacts SET expires_at = '2000-01-01T00:00:00Z' WHERE id = ?", (artifact_id,))
        conn.commit()
    assert client.get(f"/a/{artifact_id}").status_code == 410
    assert client.get(f"/api/artifacts/{artifact_id}").status_code == 404
    assert store.count() == 0


def test_browser_404_renders_html(client: TestClient):
    res = client.get("/a/doesnotexist")
    assert res.status_code == 410
    assert "text/html" in res.headers["content-type"]
    assert "Gone" in res.text


def test_api_404_returns_json(client: TestClient):
    res = client.get("/api/artifacts/doesnotexist")
    assert res.status_code == 404
    assert res.json()["status"] == 404


def test_healthz(client: TestClient):
    assert client.get("/healthz").json()["status"] == "ok"


# ---- API docs ------------------------------------------------------------


def test_api_docs_renders_self_hosted_html(client: TestClient):
    res = client.get("/api/docs")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    # self-hosted: no external CDN assets, and not an empty page
    assert "cdn" not in res.text.lower()
    assert "API reference" in res.text
    # documents the key API paths and links to the schema
    for path in ("/api/artifacts", "/api/artifacts/{id}", "/api/openapi.json", "/healthz"):
        assert path in res.text


def test_api_docs_notes_auth_when_key_set(tmp_path: Path):
    client = make_client(tmp_path, api_key="secret")
    res = client.get("/api/docs")
    assert res.status_code == 200
    assert "x-api-key" in res.text


def test_openapi_schema_served(client: TestClient):
    res = client.get("/api/openapi.json")
    assert res.status_code == 200
    assert res.json()["openapi"]
    assert "/api/artifacts" in res.json()["paths"]


# ---- examples gallery ----------------------------------------------------


def test_index_shows_instance_dashboard(client: TestClient):
    res = client.get("/")
    assert res.status_code == 200
    assert "Your Ephemera instance" in res.text
    assert "Recent artifacts" in res.text
    assert "Example artifacts" in res.text
    assert "Create an artifact" in res.text
    assert "POST /api/artifacts" in res.text
    assert "default TTL" in res.text
    for ex in EXAMPLES:
        assert f"/examples/{ex.slug}" in res.text
        assert ex.title in res.text


def test_artifact_page_live_expiry(client: TestClient):
    artifact_id = create(client, kind="log", content="line 1").json()["id"]
    res = client.get(f"/a/{artifact_id}")
    assert res.status_code == 200
    assert 'data-expires="' in res.text


@pytest.mark.parametrize("slug", [ex.slug for ex in EXAMPLES])
def test_example_opens_real_artifact(client: TestClient, slug):
    # /examples/{slug} materializes a normal artifact and redirects to its page
    res = client.get(f"/examples/{slug}", follow_redirects=False)
    assert res.status_code == 302
    location = res.headers["location"]
    assert location.startswith("/a/")
    view = client.get(location)
    assert view.status_code == 200


def test_example_materializes_through_normal_store(client: TestClient):
    before = client.app.state.store.count()
    client.get("/examples/ci-log", follow_redirects=False)
    assert client.app.state.store.count() == before + 1


def test_unknown_example_404s(client: TestClient):
    assert client.get("/examples/not-a-real-slug").status_code == 404


def test_demo_redirects_to_artifact(client: TestClient):
    res = client.get("/demo", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"].startswith("/a/")


def test_index_lists_recent(client: TestClient):
    create(client, title="Findable artifact", kind="text", content="x")
    res = client.get("/")
    assert res.status_code == 200
    assert "Findable artifact" in res.text


def test_artifact_page_offers_copy_exports(client: TestClient):
    # Markdown/report: no Copy JSON / Copy MD header buttons (rich-content cleanup)
    artifact_id = create(client, kind="markdown", content="# Demo\n\nbody").json()["id"]
    view = client.get(f"/a/{artifact_id}")
    assert view.status_code == 200
    assert "Copy JSON" not in view.text
    assert "Copy MD" not in view.text
    # Hidden copy-source textareas are still embedded for JS use
    assert "data-format=\"json\"" in view.text
    assert "data-format=\"markdown\"" in view.text

    # Non-rich kinds (e.g. json) still show the header copy buttons
    json_id = create(client, kind="json", content='{"x":1}').json()["id"]
    json_view = client.get(f"/a/{json_id}")
    assert json_view.status_code == 200
    assert "Copy JSON" in json_view.text


def _copy_source(html: str, fmt: str) -> str:
    """Decode a base64-encoded copy-source textarea out of the artifact page."""
    import re

    match = re.search(
        rf'data-format="{fmt}" data-encoded="base64" hidden>([^<]*)<', html
    )
    assert match, f"no copy-source for format {fmt!r}"
    return base64.b64decode(match.group(1)).decode("utf-8")


@pytest.mark.parametrize(
    "kind, content, json_needle, md_needle",
    [
        ("text", "plain text\nline2", '"content": "plain text\\nline2"', "```text\nplain text"),
        ("json", '{"b": 2, "a": 1}', '"a": 1', "```json"),
        ("markdown", "# H\n\nbody", '"content": "# H\\n\\nbody"', "\n# H\n"),
        ("report", "<h1>Safe</h1><p>kept</p>", '"kind": "report"', "```html\n<h1>Safe</h1>"),
    ],
)
def test_copy_exports_per_kind(client: TestClient, kind, content, json_needle, md_needle):
    artifact_id = create(client, kind=kind, content=content).json()["id"]
    html = client.get(f"/a/{artifact_id}").text
    json_export = _copy_source(html, "json")
    md_export = _copy_source(html, "markdown")
    assert json_needle in json_export
    assert f"- Kind: {kind}" in md_export
    assert md_needle in md_export


def test_copy_exports_image_kind(client: TestClient):
    artifact_id = create(
        client, kind="image", content={"src": "https://x/y.png", "alt": "A", "caption": "cap"}
    ).json()["id"]
    html = client.get(f"/a/{artifact_id}").text
    assert '"src": "https://x/y.png"' in _copy_source(html, "json")
    md_export = _copy_source(html, "markdown")
    assert "![A](https://x/y.png)" in md_export
    assert "> cap" in md_export


# ---- download endpoint ---------------------------------------------------


def _disposition(res) -> str:
    return res.headers.get("content-disposition", "")


def test_download_text_is_attachment(client: TestClient):
    artifact_id = create(client, kind="text", title="My Notes", content="line one\nline two").json()["id"]
    res = client.get(f"/a/{artifact_id}/download")
    assert res.status_code == 200
    assert "attachment" in _disposition(res)
    assert _disposition(res).endswith('my-notes.txt"')
    assert res.headers["content-type"].startswith("text/plain")
    assert res.text == "line one\nline two"


def test_download_log_uses_log_extension(client: TestClient):
    artifact_id = create(client, kind="log", content="WARN something").json()["id"]
    res = client.get(f"/a/{artifact_id}/download")
    assert res.status_code == 200
    assert ".log\"" in _disposition(res)


def test_download_json_returns_bare_content(client: TestClient):
    artifact_id = create(client, kind="json", content='{"b": 2, "a": 1}').json()["id"]
    res = client.get(f"/a/{artifact_id}/download")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/json")
    assert ".json\"" in _disposition(res)
    # bare content value, not the wrapped artifact detail
    assert res.json() == {"a": 1, "b": 2}


def test_download_markdown_source(client: TestClient):
    artifact_id = create(client, kind="markdown", content="# H\n\nbody").json()["id"]
    res = client.get(f"/a/{artifact_id}/download")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    assert ".md\"" in _disposition(res)
    assert res.text == "# H\n\nbody"


def test_download_report_is_sanitized_html(client: TestClient):
    malicious = '<h1>Safe</h1><script>alert(1)</script><p>kept</p>'
    artifact_id = create(client, kind="report", content=malicious).json()["id"]
    res = client.get(f"/a/{artifact_id}/download")
    assert res.status_code == 200
    assert "attachment" in _disposition(res)
    assert ".html\"" in _disposition(res)
    assert "<script>" not in res.text
    assert "Safe" in res.text and "kept" in res.text


def test_download_image_data_url_decodes_bytes(client: TestClient):
    raw = b"\x89PNG\r\n\x1a\nfake-bytes"
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode()
    artifact_id = create(client, kind="image", content=data_url).json()["id"]
    res = client.get(f"/a/{artifact_id}/download")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/png")
    assert ".png\"" in _disposition(res)
    assert res.content == raw


def test_download_remote_image_redirects_not_proxied(client: TestClient):
    src = "https://example.com/chart.png"
    artifact_id = create(client, kind="image", content={"src": src, "alt": "c"}).json()["id"]
    res = client.get(f"/a/{artifact_id}/download", follow_redirects=False)
    # SSRF guard: we redirect to the source rather than fetching it server-side.
    assert res.status_code == 302
    assert res.headers["location"] == src


def test_download_missing_artifact_410(client: TestClient):
    assert client.get("/a/nope/download").status_code == 410


# ---- per-kind action buttons ---------------------------------------------


def test_log_page_has_log_actions(client: TestClient):
    artifact_id = create(client, kind="log", content="ok\nERROR boom").json()["id"]
    html = client.get(f"/a/{artifact_id}").text
    assert 'data-action="toggle-wrap"' in html
    assert 'data-action="log-highlight"' in html
    assert 'data-action="log-filter"' in html
    assert 'data-action="log-jump"' in html
    assert "data-log" in html


def test_json_page_has_copy_raw_and_download(client: TestClient):
    artifact_id = create(client, kind="json", content='{"a": 1}').json()["id"]
    html = client.get(f"/a/{artifact_id}").text
    assert "Copy raw payload" in html
    assert f"/a/{artifact_id}/download" in html
    assert "Download JSON" in html


def test_markdown_page_has_preview_code_tabs(client: TestClient):
    artifact_id = create(client, kind="markdown", content="# H").json()["id"]
    html = client.get(f"/a/{artifact_id}").text
    assert 'data-view-tabs' in html
    assert 'data-tab="rendered"' in html
    assert 'data-tab="source"' in html
    assert 'data-action="toggle-source"' not in html
    assert 'data-copy-format="source"' in html
    assert 'data-view="source"' in html
    assert "Download .md" in html


def test_report_page_has_print_and_preview_code_tabs(client: TestClient):
    artifact_id = create(client, kind="report", content="<p>hi</p>").json()["id"]
    html = client.get(f"/a/{artifact_id}").text
    assert 'data-action="print"' in html
    assert 'data-view-tabs' in html
    assert 'data-tab="rendered"' in html
    assert 'data-tab="source"' in html
    assert 'data-action="toggle-source"' not in html


def test_image_page_has_image_actions(client: TestClient):
    artifact_id = create(
        client, kind="image", content={"src": "https://x/y.png", "alt": "A"}
    ).json()["id"]
    html = client.get(f"/a/{artifact_id}").text
    assert 'data-action="zoom"' in html
    assert "Copy src" in html
    assert 'data-format="img-md"' in html
    assert "![A](https://x/y.png)" in html


def test_report_source_not_leaked_as_plaintext(client: TestClient):
    # The rendered+source views must never expose an unsanitized javascript: URL
    # as plain text; the source view is base64-encoded and decoded client-side.
    malicious = '<a href="javascript:alert(1)">x</a><p>kept</p>'
    artifact_id = create(client, kind="report", content=malicious).json()["id"]
    html = client.get(f"/a/{artifact_id}").text
    assert "javascript:" not in html
    assert "kept" in html
