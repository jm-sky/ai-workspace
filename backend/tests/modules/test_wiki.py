"""Tests for Second Brain wiki module: ACL, immutable, wikilinks, ingest, query, seed, lint, rag bridge."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.tenants.service import TenantContext
from app.modules.wiki.links import parse_wikilinks
from app.modules.wiki.services.wiki_service import (
    ImmutablePageError,
    WikiService,
    _heuristic_extract_entities,
    _slugify,
)


def _tenant_ctx(tenant_id: str = "tenant-a", user_id: str = "user-a") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, user_id=user_id, tenant_role="member")


def _make_page(
    *,
    page_id: str = "page-1",
    tenant_id: str = "tenant-a",
    user_id: str = "user-a",
    folder: str = "inbox",
    slug: str = "test-page",
    title: str = "Test Page",
    body_md: str = "Hello world",
    status: str = "active",
    immutable: bool = False,
    document_id: str | None = None,
):
    """Create a mock WikiPage-like object."""
    page = MagicMock()
    page.id = page_id
    page.tenant_id = tenant_id
    page.user_id = user_id
    page.folder = folder
    page.slug = slug
    page.title = title
    page.body_md = body_md
    page.frontmatter = None
    page.source_url = None
    page.status = status
    page.immutable = immutable
    page.document_id = document_id
    page.created_at = datetime.now(UTC)
    page.updated_at = datetime.now(UTC)
    return page


# --- Wikilink parser ---

def test_parse_wikilinks_basic():
    links = parse_wikilinks("See [[my-page]] and [[other|display text]].")
    assert len(links) == 2
    assert links[0].slug == "my-page"
    assert links[0].text is None
    assert links[1].slug == "other"
    assert links[1].text == "display text"


def test_parse_wikilinks_deduplicates():
    links = parse_wikilinks("[[a]] then [[A]] then [[a|different text]]")
    assert len(links) == 1
    assert links[0].slug == "a"


def test_parse_wikilinks_empty():
    assert parse_wikilinks("No links here.") == []


def test_parse_wikilinks_nested_brackets():
    links = parse_wikilinks("[[valid-slug]] and [not a link]")
    assert len(links) == 1


# --- Slugify ---

def test_slugify_basic():
    assert _slugify("Hello World!") == "hello-world"


def test_slugify_special_chars():
    assert _slugify("Test: a/b (c)") == "test-ab-c"


def test_slugify_truncates():
    assert len(_slugify("a" * 300)) <= 200


# --- Heuristic extractor ---

def test_heuristic_extract_headings():
    # H1 is document title (skipped); H2/H3 become entities.
    content = "# Doc Title\n\nSome text.\n\n## First Heading\n\nMore.\n\n## Second Heading\n\nMore text."
    items = _heuristic_extract_entities(content)
    assert len(items) >= 2
    assert items[0][0] == "First Heading"
    assert items[1][0] == "Second Heading"


def test_heuristic_extract_max_items():
    content = "# Doc\n\n" + "\n".join(f"## Heading {i}" for i in range(20))
    items = _heuristic_extract_entities(content, max_items=5)
    assert len(items) == 5


def test_heuristic_extract_key_value_lines():
    content = "No headings here.\n\nAuthor: Jane Doe\nTopic: AI Research\nShort"
    items = _heuristic_extract_entities(content)
    assert any("Author" in item[0] for item in items)


# --- ACL: same tenant, different user ---

@pytest.mark.asyncio
async def test_acl_different_user_get_page():
    """User B cannot access User A's page — returns None (404, not 403)."""
    db = AsyncMock()
    service = WikiService(db)
    service.repo = MagicMock()
    service.repo.get_page = AsyncMock(return_value=None)

    result = await service.get_page(
        tenant_ctx=_tenant_ctx(user_id="user-b"),
        page_id="page-1",
    )
    assert result is None
    service.repo.get_page.assert_awaited_once_with(
        "page-1", tenant_id="tenant-a", user_id="user-b"
    )


@pytest.mark.asyncio
async def test_acl_different_tenant_get_page():
    """Different tenant cannot access page — returns None."""
    db = AsyncMock()
    service = WikiService(db)
    service.repo = MagicMock()
    service.repo.get_page = AsyncMock(return_value=None)

    result = await service.get_page(
        tenant_ctx=_tenant_ctx(tenant_id="other-tenant", user_id="user-a"),
        page_id="page-1",
    )
    assert result is None


