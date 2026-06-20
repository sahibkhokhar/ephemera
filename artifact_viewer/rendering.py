"""Turn stored artifact content into safe, presentation-ready data.

Two design rules drive this module:

1. For "code" surfaces (text, log, json) we never build HTML by hand. We split
   the content into lines and let Jinja's autoescaping handle every character.
   The template draws the line-number gutter, so the gutter can never be copied
   into the clipboard or confused with the payload.
2. For "rich" surfaces (markdown, report) we render to HTML and then run the
   result through a strict allow-list sanitizer. Combined with the page CSP
   (``script-src 'self'``) this gives two independent layers of protection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

import bleach
import markdown as md

# Allow-list for markdown output and "report" HTML. Intentionally narrow: no
# <script>, <style>, <iframe>, <form>, or event handlers ever survive.
ALLOWED_TAGS = [
    "a", "abbr", "blockquote", "br", "code", "del", "div", "em", "h1", "h2",
    "h3", "h4", "h5", "h6", "hr", "i", "img", "kbd", "li", "ol", "p", "pre",
    "span", "strong", "sub", "sup", "table", "tbody", "td", "th", "thead",
    "tr", "ul",
]
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
    "td": ["colspan", "rowspan", "align"],
    "th": ["colspan", "rowspan", "align"],
    "*": ["class"],
}
# Note: "javascript" is deliberately excluded so javascript: URLs are stripped.
ALLOWED_PROTOCOLS = ["http", "https", "data", "mailto"]

CodeLanguage = Literal["text", "log", "json"]


@dataclass(slots=True)
class RenderedArtifact:
    """Everything the artifact template needs, pre-computed and safe."""

    mode: Literal["code", "rich", "image"]
    lines: list[str] = field(default_factory=list)
    language: str | None = None
    html: str | None = None
    image: dict[str, str] | None = None
    raw_text: str | None = None
    line_count: int = 0
    byte_count: int = 0


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def sanitize_html(value: str) -> str:
    cleaned = bleach.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    # Add rel/target to links so external references can't tamper with opener.
    return bleach.linkify(
        cleaned,
        callbacks=[_external_link_attrs],
        skip_tags=["pre", "code"],
        parse_email=False,
    )


def _external_link_attrs(attrs: dict, new: bool = False) -> dict:
    href = attrs.get((None, "href"), "")
    if href.startswith("http"):
        attrs[(None, "rel")] = "noopener nofollow ugc"
        attrs[(None, "target")] = "_blank"
    return attrs


def render_markdown(value: str) -> str:
    html = md.markdown(
        value,
        extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
        output_format="html",
    )
    return sanitize_html(html)


def _code(raw: str, language: str) -> RenderedArtifact:
    # splitlines() drops a single trailing newline; keepends would double the
    # gutter rows, so we normalize to a clean list of logical lines.
    lines = raw.split("\n")
    return RenderedArtifact(
        mode="code",
        lines=lines,
        language=language,
        raw_text=raw,
        line_count=len(lines),
        byte_count=len(raw.encode("utf-8")),
    )


def render_artifact(kind: str, content: Any) -> RenderedArtifact:
    if kind == "json":
        return _code(pretty_json(content), "json")
    if kind in {"text", "log"}:
        return _code(str(content), kind)
    if kind == "markdown":
        text = str(content)
        return RenderedArtifact(
            mode="rich",
            language="markdown",
            html=render_markdown(text),
            raw_text=text,
            byte_count=len(text.encode("utf-8")),
        )
    if kind == "report":
        text = str(content)
        return RenderedArtifact(
            mode="rich",
            language="report",
            html=sanitize_html(text),
            raw_text=text,
            byte_count=len(text.encode("utf-8")),
        )
    if kind == "image":
        if not isinstance(content, dict):
            raise ValueError("image artifacts must store a dict payload")
        src = str(content.get("src", ""))
        image = {
            "src": src,
            "alt": str(content.get("alt", "Artifact image")),
            "caption": str(content["caption"]) if content.get("caption") else "",
        }
        return RenderedArtifact(mode="image", image=image, byte_count=len(src.encode("utf-8")))
    raise ValueError(f"Unsupported artifact kind: {kind}")
