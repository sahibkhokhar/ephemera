from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .rendering import render_artifact
from .store import ArtifactStore


class ArtifactCreateRequest(BaseModel):
    title: str = Field(default="Untitled artifact", min_length=1, max_length=160)
    kind: Literal["text", "log", "json", "markdown", "image", "report"]
    content: Any
    ttl_minutes: int = Field(default=60, ge=1, le=10080)
    metadata: dict[str, Any] | None = None

    @field_validator("metadata")
    @classmethod
    def normalize_metadata(cls, value):
        return value or {}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_url(request: Request, path: str, base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/") + path
    return str(request.base_url).rstrip("/") + path


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.ensure_dirs()
    store = ArtifactStore(settings.db_path)
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

    stop_event = threading.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        def cleanup_loop() -> None:
            while not stop_event.wait(settings.cleanup_interval_seconds):
                store.cleanup_expired()

        thread = threading.Thread(target=cleanup_loop, name="artifact-cleanup", daemon=True)
        thread.start()
        try:
            store.cleanup_expired()
            yield
        finally:
            stop_event.set()
            thread.join(timeout=2)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.store = store
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "static")), name="static")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "time": iso_now()}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        recent = store.list_recent(limit=6)
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "settings": settings,
                "recent": recent,
                "base_url": settings.base_url or str(request.base_url).rstrip("/"),
            },
        )

    @app.post("/api/artifacts")
    def create_artifact(payload: ArtifactCreateRequest, request: Request):
        stored_content = payload.content
        if payload.kind == "json" and isinstance(payload.content, str):
            try:
                stored_content = json.loads(payload.content)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"json artifact content must be valid JSON: {exc.msg}") from exc
        if payload.kind == "image":
            if isinstance(payload.content, dict):
                if "src" not in payload.content:
                    raise HTTPException(status_code=400, detail="image content must include src")
            elif isinstance(payload.content, str):
                stored_content = {"src": payload.content, "alt": (payload.metadata or {}).get("alt", "Artifact image")}
            else:
                raise HTTPException(status_code=400, detail="image content must be a data URL string or {src, alt?}")
        artifact = store.create(
            title=payload.title,
            kind=payload.kind,
            content=stored_content,
            ttl_minutes=payload.ttl_minutes,
            metadata=payload.metadata or {},
        )
        public_path = f"/a/{artifact.id}"
        response = {
            "id": artifact.id,
            "kind": artifact.kind,
            "title": artifact.title,
            "created_at": artifact.created_at.isoformat().replace("+00:00", "Z"),
            "expires_at": artifact.expires_at.isoformat().replace("+00:00", "Z"),
            "url": build_url(request, public_path, settings.base_url),
        }
        return JSONResponse(response, status_code=status.HTTP_201_CREATED)

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact_api(artifact_id: str, request: Request):
        artifact = store.get(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact not found or expired")
        return {
            "id": artifact.id,
            "title": artifact.title,
            "kind": artifact.kind,
            "content": artifact.content,
            "metadata": artifact.metadata,
            "created_at": artifact.created_at.isoformat().replace("+00:00", "Z"),
            "expires_at": artifact.expires_at.isoformat().replace("+00:00", "Z"),
            "url": build_url(request, f"/a/{artifact.id}", settings.base_url),
        }

    @app.get("/a/{artifact_id}", response_class=HTMLResponse)
    def view_artifact(artifact_id: str, request: Request):
        artifact = store.get(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=410, detail="artifact expired or removed")
        rendered = render_artifact(artifact.kind, artifact.content)
        return templates.TemplateResponse(
            request,
            "artifact.html",
            {
                "settings": settings,
                "artifact": artifact,
                "rendered": rendered,
                "base_url": settings.base_url or str(request.base_url).rstrip("/"),
            },
        )

    @app.get("/a/{artifact_id}/raw")
    def raw_artifact(artifact_id: str):
        artifact = store.get(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact not found or expired")
        return {
            "id": artifact.id,
            "kind": artifact.kind,
            "title": artifact.title,
            "content": artifact.content,
            "metadata": artifact.metadata,
            "created_at": artifact.created_at.isoformat().replace("+00:00", "Z"),
            "expires_at": artifact.expires_at.isoformat().replace("+00:00", "Z"),
        }

    @app.get("/demo")
    def demo() -> RedirectResponse:
        artifact = store.create(
            title="Demo: system summary",
            kind="markdown",
            content=(
                "# Artifact Viewer Demo\n\n"
                "- Clean server-rendered pages\n"
                "- Temporary links with TTL\n"
                "- Good for data that is annoying in chat\n\n"
                "```json\n{\n  \"status\": \"ok\",\n  \"surface\": \"markdown\"\n}\n```"
            ),
            ttl_minutes=60,
            metadata={"source": "demo"},
        )
        return RedirectResponse(url=f"/a/{artifact.id}", status_code=302)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("artifact_viewer.main:app", host="0.0.0.0", port=8000, reload=False)
