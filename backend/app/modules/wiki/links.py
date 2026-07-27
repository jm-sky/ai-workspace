"""Wikilink parser: extract [[slug]] and [[slug|text]] from markdown body."""

from __future__ import annotations

import re
from dataclasses import dataclass

WIKILINK_RE = re.compile(r"\[\[([^\]\|]+?)(?:\|([^\]]+?))?\]\]")


@dataclass(frozen=True)
class ParsedWikilink:
    """A single parsed wikilink reference."""

    slug: str
    text: str | None


def parse_wikilinks(body_md: str) -> list[ParsedWikilink]:
    """Extract all [[slug]] and [[slug|display text]] from markdown body.

    Returns deduplicated list (by slug), preserving first occurrence order.
    """
    seen: set[str] = set()
    result: list[ParsedWikilink] = []
    for match in WIKILINK_RE.finditer(body_md):
        slug = match.group(1).strip()
        text = match.group(2)
        if text is not None:
            text = text.strip()
        if not slug:
            continue
        slug_lower = slug.lower()
        if slug_lower in seen:
            continue
        seen.add(slug_lower)
        result.append(ParsedWikilink(slug=slug, text=text))
    return result
