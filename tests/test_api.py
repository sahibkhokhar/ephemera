from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from artifact_viewer.config import Settings
from artifact_viewer.main import create_app


def make_client(tmp_path: Path):
    settings = Settings(db_path=tmp_path / "artifacts.db", base_url="http://lan-test")
    app = create_app(settings)
    return TestClient(app)


def test_create_and_fetch_text_artifact(tmp_path: Path):
    client = make_client(tmp_path)
    res = client.post("/api/artifacts", json={"title": "Log", "kind": "log", "content": "hello\nworld", "ttl_minutes": 10})
    assert res.status_code == 201
    body = res.json()
    assert body["id"]
    assert body["url"] == f"http://lan-test/a/{body['id']}"

    view = client.get(f"/a/{body['id']}")
    assert view.status_code == 200
    assert "hello" in view.text
    assert "world" in view.text

    raw = client.get(f"/a/{body['id']}/raw")
    assert raw.status_code == 200
    assert raw.json()["kind"] == "log"


def test_create_and_render_json(tmp_path: Path):
    client = make_client(tmp_path)
    res = client.post("/api/artifacts", json={"title": "JSON", "kind": "json", "content": {"b": 2, "a": 1}, "ttl_minutes": 10})
    assert res.status_code == 201
    artifact_id = res.json()["id"]
    view = client.get(f"/a/{artifact_id}")
    assert view.status_code == 200
    assert '"a": 1' in view.text
    assert '"b": 2' in view.text


def test_image_artifact_accepts_data_url(tmp_path: Path):
    client = make_client(tmp_path)
    pixel = base64.b64encode(b"fakeimage").decode("ascii")
    data_url = f"data:image/png;base64,{pixel}"
    res = client.post("/api/artifacts", json={"title": "Image", "kind": "image", "content": data_url, "ttl_minutes": 10})
    assert res.status_code == 201
    artifact_id = res.json()["id"]
    view = client.get(f"/a/{artifact_id}")
    assert view.status_code == 200
    assert data_url in view.text


def test_report_html_is_sanitized(tmp_path: Path):
    client = make_client(tmp_path)
    malicious = "<h1>Safe</h1><script>alert(1)</script><p>kept</p>"
    res = client.post("/api/artifacts", json={"title": "Report", "kind": "report", "content": malicious, "ttl_minutes": 10})
    assert res.status_code == 201
    artifact_id = res.json()["id"]
    view = client.get(f"/a/{artifact_id}")
    assert view.status_code == 200
    assert "<script>" not in view.text
    assert "Safe" in view.text
    assert "kept" in view.text


def test_expired_artifact_is_gone(tmp_path: Path):
    client = make_client(tmp_path)
    res = client.post("/api/artifacts", json={"title": "Short", "kind": "text", "content": "bye", "ttl_minutes": 1})
    assert res.status_code == 201
    artifact_id = res.json()["id"]
    store = client.app.state.store
    with store._connect() as conn:
        conn.execute("UPDATE artifacts SET expires_at = '2000-01-01T00:00:00Z' WHERE id = ?", (artifact_id,))
        conn.commit()
    assert client.get(f"/a/{artifact_id}").status_code == 410
    assert client.get(f"/api/artifacts/{artifact_id}").status_code == 404
    assert store.count() == 0
