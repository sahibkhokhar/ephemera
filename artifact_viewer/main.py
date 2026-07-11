from __future__ import annotations

import base64
import difflib
import json
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .download import DownloadError, build_download
from .examples import EXAMPLES, EXAMPLES_BY_SLUG
from .rendering import TEXTUAL_KINDS, highlight_line, render_artifact, source_text
from .store import Artifact, ArtifactStore

BASE_DIR = Path(__file__).resolve().parent.parent

# Defense-in-depth for the report/markdown surfaces: even if the HTML sanitizer
# ever missed something, the browser will refuse to run inline or third-party
# scripts on any page we serve.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self'; "
    "font-src 'self'; "
    "script-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)

KIND_LABELS = {
    "text": "Text",
    "log": "Log",
    "json": "JSON",
    "markdown": "Markdown",
    "image": "Image",
    "report": "Report",
}


class ArtifactCreateRequest(BaseModel):
    title: str = Field(default="Untitled artifact", min_length=1, max_length=160)
    kind: Literal["text", "log", "json", "markdown", "image", "report"]
    content: Any
    ttl_minutes: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] | None = None

    @field_validator("metadata")
    @classmethod
    def normalize_metadata(cls, value):
        return value or {}


class ArtifactDiffRequest(BaseModel):
    a: str = Field(min_length=1, max_length=128)
    b: str = Field(min_length=1, max_length=128)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_url(request: Request, path: str, base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/") + path
    return str(request.base_url).rstrip("/") + path


def humanize_remaining(expires_at: datetime) -> str:
    seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    if seconds <= 0:
        return "expired"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours > 0:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    if minutes > 0:
        return f"{minutes}m"
    return f"{seconds}s"


def humanize_bytes(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB"):
        if value < 1024 or unit == "MB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} MB"


def _wants_html(request: Request) -> bool:
    path = request.url.path
    if path.startswith(("/api", "/healthz")) or path.endswith("/raw"):
        return False
    return True


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_dirs()
    store = ArtifactStore(settings.db_path)

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    templates.env.globals.update(
        app_name=settings.app_name,
    )
    templates.env.filters["remaining"] = humanize_remaining
    templates.env.filters["humanbytes"] = humanize_bytes
    templates.env.filters["b64"] = lambda s: base64.b64encode(str(s).encode("utf-8")).decode("ascii")

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

    # docs_url is disabled because FastAPI's bundled Swagger UI pulls its JS/CSS
    # from a CDN, which renders blank on an air-gapped LAN (and is blocked by our
    # script-src 'self' CSP). We serve a self-hosted docs page at /api/docs below.
    app = FastAPI(title=settings.app_name, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")
    app.state.store = store
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    # ---- cross-cutting middleware & error handling -----------------------

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    def error_response(request: Request, code: int, message: str) -> Response:
        if _wants_html(request):
            return templates.TemplateResponse(
                request,
                "error.html",
                {"code": code, "message": message},
                status_code=code,
            )
        return JSONResponse({"error": message, "status": code}, status_code=code)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        return error_response(request, exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {"error": "invalid request", "status": 422, "detail": exc.errors()},
            status_code=422,
        )

    # ---- auth ------------------------------------------------------------

    def require_api_key(request: Request) -> None:
        if not settings.api_key:
            return
        provided = request.headers.get("x-api-key")
        if not provided:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                provided = auth[7:].strip()
        if not provided or not secrets.compare_digest(provided, settings.api_key):
            raise HTTPException(status_code=401, detail="missing or invalid API key")

    # ---- helpers ---------------------------------------------------------

    def artifact_summary(artifact: Artifact, request: Request) -> dict[str, Any]:
        return {
            "id": artifact.id,
            "kind": artifact.kind,
            "title": artifact.title,
            "created_at": iso(artifact.created_at),
            "expires_at": iso(artifact.expires_at),
            "url": build_url(request, f"/a/{artifact.id}", settings.base_url),
        }

    def artifact_detail(artifact: Artifact, request: Request) -> dict[str, Any]:
        return {
            **artifact_summary(artifact, request),
            "content": artifact.content,
            "metadata": artifact.metadata,
        }

    def artifact_export_json(artifact: Artifact, request: Request) -> str:
        return json.dumps(artifact_detail(artifact, request), indent=2, ensure_ascii=False, sort_keys=True)

    def artifact_export_markdown(artifact: Artifact, request: Request, rendered) -> str:
        canonical_url = build_url(request, f"/a/{artifact.id}", settings.base_url)
        lines: list[str] = [
            f"# {artifact.title}",
            "",
            f"- Kind: {artifact.kind}",
            f"- ID: {artifact.id}",
            f"- Created: {iso(artifact.created_at)}",
            f"- Expires: {iso(artifact.expires_at)}",
            f"- URL: {canonical_url}",
        ]
        source = rendered.raw_text or ""
        if artifact.kind == "markdown":
            lines.extend(["", source])
        elif artifact.kind == "image":
            image = artifact.content if isinstance(artifact.content, dict) else {}
            src = str(image.get("src", ""))
            alt = str(image.get("alt", "Artifact image"))
            caption = str(image.get("caption", "")).strip()
            lines.extend(["", f"![{alt}]({src})"])
            if caption:
                lines.extend(["", f"> {caption}"])
        elif artifact.kind == "report":
            lines.extend(["", "```html", str(artifact.content), "```"])
        elif artifact.kind == "json":
            lines.extend(["", "```json", source, "```"])
        else:
            lines.extend(["", "```text", source, "```"])
        return "\n".join(lines).rstrip() + "\n"

    def get_diff_pair(a_id: str, b_id: str) -> tuple[Artifact, Artifact]:
        if a_id == b_id:
            raise HTTPException(status_code=400, detail="choose two different artifacts")
        first = store.get(a_id)
        second = store.get(b_id)
        if first is None or second is None:
            raise HTTPException(status_code=404, detail="one or both artifacts were not found or have expired")
        if first.kind not in TEXTUAL_KINDS or second.kind not in TEXTUAL_KINDS:
            raise HTTPException(status_code=422, detail="only textual artifacts can be compared")
        if first.kind != second.kind:
            raise HTTPException(status_code=422, detail="artifacts must have the same textual kind")
        return first, second

    def diff_payload(first: Artifact, second: Artifact, request: Request) -> dict[str, Any]:
        first_text = source_text(first.kind, first.content)
        second_text = source_text(second.kind, second.content)
        unified = "".join(
            difflib.unified_diff(
                first_text.splitlines(keepends=True),
                second_text.splitlines(keepends=True),
                fromfile=f"a/{first.id}",
                tofile=f"b/{second.id}",
            )
        )
        return {
            "a": artifact_summary(first, request),
            "b": artifact_summary(second, request),
            "kind": first.kind,
            "changed": first_text != second_text,
            "additions": sum(1 for line in unified.splitlines() if line.startswith("+") and not line.startswith("+++")),
            "deletions": sum(1 for line in unified.splitlines() if line.startswith("-") and not line.startswith("---")),
            "diff": unified,
            "unified_diff": unified,
        }

    def diff_rows(first: Artifact, second: Artifact) -> list[dict[str, Any]]:
        left = source_text(first.kind, first.content).splitlines()
        right = source_text(second.kind, second.content).splitlines()
        rows: list[dict[str, Any]] = []
        matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
        for group in matcher.get_grouped_opcodes(n=3):
            start_a, start_b = group[0][1], group[0][3]
            end_a, end_b = group[-1][4], group[-1][5]
            rows.append({"hunk": f"@@ -{start_a + 1},{end_a - start_a} +{start_b + 1},{end_b - start_b} @@"})
            for tag, i1, i2, j1, j2 in group:
                if tag == "equal":
                    for offset, line in enumerate(left[i1:i2]):
                        rows.append({"type": "context", "old_no": i1 + offset + 1, "new_no": j1 + offset + 1,
                                     "old": highlight_line(line, first.kind), "new": highlight_line(line, first.kind)})
                elif tag == "delete":
                    for offset, line in enumerate(left[i1:i2]):
                        rows.append({"type": "delete", "old_no": i1 + offset + 1, "new_no": "", "old": highlight_line(line, first.kind), "new": ""})
                elif tag == "insert":
                    for offset, line in enumerate(right[j1:j2]):
                        rows.append({"type": "insert", "old_no": "", "new_no": j1 + offset + 1, "old": "", "new": highlight_line(line, first.kind)})
                else:
                    width = max(i2 - i1, j2 - j1)
                    for offset in range(width):
                        old_line = left[i1 + offset] if i1 + offset < i2 else None
                        new_line = right[j1 + offset] if j1 + offset < j2 else None
                        rows.append({"type": "replace", "old_no": i1 + offset + 1 if old_line is not None else "",
                                     "new_no": j1 + offset + 1 if new_line is not None else "",
                                     "old": highlight_line(old_line, first.kind) if old_line is not None else "",
                                     "new": highlight_line(new_line, first.kind) if new_line is not None else ""})
        return rows

    def normalize_content(payload: ArtifactCreateRequest) -> Any:
        content = payload.content
        if payload.kind == "json" and isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"json content must be valid JSON: {exc.msg}") from exc
        if payload.kind == "image":
            if isinstance(content, dict):
                if "src" not in content:
                    raise HTTPException(status_code=400, detail="image content must include 'src'")
                return content
            if isinstance(content, str):
                alt = (payload.metadata or {}).get("alt", "Artifact image")
                return {"src": content, "alt": alt}
            raise HTTPException(status_code=400, detail="image content must be a URL string or {src, alt?, caption?}")
        return content

    # ---- routes ----------------------------------------------------------

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok", "time": iso_now()}

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index(request: Request):
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "recent": store.list_recent(limit=8),
                "count": store.count(),
                "base_url": settings.base_url or str(request.base_url).rstrip("/"),
                "auth_required": bool(settings.api_key),
                "default_ttl_minutes": settings.default_ttl_minutes,
                "max_ttl_minutes": settings.max_ttl_minutes,
            },
        )

    @app.get("/api/docs", response_class=HTMLResponse, include_in_schema=False)
    def api_docs(request: Request):
        return templates.TemplateResponse(
            request,
            "api_docs.html",
            {
                "base_url": settings.base_url or str(request.base_url).rstrip("/"),
                "auth_required": bool(settings.api_key),
                "kinds": list(KIND_LABELS.keys()),
                "default_ttl_minutes": settings.default_ttl_minutes,
                "max_ttl_minutes": settings.max_ttl_minutes,
                "max_content_bytes": humanize_bytes(settings.max_content_bytes),
            },
        )

    @app.post("/api/artifacts", status_code=status.HTTP_201_CREATED)
    def create_artifact(payload: ArtifactCreateRequest, request: Request, _: None = Depends(require_api_key)):
        content = normalize_content(payload)

        size = len(json.dumps(content, ensure_ascii=False).encode("utf-8"))
        if size > settings.max_content_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"content is {humanize_bytes(size)}; limit is {humanize_bytes(settings.max_content_bytes)}",
            )

        ttl = payload.ttl_minutes if payload.ttl_minutes is not None else settings.default_ttl_minutes
        if ttl > settings.max_ttl_minutes:
            raise HTTPException(
                status_code=400,
                detail=f"ttl_minutes exceeds the maximum of {settings.max_ttl_minutes}",
            )

        artifact = store.create(
            title=payload.title,
            kind=payload.kind,
            content=content,
            ttl_minutes=ttl,
            metadata=payload.metadata or {},
        )
        return JSONResponse(artifact_summary(artifact, request), status_code=status.HTTP_201_CREATED)

    async def read_capped_body(request: Request) -> bytes:
        """Buffer the request body, refusing to exceed ``max_content_bytes``.

        Both the advertised ``Content-Length`` and the actual streamed size are
        checked, so a missing/forged length or chunked transfer can't push the
        server past its memory cap.
        """
        limit = settings.max_content_bytes
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"content exceeds the limit of {humanize_bytes(limit)}",
                    )
            except ValueError:
                pass
        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                raise HTTPException(
                    status_code=413,
                    detail=f"content exceeds the limit of {humanize_bytes(limit)}",
                )
            chunks.append(chunk)
        return b"".join(chunks)

    @app.post("/api/artifacts/upload", status_code=status.HTTP_201_CREATED)
    async def upload_artifact(
        request: Request,
        kind: Literal["text", "log", "json", "markdown", "image", "report"] = Query(
            ..., description="Artifact kind; determines how the raw body is interpreted."
        ),
        title: str | None = Query(default=None, max_length=160),
        filename: str | None = Query(default=None, max_length=255),
        ttl_minutes: int | None = Query(default=None, ge=1),
        _: None = Depends(require_api_key),
    ):
        """Create an artifact from a raw request body — the file's bytes are the
        content, so callers stream a file straight in without JSON-wrapping it.
        """
        raw = await read_capped_body(request)
        if not raw:
            raise HTTPException(status_code=400, detail="request body is empty")

        if kind == "image":
            media_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
            if not media_type.startswith("image/"):
                raise HTTPException(
                    status_code=400,
                    detail="image uploads require an image/* content-type header",
                )
            data_url = f"data:{media_type};base64," + base64.b64encode(raw).decode("ascii")
            content: Any = {"src": data_url, "alt": title or filename or "Artifact image"}
        elif kind == "json":
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(status_code=400, detail="json body must be UTF-8 encoded") from exc
            try:
                content = json.loads(text)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"json content must be valid JSON: {exc.msg}") from exc
        else:
            # text / log / markdown / report: stored as text, then escaped
            # (code surfaces) or sanitized (rich surfaces) at render time.
            content = raw.decode("utf-8", errors="replace")

        resolved_title = (title or filename or "Untitled artifact").strip() or "Untitled artifact"

        ttl = ttl_minutes if ttl_minutes is not None else settings.default_ttl_minutes
        if ttl > settings.max_ttl_minutes:
            raise HTTPException(
                status_code=400,
                detail=f"ttl_minutes exceeds the maximum of {settings.max_ttl_minutes}",
            )

        artifact = store.create(
            title=resolved_title,
            kind=kind,
            content=content,
            ttl_minutes=ttl,
            metadata={},
        )
        return JSONResponse(artifact_summary(artifact, request), status_code=status.HTTP_201_CREATED)

    @app.post("/api/artifacts/diff")
    def compare_artifacts(payload: ArtifactDiffRequest, request: Request):
        first, second = get_diff_pair(payload.a, payload.b)
        return diff_payload(first, second, request)

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact_api(artifact_id: str, request: Request):
        artifact = store.get(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact not found or expired")
        return artifact_detail(artifact, request)

    @app.get("/diff", response_class=HTMLResponse, include_in_schema=False)
    def diff_view(request: Request, a: str = Query(..., min_length=1, max_length=128), b: str = Query(..., min_length=1, max_length=128)):
        first, second = get_diff_pair(a, b)
        return templates.TemplateResponse(
            request,
            "diff.html",
            {
                "a": first,
                "b": second,
                "kind": first.kind,
                "rows": diff_rows(first, second),
                "unified": diff_payload(first, second, request)["unified_diff"],
            },
        )

    @app.get("/a/{artifact_id}", response_class=HTMLResponse, include_in_schema=False)
    def view_artifact(artifact_id: str, request: Request):
        artifact = store.get(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=410, detail="This artifact has expired or was removed.")
        rendered = render_artifact(artifact.kind, artifact.content)
        return templates.TemplateResponse(
            request,
            "artifact.html",
            {
                "artifact": artifact,
                "rendered": rendered,
                "canonical_url": build_url(request, f"/a/{artifact.id}", settings.base_url),
                "copy_json_b64": base64.b64encode(artifact_export_json(artifact, request).encode("utf-8")).decode("ascii"),
                "copy_markdown_b64": base64.b64encode(
                    artifact_export_markdown(artifact, request, rendered).encode("utf-8")
                ).decode("ascii"),
            },
        )

    @app.get("/a/{artifact_id}/raw", include_in_schema=False)
    def raw_artifact(artifact_id: str, request: Request):
        artifact = store.get(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact not found or expired")
        return artifact_detail(artifact, request)

    @app.get("/a/{artifact_id}/download", include_in_schema=False)
    def download_artifact(artifact_id: str):
        artifact = store.get(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=410, detail="This artifact has expired or was removed.")
        try:
            result = build_download(artifact)
        except DownloadError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if result.redirect_url is not None:
            # Remote images are redirected, never proxied — see download.py.
            return RedirectResponse(result.redirect_url, status_code=302)
        # Content-Disposition: attachment (plus the global nosniff header) means
        # even report HTML is saved to disk rather than rendered in the browser.
        return Response(
            content=result.body,
            media_type=result.media_type,
            headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
        )

    def materialize_example(slug: str) -> Artifact:
        example = EXAMPLES_BY_SLUG[slug]
        return store.create(
            title=example.title,
            kind=example.kind,
            content=example.content,
            ttl_minutes=settings.default_ttl_minutes,
            metadata=example.metadata,
        )

    @app.get("/examples/{slug}", include_in_schema=False)
    def open_example(slug: str) -> RedirectResponse:
        if slug not in EXAMPLES_BY_SLUG:
            raise HTTPException(status_code=404, detail="unknown example")
        artifact = materialize_example(slug)
        return RedirectResponse(url=f"/a/{artifact.id}", status_code=302)

    @app.get("/demo", include_in_schema=False)
    def demo() -> RedirectResponse:
        # Back-compat entry point: open the postmortem, our richest example.
        artifact = materialize_example("postmortem")
        return RedirectResponse(url=f"/a/{artifact.id}", status_code=302)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("artifact_viewer.main:app", host="0.0.0.0", port=8000, reload=False)