# --- Immutable (raw) pages: 409 ---

@pytest.mark.asyncio
async def test_immutable_page_update_raises():
    """PATCH on immutable page raises ImmutablePageError."""
    db = AsyncMock()
    service = WikiService(db)
    page = _make_page(immutable=True, folder="raw")
    service.repo = MagicMock()
    service.repo.get_page = AsyncMock(return_value=page)

    with pytest.raises(ImmutablePageError):
        await service.update_page(
            tenant_ctx=_tenant_ctx(),
            page_id="page-1",
            title="New Title",
        )


@pytest.mark.asyncio
async def test_immutable_page_delete_raises():
    """DELETE on immutable page raises ImmutablePageError."""
    db = AsyncMock()
    service = WikiService(db)
    page = _make_page(immutable=True, folder="raw")
    service.repo = MagicMock()
    service.repo.get_page = AsyncMock(return_value=page)

    with pytest.raises(ImmutablePageError):
        await service.delete_page(
            tenant_ctx=_tenant_ctx(),
            page_id="page-1",
        )


# --- Wikilinks rebuild ---

@pytest.mark.asyncio
async def test_get_page_enriches_incoming_link_source():
    """Incoming links expose fromSlug/fromTitle of the linking page, not toSlug only."""
    db = AsyncMock()
    service = WikiService(db)

    target = _make_page(
        page_id="entity-1",
        folder="entities",
        slug="portal-klienta",
        title="Portal Klienta",
    )
    source = _make_page(
        page_id="summary-1",
        folder="summaries",
        slug="summary-praca",
        title="Summary: Praca",
    )
    incoming = MagicMock()
    incoming.id = "link-1"
    incoming.from_page_id = "summary-1"
    incoming.to_page_id = "entity-1"
    incoming.to_slug = "portal-klienta"
    incoming.link_text = None

    service.repo = MagicMock()
    service.repo.get_page = AsyncMock(return_value=target)
    service.repo.get_outgoing_links = AsyncMock(return_value=[])
    service.repo.get_incoming_links = AsyncMock(return_value=[incoming])
    service.repo.get_pages_by_ids = AsyncMock(return_value={"summary-1": source})

    result = await service.get_page(tenant_ctx=_tenant_ctx(), page_id="entity-1")

    assert result is not None
    assert len(result.incomingLinks) == 1
    link = result.incomingLinks[0]
    assert link.fromSlug == "summary-praca"
    assert link.fromTitle == "Summary: Praca"
    assert link.fromFolder == "summaries"
    assert link.toSlug == "portal-klienta"


@pytest.mark.asyncio
async def test_wikilinks_rebuild_on_save():
    """Saving page with [[a]] and [[b|text]] creates 2 edges; nonexistent slug → to_page_id=None."""
    db = AsyncMock()
    service = WikiService(db)
    page = _make_page(body_md="See [[slug-a]] and [[slug-b|display]]")

    service.repo = MagicMock()
    service.repo.resolve_slug_to_page_id = AsyncMock(return_value=None)
    service.repo.rebuild_links = AsyncMock(return_value=[])

    await service._rebuild_page_links(page)

    service.repo.rebuild_links.assert_awaited_once()
    call_args = service.repo.rebuild_links.await_args
    links = call_args[1]["links"] if "links" in (call_args[1] or {}) else call_args[0][1]
    assert len(links) == 2
    assert links[0][0] == "slug-a"
    assert links[0][2] is None  # dangling
    assert links[1][0] == "slug-b"
    assert links[1][1] == "display"


@pytest.mark.asyncio
async def test_wikilinks_rebuild_removes_old_links():
    """Editing page to remove a link → full rebuild, old edge gone."""
    db = AsyncMock()
    service = WikiService(db)
    page = _make_page(body_md="No links here anymore.")

    service.repo = MagicMock()
    service.repo.rebuild_links = AsyncMock(return_value=[])

    await service._rebuild_page_links(page)

    call_args = service.repo.rebuild_links.await_args
    links = call_args[0][1]
    assert links == []


# --- Ingest + ripple ---

