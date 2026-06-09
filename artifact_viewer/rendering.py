from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import bleach
import markdown as md


ALLOWED_TAGS = [
    "a", "abbr", "acronym", "b", "blockquote", "br", "code", "div", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "i", "img", "li", "ol", "p", "pre", "span", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
]
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title"],
    "code": ["class"],
    "pre": ["class"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
    "*": ["class"],
}
ALLOWED_PROTOCOLS = ["http", "https", "data", "mailto"]


@dataclass(slots=True)
class RenderedArtifact:
    body_html: str
    body_kind: str
    raw_text: str | None = None
    image_src: str | None = None
    image_alt: str | None = None


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def sanitize_html(value: str) -> str:
    return bleach.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )


def render_markdown(value: str) -> str:
    html = md.markdown(value, extensions=["fenced_code", "tables", "sane_lists"])
    return sanitize_html(html)


def render_report_html(value: str) -> str:
    return sanitize_html(value)


def render_artifact(kind: str, content: Any) -> RenderedArtifact:
    if kind == "json":
        raw = pretty_json(content)
        return RenderedArtifact(body_html=f'<pre class="artifact-pre">{bleach.clean(raw)}</pre>', body_kind="preformatted", raw_text=raw)
    if kind in {"text", "log"}:
        raw = str(content)
        return RenderedArtifact(body_html=f'<pre class="artifact-pre">{bleach.clean(raw)}</pre>', body_kind="preformatted", raw_text=raw)
    if kind == "markdown":
        rendered = render_markdown(str(content))
        return RenderedArtifact(body_html=f'<div class="prose">{rendered}</div>', body_kind="rich")
    if kind == "report":
        rendered = render_report_html(str(content))
        return RenderedArtifact(body_html=f'<div class="report-surface">{rendered}</div>', body_kind="rich")
    if kind == "image":
        if not isinstance(content, dict):
            raise ValueError("image artifacts must store a dict payload")
        src = str(content.get("src", ""))
        alt = str(content.get("alt", "Artifact image"))
        caption = content.get("caption")
        image_html = f'<figure class="image-frame"><img src="{bleach.clean(src)}" alt="{bleach.clean(alt)}"></figure>'
        if caption:
            image_html += f'<p class="figure-caption">{bleach.clean(str(caption))}</p>'
        return RenderedArtifact(body_html=image_html, body_kind="image", image_src=src, image_alt=alt)
    raise ValueError(f"Unsupported artifact kind: {kind}")
