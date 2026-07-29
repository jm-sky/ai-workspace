"""Business logic for Second Brain wiki: CRUD, ingest, query, lint."""

from __future__ import annotations

import logging
import re
import textwrap
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.id_utils import generate_id
from app.modules.rag.repositories import RagRepository
from app.modules.rag.services.rag_service import RagService
from app.modules.rag.types import RagSourceType
from app.modules.tenants.service import TenantContext
from app.modules.wiki.db_models import WikiLink, WikiPage
from app.modules.wiki.links import parse_wikilinks
from app.modules.wiki.repositories import _UNSET, WikiRepository
from app.modules.wiki.schemas import (
    WikiGraphEdge,
    WikiGraphNode,
    WikiGraphResponse,
    WikiIngestResponse,
    WikiLinkResponse,
    WikiLintIssue,
    WikiLintResponse,
    WikiPageDetailResponse,
    WikiPageResponse,
)
from app.modules.wiki.types import WikiFolder

logger = logging.getLogger(__name__)

RIPPLE_MAX_PAGES = 15


def _slugify(text: str) -> str:
    """Simple slugification: lowercase, replace spaces/special with dashes."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:200]


def _page_to_response(page: WikiPage) -> WikiPageResponse:
    return WikiPageResponse(
        id=page.id,
        folder=page.folder,
        slug=page.slug,
        title=page.title,
        bodyMd=page.body_md,
        frontmatter=page.frontmatter,
        sourceUrl=page.source_url,
        status=page.status,
        immutable=page.immutable,
        documentId=page.document_id,
        createdAt=page.created_at,
        updatedAt=page.updated_at,
    )


def _link_to_response(link: WikiLink) -> WikiLinkResponse:
    return WikiLinkResponse(
        id=link.id,
        fromPageId=link.from_page_id,
        toPageId=link.to_page_id,
        toSlug=link.to_slug,
        linkText=link.link_text,
    )


def _heuristic_extract_entities(content: str, max_items: int = 8) -> list[tuple[str, str, str]]:
    """Librarian heuristic extractor: pull headings and key lines as entity/concept seeds.

    Returns list of (title, body, folder_hint) where folder_hint is 'entities' or 'concepts'.
    This is a deterministic fallback so that wiki_ingest works without
    an LLM key. A future iteration may call OpenRouter for richer extraction.
    """
    items: list[tuple[str, str, str]] = []

    # Build a map: heading title -> lines under that heading (for richer body)
    heading_re = re.compile(r"^(#{1,3})\s+(.+)", re.MULTILINE)
    lines = content.splitlines()

    # Pass 1: headings (skip H1 — that's the document title)
    heading_matches = list(heading_re.finditer(content))
    for i, m in enumerate(heading_matches):
        level = len(m.group(1))
        if level == 1:
            continue  # skip document title
        title = m.group(2).strip()
        if not title or len(title) <= 2:
            continue

        # Collect lines between this heading and the next
        start_line = content[:m.end()].count("\n") + 1
        if i + 1 < len(heading_matches):
            end_line = content[:heading_matches[i + 1].start()].count("\n")
        else:
            end_line = len(lines)
        section_lines = [l for l in lines[start_line:end_line] if l.strip()]
        section_body = "\n".join(section_lines[:6])  # max 6 lines of context

        body = f"{section_body}" if section_body else f"Sekcja z dokumentu: {title}"
        items.append((title, body, "entities"))
        if len(items) >= max_items:
            break

    # Pass 2: key:value lines → concepts
    if len(items) < max_items:
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key and len(key) > 2 and value and len(key) < 60:
                    items.append((key, value, "concepts"))
                if len(items) >= max_items:
                    break

    return items


class WikiService:
    """Second Brain wiki service: CRUD, ingest, query, lint, graph."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WikiRepository(db)
        self.rag_repo = RagRepository(db)

    async def _ensure_unique_slug(
        self,
        *,
        tenant_id: str,
        user_id: str,
        folder: str,
        slug: str,
        exclude_id: str | None = None,
    ) -> str:
        """Return slug or slug-2 etc. on conflict."""
        if not await self.repo.slug_exists(
            tenant_id=tenant_id, user_id=user_id, folder=folder, slug=slug, exclude_id=exclude_id
        ):
            return slug
        for suffix in range(2, 100):
            candidate = f"{slug}-{suffix}"
            if not await self.repo.slug_exists(
                tenant_id=tenant_id, user_id=user_id, folder=folder, slug=candidate, exclude_id=exclude_id
            ):
                return candidate
        return f"{slug}-{generate_id()[:8]}"

    async def _sync_rag_document(self, page: WikiPage, *, tenant_ctx: TenantContext) -> str | None:
        """Create or update a rag_document for a wiki page (source_type=wiki)."""
        if page.status == "deprecated":
            if page.document_id:
                await self.rag_repo.delete_document(
                    page.document_id, tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
                )
                page.document_id = None
                await self.db.flush()
            return None

        if page.document_id:
            await self.rag_repo.delete_document(
                page.document_id, tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
            )

        doc = await self.rag_repo.create_document(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            title=page.title,
            source_type=RagSourceType.WIKI.value,
            source_ref=page.id,
            status="ready",
        )
        page.document_id = doc.id
        await self.db.flush()
        return doc.id

    async def _rebuild_page_links(self, page: WikiPage) -> list[WikiLink]:
        """Parse [[wikilinks]] from page body and rebuild edges."""
        parsed = parse_wikilinks(page.body_md)
        link_data: list[tuple[str, str | None, str | None]] = []
        for wl in parsed:
            target_id = await self.repo.resolve_slug_to_page_id(
                tenant_id=page.tenant_id, user_id=page.user_id, slug=wl.slug
            )
            link_data.append((wl.slug, wl.text, target_id))
        return await self.repo.rebuild_links(page, link_data)

    async def ensure_seed(self, *, tenant_ctx: TenantContext) -> None:
        """Seed meta/index and meta/log if they don't exist."""
        for slug, title, body in [
            ("index", "Wiki Index", "# Wiki Index\n\nMain entry point for your Second Brain wiki."),
            ("log", "Ingest Log", "# Ingest Log\n\nAutomatically maintained by the librarian."),
        ]:
            existing = await self.repo.get_page_by_slug(
                tenant_id=tenant_ctx.tenant_id,
                user_id=tenant_ctx.user_id,
                folder=WikiFolder.META.value,
                slug=slug,
            )
            if existing is None:
                await self.repo.create_page(
                    tenant_id=tenant_ctx.tenant_id,
                    user_id=tenant_ctx.user_id,
                    folder=WikiFolder.META.value,
                    slug=slug,
                    title=title,
                    body_md=body,
                )
        await self.db.flush()

    async def create_page(
        self,
        *,
        tenant_ctx: TenantContext,
        folder: str,
        slug: str | None,
        title: str,
        body_md: str,
        frontmatter: dict | None = None,
        source_url: str | None = None,
    ) -> WikiPageResponse:
        """Create a wiki page. Raw folder => immutable. Slug auto-generated if None."""
        await self.ensure_seed(tenant_ctx=tenant_ctx)

        base_slug = _slugify(slug or title)
        if not base_slug:
            base_slug = "untitled"

        final_slug = await self._ensure_unique_slug(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            folder=folder,
            slug=base_slug,
        )

        is_immutable = folder == WikiFolder.RAW.value

        page = await self.repo.create_page(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            folder=folder,
            slug=final_slug,
            title=title.strip(),
            body_md=body_md,
            frontmatter=frontmatter,
            source_url=source_url,
            immutable=is_immutable,
        )

        await self._sync_rag_document(page, tenant_ctx=tenant_ctx)
        await self._rebuild_page_links(page)
        await self.db.commit()
        return _page_to_response(page)

    async def get_page(
        self,
        *,
        tenant_ctx: TenantContext,
        page_id: str,
    ) -> WikiPageDetailResponse | None:
        page = await self.repo.get_page(
            page_id, tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
        )
        if page is None:
            return None
        outgoing = await self.repo.get_outgoing_links(page.id)
        incoming = await self.repo.get_incoming_links(page.id)
        resp = _page_to_response(page)
        return WikiPageDetailResponse(
            **resp.model_dump(),
            outgoingLinks=[_link_to_response(lnk) for lnk in outgoing],
            incomingLinks=[_link_to_response(lnk) for lnk in incoming],
        )

    async def list_pages(
        self,
        *,
        tenant_ctx: TenantContext,
        folder: str | None = None,
        status: str | None = None,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[WikiPageResponse], int]:
        pages, total = await self.repo.list_pages(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            folder=folder,
            status=status,
            q=q,
            limit=limit,
            offset=offset,
        )
        return [_page_to_response(p) for p in pages], total

    async def update_page(
        self,
        *,
        tenant_ctx: TenantContext,
        page_id: str,
        title: str | None = None,
        body_md: str | None = None,
        frontmatter: dict | None = _UNSET,
        status: str | None = None,
    ) -> WikiPageResponse | None:
        page = await self.repo.get_page(
            page_id, tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
        )
        if page is None:
            return None

        if page.immutable:
            raise ImmutablePageError(page_id)

        page = await self.repo.update_page(
            page,
            title=title,
            body_md=body_md,
            frontmatter=frontmatter if frontmatter is not _UNSET else _UNSET,
            status=status,
        )
        await self._sync_rag_document(page, tenant_ctx=tenant_ctx)
        if body_md is not None:
            await self._rebuild_page_links(page)
        await self.db.commit()
        return _page_to_response(page)

    async def delete_page(
        self,
        *,
        tenant_ctx: TenantContext,
        page_id: str,
    ) -> bool:
        page = await self.repo.get_page(
            page_id, tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
        )
        if page is None:
            return False

        if page.immutable:
            raise ImmutablePageError(page_id)

        if page.document_id:
            await self.rag_repo.delete_document(
                page.document_id, tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
            )

        await self.repo.delete_page(page)
        await self.db.commit()
        return True

    async def deprecate_page(
        self,
        *,
        tenant_ctx: TenantContext,
        page_id: str,
    ) -> WikiPageResponse | None:
        page = await self.repo.get_page(
            page_id, tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
        )
        if page is None:
            return None

        page = await self.repo.update_page(page, status="deprecated")
        await self._sync_rag_document(page, tenant_ctx=tenant_ctx)
        await self.db.commit()
        return _page_to_response(page)

    async def ingest(
        self,
        *,
        tenant_ctx: TenantContext,
        content: str,
        source_url: str | None = None,
        title: str | None = None,
    ) -> WikiIngestResponse:
        """Librarian ingest: Raw → Summary → ripple Entities/Concepts → Log entry.

        Uses deterministic heuristic extractor (no LLM required).
        """
        await self.ensure_seed(tenant_ctx=tenant_ctx)

        # Auto-detect title from first H1 heading if not provided
        if not title:
            first_h1 = re.search(r"^#\s+(.+)", content, re.MULTILINE)
            title = first_h1.group(1).strip() if first_h1 else None
        ingest_title = title or "Untitled ingest"

        raw_page = await self.repo.create_page(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            folder=WikiFolder.RAW.value,
            slug=await self._ensure_unique_slug(
                tenant_id=tenant_ctx.tenant_id,
                user_id=tenant_ctx.user_id,
                folder=WikiFolder.RAW.value,
                slug=_slugify(ingest_title),
            ),
            title=ingest_title,
            body_md=content,
            source_url=source_url,
            immutable=True,
        )
        await self._sync_rag_document(raw_page, tenant_ctx=tenant_ctx)

        summary_body = textwrap.dedent(f"""\
            # Summary: {ingest_title}

            Source: [[{raw_page.slug}|raw]]

            {content[:500]}{"..." if len(content) > 500 else ""}
        """)
        summary_page = await self.repo.create_page(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            folder=WikiFolder.SUMMARIES.value,
            slug=await self._ensure_unique_slug(
                tenant_id=tenant_ctx.tenant_id,
                user_id=tenant_ctx.user_id,
                folder=WikiFolder.SUMMARIES.value,
                slug=_slugify(f"summary-{ingest_title}"),
            ),
            title=f"Summary: {ingest_title}",
            body_md=summary_body,
            source_url=source_url,
        )
        await self._sync_rag_document(summary_page, tenant_ctx=tenant_ctx)
        await self._rebuild_page_links(summary_page)

        # Over-fetch so RIPPLE_MAX_PAGES is the real gate, not the extractor cap.
        entities = _heuristic_extract_entities(content, max_items=RIPPLE_MAX_PAGES + 5)
        rippled_ids: list[str] = []
        truncated = False
        total_pages_count = 2

        for entity_title, entity_body, folder_hint in entities:
            if total_pages_count >= RIPPLE_MAX_PAGES:
                truncated = True
                break
            total_pages_count += 1

            folder = WikiFolder.CONCEPTS.value if folder_hint == "concepts" else WikiFolder.ENTITIES.value

            entity_slug = _slugify(entity_title)
            if not entity_slug:
                entity_slug = "unnamed"

            entity_page = await self.repo.create_page(
                tenant_id=tenant_ctx.tenant_id,
                user_id=tenant_ctx.user_id,
                folder=folder,
                slug=await self._ensure_unique_slug(
                    tenant_id=tenant_ctx.tenant_id,
                    user_id=tenant_ctx.user_id,
                    folder=folder,
                    slug=entity_slug,
                ),
                title=entity_title,
                body_md=f"# {entity_title}\n\n{entity_body}\n\nSource: [[{raw_page.slug}|raw]]",
            )
            await self._sync_rag_document(entity_page, tenant_ctx=tenant_ctx)
            await self._rebuild_page_links(entity_page)
            rippled_ids.append(entity_page.id)

        log_page = await self.repo.get_page_by_slug(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            folder=WikiFolder.META.value,
            slug="log",
        )
        if log_page:
            timestamp = datetime.now(UTC).isoformat()
            trunc_note = " (TRUNCATED — ripple limit reached)" if truncated else ""
            log_entry = (
                f"\n\n## {timestamp} — {ingest_title}{trunc_note}\n"
                f"- Raw: [[{raw_page.slug}]]\n"
                f"- Summary: [[{summary_page.slug}]]\n"
                f"- Rippled: {len(rippled_ids)} pages\n"
            )
            await self.repo.update_page(log_page, body_md=log_page.body_md + log_entry)
            await self._rebuild_page_links(log_page)

        await self.db.commit()

        return WikiIngestResponse(
            rawPageId=raw_page.id,
            summaryPageId=summary_page.id,
            rippledPages=rippled_ids,
            truncated=truncated,
        )

    async def query(
        self,
        *,
        tenant_ctx: TenantContext,
        query: str,
        limit: int = 8,
    ) -> list[dict]:
        """Search wiki pages only (source_type=wiki) via RAG pipeline.

        Excludes deprecated pages. Returns quotes with pageId + slug.
        """
        rag_service = RagService(self.db)
        hits = await rag_service.search(
            tenant_ctx=tenant_ctx,
            query=query,
            limit=limit,
            rag_enabled=True,
            source_types=["wiki"],
        )

        results = []
        for hit in hits:
            page = None
            if hit.documentId:
                doc = await self.rag_repo.get_document(
                    hit.documentId,
                    tenant_id=tenant_ctx.tenant_id,
                    user_id=tenant_ctx.user_id,
                )
                if doc and doc.source_ref:
                    page = await self.repo.get_page(
                        doc.source_ref,
                        tenant_id=tenant_ctx.tenant_id,
                        user_id=tenant_ctx.user_id,
                    )

            if page and page.status == "deprecated":
                continue

            results.append({
                "content": hit.content,
                "score": hit.score,
                "pageId": page.id if page else None,
                "slug": page.slug if page else None,
                "title": hit.title,
            })
        return results

    async def lint(
        self,
        *,
        tenant_ctx: TenantContext,
    ) -> WikiLintResponse:
        """Report dangling links, orphans, pages without links. Auto-fix: rebuild links."""
        issues: list[WikiLintIssue] = []
        fixes = 0

        dangling = await self.repo.find_dangling_links(
            tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
        )
        for link in dangling:
            issues.append(WikiLintIssue(
                type="dangling_link",
                pageId=link.from_page_id,
                slug=link.to_slug,
                detail=f"Link to [[{link.to_slug}]] has no target page",
            ))

        orphans = await self.repo.find_orphan_pages(
            tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
        )
        for page in orphans:
            issues.append(WikiLintIssue(
                type="orphan_page",
                pageId=page.id,
                slug=page.slug,
                detail=f"Page '{page.title}' has no incoming or outgoing links",
            ))

        no_links = await self.repo.find_pages_without_links(
            tenant_id=tenant_ctx.tenant_id, user_id=tenant_ctx.user_id
        )
        for page in no_links:
            if page.id not in {o.id for o in orphans}:
                issues.append(WikiLintIssue(
                    type="no_outgoing_links",
                    pageId=page.id,
                    slug=page.slug,
                    detail=f"Page '{page.title}' has no outgoing links",
                ))

        all_pages, _ = await self.repo.list_pages(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            status="active",
            limit=500,
        )
        for page in all_pages:
            rebuilt = await self._rebuild_page_links(page)
            if rebuilt:
                fixes += 1

        await self.db.commit()

        return WikiLintResponse(issues=issues, fixesApplied=fixes)

    async def get_graph(
        self,
        *,
        tenant_ctx: TenantContext,
        folder: str | None = None,
        max_nodes: int = 300,
    ) -> WikiGraphResponse:
        pages, links = await self.repo.get_graph_data(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            folder=folder,
            max_nodes=max_nodes,
        )
        return WikiGraphResponse(
            nodes=[
                WikiGraphNode(
                    id=p.id,
                    slug=p.slug,
                    title=p.title,
                    folder=p.folder,
                    status=p.status,
                )
                for p in pages
            ],
            edges=[
                WikiGraphEdge(
                    fromId=lnk.from_page_id,
                    toId=lnk.to_page_id,
                    toSlug=lnk.to_slug,
                )
                for lnk in links
            ],
        )


    async def bulk_delete(
        self,
        *,
        tenant_ctx: TenantContext,
        folder: str | None = None,
        status: str | None = None,
        page_ids: list[str] | None = None,
        force: bool = False,
    ) -> int:
        """Bulk delete wiki pages matching given filters / IDs.

        Immutable (raw) pages are skipped unless force=True.
        Cleans up associated RAG documents.
        """
        pages = await self.repo.bulk_delete_pages(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            folder=folder,
            status=status,
            page_ids=page_ids,
            force=force,
        )
        for page in pages:
            if page.document_id:
                await self.rag_repo.delete_document(
                    page.document_id,
                    tenant_id=tenant_ctx.tenant_id,
                    user_id=tenant_ctx.user_id,
                )
        await self.db.commit()
        return len(pages)

    async def purge_all(
        self,
        *,
        tenant_ctx: TenantContext,
    ) -> int:
        """Delete ALL wiki pages for user in tenant. Cleans up RAG documents."""
        pages = await self.repo.purge_all_pages(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
        )
        for page in pages:
            if page.document_id:
                await self.rag_repo.delete_document(
                    page.document_id,
                    tenant_id=tenant_ctx.tenant_id,
                    user_id=tenant_ctx.user_id,
                )
        await self.db.commit()
        return len(pages)


class ImmutablePageError(Exception):
    """Raised when trying to modify or delete an immutable (raw) page."""

    def __init__(self, page_id: str):
        self.page_id = page_id
        super().__init__(f"Page {page_id} is immutable (raw)")