def _mock_ingest_repo(service: WikiService, *, fake_create_page, get_by_slug=None):
    """Shared mocks for ingest tests (seed + ripple + autolink catalog)."""
    service.repo = MagicMock()
    service.repo.create_page = AsyncMock(side_effect=fake_create_page)
    service.repo.get_page_by_slug = (
        AsyncMock(side_effect=get_by_slug) if get_by_slug else AsyncMock(return_value=None)
    )
    service.repo.slug_exists = AsyncMock(return_value=False)
    service.repo.rebuild_links = AsyncMock(return_value=[])
    service.repo.resolve_slug_to_page_id = AsyncMock(return_value=None)
    service.repo.list_link_targets = AsyncMock(return_value=[])
    service.repo.update_page = AsyncMock(side_effect=lambda page, **kwargs: page)
    service.rag_repo = MagicMock()
    service.rag_repo.create_document = AsyncMock(return_value=MagicMock(id="doc-1"))
    service.rag_repo.delete_document = AsyncMock(return_value=True)


@pytest.mark.asyncio
async def test_ingest_creates_raw_summary_and_rippled():
    """wiki_ingest creates Raw + Summary + rippled pages + Log entry."""
    db = AsyncMock()
    service = WikiService(db)

    created_pages = []

    async def fake_create_page(**kwargs):
        page = _make_page(
            page_id=f"page-{len(created_pages)}",
            folder=kwargs["folder"],
            slug=kwargs["slug"],
            title=kwargs["title"],
            body_md=kwargs["body_md"],
            immutable=kwargs.get("immutable", False),
        )
        created_pages.append(page)
        return page

    _mock_ingest_repo(service, fake_create_page=fake_create_page)

    content = "# Title\n\nSome content here.\n\n## SubSection\n\nMore content with details."

    result = await service.ingest(
        tenant_ctx=_tenant_ctx(),
        content=content,
        title="Test Article",
    )

    assert result.rawPageId is not None
    assert result.summaryPageId is not None
    assert len(result.rippledPages) >= 1
    assert result.truncated is False
    assert result.mergedPages == []
    assert result.autoLinksApplied >= 0

    raw_pages = [p for p in created_pages if p.folder == "raw"]
    assert len(raw_pages) == 1
    assert raw_pages[0].immutable is True

    summary_pages = [p for p in created_pages if p.folder == "summaries"]
    assert len(summary_pages) == 1


@pytest.mark.asyncio
async def test_ingest_ripple_limit():
    """Ingest with many headings respects RIPPLE_MAX_PAGES limit."""
    db = AsyncMock()
    service = WikiService(db)

    page_count = 0

    async def fake_create_page(**kwargs):
        nonlocal page_count
        page_count += 1
        return _make_page(
            page_id=f"page-{page_count}",
            folder=kwargs["folder"],
            slug=kwargs["slug"],
            title=kwargs["title"],
            body_md=kwargs["body_md"],
            immutable=kwargs.get("immutable", False),
        )

    _mock_ingest_repo(service, fake_create_page=fake_create_page)

    # H2 headings → entities (H1 is skipped by heuristic)
    many_headings = "# Large ingest\n\n" + "\n\n".join(
        f"## Entity {i}\n\nDescription of entity {i}." for i in range(30)
    )

    result = await service.ingest(
        tenant_ctx=_tenant_ctx(),
        content=many_headings,
        title="Large ingest",
    )

    assert result.truncated is True
    total_rippled = len(result.rippledPages)
    assert total_rippled <= 13  # 15 max minus raw and summary


@pytest.mark.asyncio
async def test_ingest_merges_existing_entity_instead_of_slug_suffix():
    """Second ingest of same entity slug appends to existing page — no firma-2."""
    db = AsyncMock()
    service = WikiService(db)

    existing_entity = _make_page(
        page_id="entity-firma",
        folder="entities",
        slug="portal-klienta",
        title="Portal Klienta",
        body_md="# Portal Klienta\n\nFirst notes.\n\nSource: [[first-raw|raw]]",
    )
    created_pages = []

    async def fake_create_page(**kwargs):
        page = _make_page(
            page_id=f"page-{len(created_pages)}",
            folder=kwargs["folder"],
            slug=kwargs["slug"],
            title=kwargs["title"],
            body_md=kwargs["body_md"],
            immutable=kwargs.get("immutable", False),
        )
        created_pages.append(page)
        return page

    async def fake_get_by_slug(*, tenant_id, user_id, folder, slug):
        if folder == "entities" and slug == "portal-klienta":
            return existing_entity
        return None

    updated_bodies: list[str] = []

    async def fake_update_page(page, **kwargs):
        if "body_md" in kwargs:
            page.body_md = kwargs["body_md"]
            updated_bodies.append(kwargs["body_md"])
        return page

    _mock_ingest_repo(service, fake_create_page=fake_create_page, get_by_slug=fake_get_by_slug)
    service.repo.update_page = AsyncMock(side_effect=fake_update_page)

    content = (
        "# Second Doc\n\nMentions Portal Klienta and Gear-Stack.\n\n"
        "## Portal Klienta\n\nMore context about the portal.\n"
    )

    result = await service.ingest(
        tenant_ctx=_tenant_ctx(),
        content=content,
        title="Second Doc",
    )

    entity_creates = [p for p in created_pages if p.folder == "entities"]
    assert entity_creates == []
    assert "entity-firma" in result.mergedPages
    assert "entity-firma" in result.rippledPages
    assert any("## From ingest" in b for b in updated_bodies)
    assert any("Source: [[" in b and "raw]]" in b for b in updated_bodies)
    assert not any(p.slug == "portal-klienta-2" for p in created_pages)


