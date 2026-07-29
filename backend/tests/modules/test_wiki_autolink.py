"""Unit tests for wiki auto-wikilink and ingest-section merge helpers."""

from app.modules.wiki.autolink import (
    LinkTarget,
    append_ingest_section,
    auto_wikilink_body,
)


def test_auto_wikilink_longest_match_first():
    body = "Używamy Portal Klienta X w produkcji."
    targets = [
        LinkTarget(slug="portal", title="Portal"),
        LinkTarget(slug="portal-klienta-x", title="Portal Klienta X"),
    ]
    new_body, n = auto_wikilink_body(body, targets)
    assert n == 1
    assert "[[portal-klienta-x|Portal Klienta X]]" in new_body
    assert "[[portal|" not in new_body


def test_auto_wikilink_preserves_existing_wikilinks():
    body = "See [[portal-klienta]] and also Portal Klienta again."
    targets = [LinkTarget(slug="portal-klienta", title="Portal Klienta")]
    new_body, n = auto_wikilink_body(body, targets)
    assert n == 1
    assert new_body.count("[[portal-klienta") == 2
    assert "[[portal-klienta]]" in new_body
    assert "[[portal-klienta|Portal Klienta]]" in new_body


def test_auto_wikilink_skips_code_blocks():
    body = (
        "Gear-Stack is great.\n"
        "```\nGear-Stack in code\n```\n"
        "Inline `Gear-Stack` too."
    )
    targets = [LinkTarget(slug="gear-stack", title="Gear-Stack")]
    new_body, n = auto_wikilink_body(body, targets)
    assert n == 1
    assert "[[gear-stack|Gear-Stack]] is great." in new_body
    assert "```\nGear-Stack in code\n```" in new_body
    assert "`Gear-Stack`" in new_body


def test_auto_wikilink_max_links_limit():
    body = " ".join(f"Item{i}" for i in range(25))
    targets = [LinkTarget(slug=f"item{i}", title=f"Item{i}") for i in range(25)]
    new_body, n = auto_wikilink_body(body, targets, max_links=20)
    assert n == 20
    assert new_body.count("[[") == 20


def test_auto_wikilink_min_len():
    body = "Typ i Rol w projekcie."
    targets = [
        LinkTarget(slug="typ", title="Typ"),
        LinkTarget(slug="rol", title="Rol"),
    ]
    new_body, n = auto_wikilink_body(body, targets, min_len=4)
    assert n == 0
    assert new_body == body


def test_auto_wikilink_case_insensitive_display():
    body = "Working with GEAR-STACK daily."
    targets = [LinkTarget(slug="gear-stack", title="Gear-Stack")]
    new_body, n = auto_wikilink_body(body, targets)
    assert n == 1
    assert "[[gear-stack|GEAR-STACK]]" in new_body


def test_auto_wikilink_skips_self():
    body = "Portal Klienta mentions Portal Klienta."
    targets = [LinkTarget(slug="portal-klienta", title="Portal Klienta")]
    new_body, n = auto_wikilink_body(body, targets, self_slug="portal-klienta")
    assert n == 0
    assert new_body == body


def test_auto_wikilink_slug_equals_match_no_pipe():
    body = "See gear-stack docs."
    targets = [LinkTarget(slug="gear-stack", title="Gear Stack")]
    new_body, n = auto_wikilink_body(body, targets)
    assert n == 1
    assert "[[gear-stack]]" in new_body
    assert "|" not in new_body.split("[[gear-stack")[1].split("]]")[0]


def test_append_ingest_section_adds_block():
    body = "# Firma\n\nExisting notes."
    result = append_ingest_section(
        body,
        timestamp="2026-07-29T10:00:00+00:00",
        ingest_title="Doc A",
        entity_body="New context about Firma.",
        raw_slug="doc-a",
    )
    assert result is not None
    assert "## From ingest 2026-07-29T10:00:00+00:00 — Doc A" in result
    assert "New context about Firma." in result
    assert "Source: [[doc-a|raw]]" in result


def test_append_ingest_section_skips_duplicate_raw():
    body = "# Firma\n\nSource: [[doc-a|raw]]\n"
    result = append_ingest_section(
        body,
        timestamp="2026-07-29T11:00:00+00:00",
        ingest_title="Doc A again",
        entity_body="Duplicate.",
        raw_slug="doc-a",
    )
    assert result is None
