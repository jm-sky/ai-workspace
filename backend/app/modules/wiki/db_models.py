"""SQLAlchemy models for wiki_pages and wiki_links."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WikiPage(Base):
    """User-owned wiki page in a folder."""

    __tablename__ = "wiki_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    folder: Mapped[str] = mapped_column(String(20), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    frontmatter: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rag_documents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    outgoing_links: Mapped[list["WikiLink"]] = relationship(
        "WikiLink", foreign_keys="WikiLink.from_page_id", back_populates="from_page", cascade="all, delete-orphan"
    )
    incoming_links: Mapped[list["WikiLink"]] = relationship(
        "WikiLink", foreign_keys="WikiLink.to_page_id", back_populates="to_page"
    )


class WikiLink(Base):
    """Directed edge between wiki pages, parsed from [[wikilinks]]."""

    __tablename__ = "wiki_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    from_page_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False
    )
    to_page_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True
    )
    to_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    link_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    from_page: Mapped[WikiPage] = relationship("WikiPage", foreign_keys=[from_page_id], back_populates="outgoing_links")
    to_page: Mapped[WikiPage | None] = relationship("WikiPage", foreign_keys=[to_page_id], back_populates="incoming_links")