@pytest.mark.asyncio
async def test_ingest_autolinks_known_page_in_summary():
    """Summary body mentioning an existing title gets [[slug]] and rebuild_links."""
    db = AsyncMock()
    service = WikiService(db)

    created_pages = []

    async def fake_create_page(**kwargs):
        page = _make_page(
            page_id=f"page-{len(created_pages)}",
            folder=kwargs["folder"],
            slug=kwargs["slug"],
            title=kwargs["title"],
            body_md=kwargs["body_md"],
            immutable=kwargs.get("immutable", False),
        )
        created_pages.append(page)
        return page

    async def fake_update_page(page, **kwargs):
        if "body_md" in kwargs:
            page.body_md = kwargs["body_md"]
        return page

    _mock_ingest_repo(service, fake_create_page=fake_create_page)
    service.repo.update_page = AsyncMock(side_effect=fake_update_page)
    service.repo.list_link_targets = AsyncMock(
        return_value=[("gear-stack", "Gear-Stack", "entities")]
    )
    service.repo.resolve_slug_to_page_id = AsyncMock(return_value="entity-gear")

    content = "# Notes\n\nWe use Gear-Stack for the monorepo.\n\n## Other Topic\n\nDetails here."

    result = await service.ingest(
        tenant_ctx=_tenant_ctx(),
        content=content,
        title="Notes",
    )

    assert result.autoLinksApplied >= 1
    summary = next(p for p in created_pages if p.folder == "summaries")
    assert "[[gear-stack" in summary.body_md
    service.repo.rebuild_links.assert_awaited()


@pytest.mark.asyncio
async def test_ingest_autolinks_within_run_entities():
    """Newly created entities mentioning each other get cross-links in one ingest."""
    db = AsyncMock()
    service = WikiService(db)

    created_pages = []

    async def fake_create_page(**kwargs):
        page = _make_page(
            page_id=f"page-{len(created_pages)}",
            folder=kwargs["folder"],
            slug=kwargs["slug"],
            title=kwargs["title"],
            body_md=kwargs["body_md"],
            immutable=kwargs.get("immutable", False),
        )
        created_pages.append(page)
        return page

    async def fake_update_page(page, **kwargs):
        if "body_md" in kwargs:
            page.body_md = kwargs["body_md"]
        return page

    _mock_ingest_repo(service, fake_create_page=fake_create_page)
    service.repo.update_page = AsyncMock(side_effect=fake_update_page)

    content = (
        "# Map\n\n"
        "## Alpha Project\n\nRelated to Beta Module and more.\n\n"
        "## Beta Module\n\nStandalone notes.\n"
    )

    result = await service.ingest(
        tenant_ctx=_tenant_ctx(),
        content=content,
        title="Map",
    )

    entities = [p for p in created_pages if p.folder == "entities"]
    assert len(entities) >= 2
    alpha = next(p for p in entities if p.slug == "alpha-project")
    assert "[[beta-module" in alpha.body_md
    assert result.autoLinksApplied >= 1


# --- Inbox no auto-promote ---

