"""Persistence for wiki pages and links."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.id_utils import generate_id
from app.modules.wiki.db_models import WikiLink, WikiPage

_UNSET: Any = object()


class WikiRepository:
    """CRUD + ACL-filtered queries for wiki pages and links."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_page(
        self,
        *,
        tenant_id: str,
        user_id: str,
        folder: str,
        slug: str,
        title: str,
        body_md: str,
        frontmatter: dict | None = None,
        source_url: str | None = None,
        immutable: bool = False,
        document_id: str | None = None,
    ) -> WikiPage:
        now = datetime.now(UTC)
        page = WikiPage(
            id=generate_id(),
            tenant_id=tenant_id,
            user_id=user_id,
            folder=folder,
            slug=slug,
            title=title,
            body_md=body_md,
            frontmatter=frontmatter,
            source_url=source_url,
            status="active",
            immutable=immutable,
            document_id=document_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(page)
        await self.db.flush()
        return page

    async def get_page(
        self,
        page_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> WikiPage | None:
        result = await self.db.execute(
            select(WikiPage).where(
                WikiPage.id == page_id,
                WikiPage.tenant_id == tenant_id,
                WikiPage.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_page_by_slug(
        self,
        *,
        tenant_id: str,
        user_id: str,
        folder: str,
        slug: str,
    ) -> WikiPage | None:
        result = await self.db.execute(
            select(WikiPage).where(
                WikiPage.tenant_id == tenant_id,
                WikiPage.user_id == user_id,
                WikiPage.folder == folder,
                WikiPage.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def list_pages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        folder: str | None = None,
        status: str | None = None,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[WikiPage], int]:
        base = select(WikiPage).where(
            WikiPage.tenant_id == tenant_id,
            WikiPage.user_id == user_id,
        )
        count_base = (
            select(func.count())
            .select_from(WikiPage)
            .where(
                WikiPage.tenant_id == tenant_id,
                WikiPage.user_id == user_id,
            )
        )
        if folder:
            base = base.where(WikiPage.folder == folder)
            count_base = count_base.where(WikiPage.folder == folder)
        if status:
            base = base.where(WikiPage.status == status)
            count_base = count_base.where(WikiPage.status == status)
        if q:
            like_q = f"%{q}%"
            base = base.where(WikiPage.title.ilike(like_q) | WikiPage.body_md.ilike(like_q))
            count_base = count_base.where(WikiPage.title.ilike(like_q) | WikiPage.body_md.ilike(like_q))

        total_result = await self.db.execute(count_base)
        total = int(total_result.scalar() or 0)

        result = await self.db.execute(
            base.order_by(WikiPage.updated_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total

    async def update_page(
        self,
        page: WikiPage,
        *,
        title: str | None = None,
        body_md: str | None = None,
        frontmatter: Any = _UNSET,
        status: str | None = None,
        document_id: Any = _UNSET,
    ) -> WikiPage:
        if title is not None:
            page.title = title
        if body_md is not None:
            page.body_md = body_md
        if frontmatter is not _UNSET:
            page.frontmatter = frontmatter
        if status is not None:
            page.status = status
        if document_id is not _UNSET:
            page.document_id = document_id
        page.updated_at = datetime.now(UTC)
        await self.db.flush()
        return page

    async def delete_page(self, page: WikiPage) -> None:
        await self.db.delete(page)
        await self.db.flush()

    async def slug_exists(
        self,
        *,
        tenant_id: str,
        user_id: str,
        folder: str,
        slug: str,
        exclude_id: str | None = None,
    ) -> bool:
        q = select(func.count()).select_from(WikiPage).where(
            WikiPage.tenant_id == tenant_id,
            WikiPage.user_id == user_id,
            WikiPage.folder == folder,
            WikiPage.slug == slug,
        )
        if exclude_id:
            q = q.where(WikiPage.id != exclude_id)
        result = await self.db.execute(q)
        return (int(result.scalar() or 0)) > 0

    async def rebuild_links(
        self,
        page: WikiPage,
        links: list[tuple[str, str | None, str | None]],
    ) -> list[WikiLink]:
        """Delete existing outgoing links and insert new ones.

        links: list of (to_slug, link_text, to_page_id | None)
        """
        await self.db.execute(
            delete(WikiLink).where(WikiLink.from_page_id == page.id)
        )
        result = []
        for to_slug, link_text, to_page_id in links:
            link = WikiLink(
                id=generate_id(),
                tenant_id=page.tenant_id,
                user_id=page.user_id,
                from_page_id=page.id,
                to_page_id=to_page_id,
                to_slug=to_slug,
                link_text=link_text,
            )
            self.db.add(link)
            result.append(link)
        await self.db.flush()
        return result

    async def get_outgoing_links(self, page_id: str) -> list[WikiLink]:
        result = await self.db.execute(
            select(WikiLink).where(WikiLink.from_page_id == page_id)
        )
        return list(result.scalars().all())

    async def get_incoming_links(self, page_id: str) -> list[WikiLink]:
        result = await self.db.execute(
            select(WikiLink).where(WikiLink.to_page_id == page_id)
        )
        return list(result.scalars().all())

    async def resolve_slug_to_page_id(
        self,
        *,
        tenant_id: str,
        user_id: str,
        slug: str,
    ) -> str | None:
        """Try to resolve a slug across all folders (first match wins)."""
        result = await self.db.execute(
            select(WikiPage.id).where(
                WikiPage.tenant_id == tenant_id,
                WikiPage.user_id == user_id,
                WikiPage.slug == slug,
                WikiPage.status == "active",
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_graph_data(
        self,
        *,
        tenant_id: str,
        user_id: str,
        folder: str | None = None,
        max_nodes: int = 300,
    ) -> tuple[list[WikiPage], list[WikiLink]]:
        page_q = (
            select(WikiPage)
            .where(
                WikiPage.tenant_id == tenant_id,
                WikiPage.user_id == user_id,
                WikiPage.status == "active",
            )
            .order_by(WikiPage.updated_at.desc())
            .limit(max_nodes)
        )
        if folder:
            page_q = page_q.where(WikiPage.folder == folder)

        pages_result = await self.db.execute(page_q)
        pages = list(pages_result.scalars().all())
        page_ids = {p.id for p in pages}

        if not page_ids:
            return pages, []

        links_result = await self.db.execute(
            select(WikiLink).where(
                WikiLink.tenant_id == tenant_id,
                WikiLink.user_id == user_id,
                WikiLink.from_page_id.in_(page_ids),
            )
        )
        links = list(links_result.scalars().all())
        return pages, links

    async def find_dangling_links(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> list[WikiLink]:
        result = await self.db.execute(
            select(WikiLink).where(
                WikiLink.tenant_id == tenant_id,
                WikiLink.user_id == user_id,
                WikiLink.to_page_id.is_(None),
            )
        )
        return list(result.scalars().all())

    async def find_orphan_pages(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> list[WikiPage]:
        """Pages with no incoming or outgoing links (excluding meta)."""
        linked_ids = (
            select(WikiLink.from_page_id)
            .where(WikiLink.tenant_id == tenant_id, WikiLink.user_id == user_id)
            .union(
                select(WikiLink.to_page_id)
                .where(
                    WikiLink.tenant_id == tenant_id,
                    WikiLink.user_id == user_id,
                    WikiLink.to_page_id.isnot(None),
                )
            )
        )
        result = await self.db.execute(
            select(WikiPage).where(
                WikiPage.tenant_id == tenant_id,
                WikiPage.user_id == user_id,
                WikiPage.folder != "meta",
                WikiPage.status == "active",
                WikiPage.id.notin_(linked_ids),
            )
        )
        return list(result.scalars().all())

    async def find_pages_without_links(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> list[WikiPage]:
        """Active pages that have zero outgoing links."""
        pages_with_outgoing = (
            select(WikiLink.from_page_id)
            .where(WikiLink.tenant_id == tenant_id, WikiLink.user_id == user_id)
            .distinct()
        )
        result = await self.db.execute(
            select(WikiPage).where(
                WikiPage.tenant_id == tenant_id,
                WikiPage.user_id == user_id,
                WikiPage.status == "active",
                WikiPage.folder != "meta",
                WikiPage.id.notin_(pages_with_outgoing),
            )
        )
        return list(result.scalars().all())
