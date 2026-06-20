"""Compute safe file downloads for an artifact.

The web layer (:mod:`artifact_viewer.main`) calls :func:`build_download` and turns
the result into either an attachment ``Response`` or a redirect. Keeping the
decision logic here makes the SSRF boundary explicit and easy to unit-test:

* Source-bearing kinds (text/log/markdown/json/report) are served as
  attachments built entirely from data we already hold — no network calls.
* ``report`` is downloaded as the *sanitized* HTML, never the raw input.
* ``image`` data URLs are decoded server-side into their real bytes. Remote
  ``http(s)`` images are **never** fetched by the server (that would be an SSRF
  vector); we hand the browser a redirect to the original URL instead.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from urllib.parse import unquote_to_bytes

from .rendering import pretty_json, sanitize_html
from .store import Artifact


class DownloadError(ValueError):
    """Raised when an artifact cannot be turned into a safe download."""


@dataclass(slots=True)
class DownloadResult:
    """Either an inline body to stream as an attachment, or a redirect target."""

    filename: str
    media_type: str = ""
    body: bytes | None = None
    redirect_url: str | None = None


# Plain-text-ish source kinds: (extension, media type).
_SOURCE_KINDS = {
    "text": ("txt", "text/plain; charset=utf-8"),
    "log": ("log", "text/plain; charset=utf-8"),
    "markdown": ("md", "text/markdown; charset=utf-8"),
}

_IMAGE_EXT_BY_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/bmp": "bmp",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    "image/avif": "avif",
    "image/tiff": "tiff",
}


def _slug(title: str, fallback: str) -> str:
    """A filesystem- and header-safe stem derived from the artifact title."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-._").lower()
    return slug[:64] or fallback


def _decode_data_url(src: str) -> tuple[str, bytes]:
    """Decode a ``data:`` URL into ``(media_type, bytes)`` without any network IO."""
    header, sep, payload = src[len("data:"):].partition(",")
    if not sep:
        raise DownloadError("malformed data URL")
    is_base64 = header.endswith(";base64")
    media_type = (header[: -len(";base64")] if is_base64 else header) or "text/plain"
    try:
        if is_base64:
            data = base64.b64decode(payload, validate=True)
        else:
            data = unquote_to_bytes(payload)
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise DownloadError("could not decode data URL payload") from exc
    return media_type, data


def _image_download(artifact: Artifact, stem: str) -> DownloadResult:
    content = artifact.content if isinstance(artifact.content, dict) else {}
    src = str(content.get("src", "")).strip()
    if src.startswith("data:"):
        media_type, data = _decode_data_url(src)
        ext = _IMAGE_EXT_BY_MIME.get(media_type.split(";", 1)[0].strip().lower(), "bin")
        return DownloadResult(
            filename=f"{stem}.{ext}",
            media_type=media_type or "application/octet-stream",
            body=data,
        )
    if src.startswith(("http://", "https://")):
        # SSRF guard: the server must not fetch arbitrary URLs. Let the browser
        # follow the redirect to the image the author originally referenced.
        return DownloadResult(filename=stem, redirect_url=src)
    raise DownloadError("image source is not downloadable")


def build_download(artifact: Artifact) -> DownloadResult:
    """Return how to download ``artifact`` — either inline bytes or a redirect."""
    stem = _slug(artifact.title, artifact.id)
    kind = artifact.kind

    if kind in _SOURCE_KINDS:
        ext, media_type = _SOURCE_KINDS[kind]
        return DownloadResult(
            filename=f"{stem}.{ext}",
            media_type=media_type,
            body=str(artifact.content).encode("utf-8"),
        )
    if kind == "json":
        return DownloadResult(
            filename=f"{stem}.json",
            media_type="application/json; charset=utf-8",
            body=pretty_json(artifact.content).encode("utf-8"),
        )
    if kind == "report":
        # Download the sanitized HTML, not the raw input, and never inline.
        return DownloadResult(
            filename=f"{stem}.html",
            media_type="text/html; charset=utf-8",
            body=sanitize_html(str(artifact.content)).encode("utf-8"),
        )
    if kind == "image":
        return _image_download(artifact, stem)

    raise DownloadError(f"cannot download artifact of kind {kind!r}")