@pytest.mark.asyncio
async def test_inbox_page_stays_in_inbox():
    """Creating a page in inbox does not trigger ingest/ripple."""
    db = AsyncMock()
    service = WikiService(db)

    created = _make_page(folder="inbox", slug="my-digest", title="Digest")

    service.repo = MagicMock()
    service.repo.create_page = AsyncMock(return_value=created)
    service.repo.slug_exists = AsyncMock(return_value=False)
    service.repo.rebuild_links = AsyncMock(return_value=[])
    service.repo.get_page_by_slug = AsyncMock(return_value=None)

    service.rag_repo = MagicMock()
    service.rag_repo.create_document = AsyncMock(return_value=MagicMock(id="doc-inbox"))
    service.rag_repo.delete_document = AsyncMock(return_value=True)

    page = await service.create_page(
        tenant_ctx=_tenant_ctx(),
        folder="inbox",
        slug="my-digest",
        title="Digest",
        body_md="Some notes.",
    )

    assert page.folder == "inbox"
    # create_page should be called only once (the inbox page + 2 seed pages max)
    # No summary or entity pages created
    create_calls = service.repo.create_page.await_args_list
    folders_created = [c.kwargs.get("folder") for c in create_calls]
    assert "summaries" not in folders_created
    assert "entities" not in folders_created


# --- wiki_query scope ---

@pytest.mark.asyncio
async def test_wiki_query_filters_source_type():
    """wiki_query calls RagService.search with source_types=['wiki']."""
    db = AsyncMock()
    service = WikiService(db)

    mock_rag_service = MagicMock()
    mock_rag_service.search = AsyncMock(return_value=[])

    with patch("app.modules.wiki.services.wiki_service.RagService", return_value=mock_rag_service):
        results = await service.query(
            tenant_ctx=_tenant_ctx(),
            query="test query",
            limit=5,
        )

    assert results == []
    mock_rag_service.search.assert_awaited_once()
    call_kwargs = mock_rag_service.search.await_args.kwargs
    assert call_kwargs["source_types"] == ["wiki"]


# --- Seed ---

@pytest.mark.asyncio
async def test_seed_creates_meta_pages():
    """First use seeds meta/index and meta/log."""
    db = AsyncMock()
    service = WikiService(db)
    service.repo = MagicMock()
    service.repo.get_page_by_slug = AsyncMock(return_value=None)
    service.repo.create_page = AsyncMock(side_effect=lambda **kw: _make_page(
        folder=kw["folder"], slug=kw["slug"], title=kw["title"]
    ))

    await service.ensure_seed(tenant_ctx=_tenant_ctx())

    create_calls = service.repo.create_page.await_args_list
    slugs = [c.kwargs["slug"] for c in create_calls]
    assert "index" in slugs
    assert "log" in slugs
    assert all(c.kwargs["folder"] == "meta" for c in create_calls)


@pytest.mark.asyncio
async def test_seed_skips_if_exists():
    """Seed does not recreate pages that already exist."""
    db = AsyncMock()
    service = WikiService(db)
    service.repo = MagicMock()
    service.repo.get_page_by_slug = AsyncMock(return_value=_make_page(folder="meta", slug="index"))

    service.repo.create_page = AsyncMock()

    await service.ensure_seed(tenant_ctx=_tenant_ctx())

    service.repo.create_page.assert_not_awaited()


# --- Lint ---

@pytest.mark.asyncio
async def test_lint_reports_dangling_links():
    db = AsyncMock()
    service = WikiService(db)
    service.repo = MagicMock()

    dangling = MagicMock()
    dangling.from_page_id = "page-1"
    dangling.to_slug = "nonexistent"

    service.repo.find_dangling_links = AsyncMock(return_value=[dangling])
    service.repo.find_orphan_pages = AsyncMock(return_value=[])
    service.repo.find_pages_without_links = AsyncMock(return_value=[])
    service.repo.list_pages = AsyncMock(return_value=([], 0))

    result = await service.lint(tenant_ctx=_tenant_ctx())

    assert len(result.issues) == 1
    assert result.issues[0].type == "dangling_link"
    assert result.issues[0].slug == "nonexistent"


@pytest.mark.asyncio
async def test_lint_reports_orphans():
    db = AsyncMock()
    service = WikiService(db)
    service.repo = MagicMock()

    orphan = _make_page(page_id="orphan-1", slug="lonely")

    service.repo.find_dangling_links = AsyncMock(return_value=[])
    service.repo.find_orphan_pages = AsyncMock(return_value=[orphan])
    service.repo.find_pages_without_links = AsyncMock(return_value=[])
    service.repo.list_pages = AsyncMock(return_value=([], 0))

    result = await service.lint(tenant_ctx=_tenant_ctx())

    orphan_issues = [i for i in result.issues if i.type == "orphan_page"]
    assert len(orphan_issues) == 1


