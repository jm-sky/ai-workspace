"""Auto-wikilink plain-text mentions of known wiki pages."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Placeholders must not collide with normal markdown/wiki text.
_PH = "\x00WLPH{0}\x00"

# Protected regions: fenced code, inline code, existing wikilinks.
_PROTECT_RE = re.compile(
    r"(```[\s\S]*?```|`[^`\n]+`|\[\[[^\]]+\]\])",
    re.MULTILINE,
)


@dataclass(frozen=True)
class LinkTarget:
    """A page that can be auto-linked by title and/or slug."""

    slug: str
    title: str


def append_ingest_section(
    body: str,
    *,
    timestamp: str,
    ingest_title: str,
    entity_body: str,
    raw_slug: str,
) -> str | None:
    """Append a From-ingest section, or None if this raw source is already cited."""
    marker = f"Source: [[{raw_slug}"
    if marker in body:
        return None
    section = (
        f"\n\n## From ingest {timestamp} — {ingest_title}\n\n"
        f"{entity_body}\n\n"
        f"Source: [[{raw_slug}|raw]]\n"
    )
    return body.rstrip() + section


def _mask_protected(body: str) -> tuple[str, list[str]]:
    """Replace protected spans with placeholders; return (masked, originals)."""
    originals: list[str] = []

    def _repl(match: re.Match[str]) -> str:
        originals.append(match.group(0))
        return _PH.format(len(originals) - 1)

    return _PROTECT_RE.sub(_repl, body), originals


def _unmask_protected(body: str, originals: list[str]) -> str:
    for i, original in enumerate(originals):
        body = body.replace(_PH.format(i), original, 1)
    return body


def _match_terms(target: LinkTarget, *, min_len: int) -> list[str]:
    """Collect unique match strings (title + slug), longest first within target."""
    terms: list[str] = []
    seen: set[str] = set()
    for term in (target.title, target.slug):
        t = term.strip()
        key = t.lower()
        if len(t) >= min_len and key not in seen:
            seen.add(key)
            terms.append(t)
    terms.sort(key=len, reverse=True)
    return terms


def auto_wikilink_body(
    body: str,
    targets: list[LinkTarget],
    *,
    self_slug: str | None = None,
    min_len: int = 4,
    max_links: int = 20,
) -> tuple[str, int]:
    """Replace plain-text title/slug mentions with [[slug]] / [[slug|text]].

    Longest-match-first across all targets. Skips protected regions and self-links.
    Returns (new_body, number_of_replacements).
    """
    if not body or not targets or max_links <= 0:
        return body, 0

    pairs: list[tuple[str, str]] = []
    seen_terms: set[str] = set()
    for target in targets:
        if self_slug and target.slug.lower() == self_slug.lower():
            continue
        for term in _match_terms(target, min_len=min_len):
            key = term.lower()
            if key in seen_terms:
                continue
            seen_terms.add(key)
            pairs.append((term, target.slug))

    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    if not pairs:
        return body, 0

    masked, originals = _mask_protected(body)
    applied = 0

    for term, slug in pairs:
        if applied >= max_links:
            break
        pattern = re.compile(
            rf"(?<!\w)({re.escape(term)})(?!\w)",
            re.IGNORECASE,
        )
        while applied < max_links:
            match = pattern.search(masked)
            if not match:
                break
            matched_text = match.group(1)
            # Keep display text when casing/spelling differs from canonical slug.
            if matched_text == slug:
                link = f"[[{slug}]]"
            else:
                link = f"[[{slug}|{matched_text}]]"
            # Protect newly inserted link from further matches.
            originals.append(link)
            placeholder = _PH.format(len(originals) - 1)
            masked = masked[: match.start()] + placeholder + masked[match.end() :]
            applied += 1

    return _unmask_protected(masked, originals), applied