@pytest.mark.asyncio
async def test_lint_does_not_auto_deprecate():
    """wiki_lint never auto-deprecates; only reports."""
    db = AsyncMock()
    service = WikiService(db)
    service.repo = MagicMock()

    service.repo.find_dangling_links = AsyncMock(return_value=[])
    service.repo.find_orphan_pages = AsyncMock(return_value=[])
    service.repo.find_pages_without_links = AsyncMock(return_value=[])
    service.repo.list_pages = AsyncMock(return_value=([], 0))

    result = await service.lint(tenant_ctx=_tenant_ctx())

    service.repo.update_page.assert_not_called()
    assert all(i.type != "auto_deprecate" for i in result.issues)


# --- RAG bridge ---

@pytest.mark.asyncio
async def test_rag_bridge_sync_on_create():
    """Creating a page creates a rag_document with source_type=wiki."""
    db = AsyncMock()
    service = WikiService(db)

    page = _make_page(document_id=None)
    service.repo = MagicMock()
    service.repo.create_page = AsyncMock(return_value=page)
    service.repo.slug_exists = AsyncMock(return_value=False)
    service.repo.rebuild_links = AsyncMock(return_value=[])
    service.repo.get_page_by_slug = AsyncMock(return_value=None)

    rag_doc = MagicMock(id="rag-doc-1")
    service.rag_repo = MagicMock()
    service.rag_repo.create_document = AsyncMock(return_value=rag_doc)
    service.rag_repo.delete_document = AsyncMock(return_value=True)

    await service.create_page(
        tenant_ctx=_tenant_ctx(),
        folder="inbox",
        slug="test",
        title="Test",
        body_md="Content",
    )

    service.rag_repo.create_document.assert_awaited()
    create_kwargs = service.rag_repo.create_document.await_args.kwargs
    assert create_kwargs["source_type"] == "wiki"
    assert create_kwargs["source_ref"] == page.id


@pytest.mark.asyncio
async def test_rag_bridge_delete_on_page_delete():
    """Deleting a page deletes its rag_document too."""
    db = AsyncMock()
    service = WikiService(db)

    page = _make_page(immutable=False, document_id="rag-doc-1")
    service.repo = MagicMock()
    service.repo.get_page = AsyncMock(return_value=page)
    service.repo.delete_page = AsyncMock()

    service.rag_repo = MagicMock()
    service.rag_repo.delete_document = AsyncMock(return_value=True)

    deleted = await service.delete_page(
        tenant_ctx=_tenant_ctx(),
        page_id="page-1",
    )

    assert deleted is True
    service.rag_repo.delete_document.assert_awaited_once_with(
        "rag-doc-1", tenant_id="tenant-a", user_id="user-a"
    )


@pytest.mark.asyncio
async def test_rag_bridge_deprecate_removes_rag_doc():
    """Deprecating a page removes its rag_document (excluded from search)."""
    db = AsyncMock()
    service = WikiService(db)

    page = _make_page(document_id="rag-doc-1")
    # After update, status becomes deprecated
    updated_page = _make_page(document_id="rag-doc-1", status="deprecated")
    service.repo = MagicMock()
    service.repo.get_page = AsyncMock(return_value=page)
    service.repo.update_page = AsyncMock(return_value=updated_page)

    service.rag_repo = MagicMock()
    service.rag_repo.delete_document = AsyncMock(return_value=True)

    result = await service.deprecate_page(
        tenant_ctx=_tenant_ctx(),
        page_id="page-1",
    )

    assert result is not None
    service.rag_repo.delete_document.assert_awaited()


# --- Agent tool wiring ---

@pytest.mark.asyncio
async def test_wiki_ingest_tool_requires_content():
    from app.modules.agent.tools.wiki import WikiIngestTool

    tool = WikiIngestTool(tenant_ctx=_tenant_ctx(), db=AsyncMock())
    result = await tool.execute({})
    assert result == {"error": "content is required"}


@pytest.mark.asyncio
async def test_wiki_query_tool_requires_query():
    from app.modules.agent.tools.wiki import WikiQueryTool

    tool = WikiQueryTool(tenant_ctx=_tenant_ctx(), db=AsyncMock())
    result = await tool.execute({})
    assert result == {"error": "query is required"}


# --- Migration pattern verification ---

def test_migration_066_exists():
    from pathlib import Path
    migration = Path(__file__).parent.parent.parent / "migrations" / "066_wiki_pages.py"
    assert migration.exists()
