"""Pydantic schemas for Wiki API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WikiPageCreate(BaseModel):
    """Create a wiki page (manual, e.g. inbox digest)."""

    folder: str = Field(..., min_length=1, max_length=20)
    slug: str | None = Field(default=None, max_length=200)
    title: str = Field(..., min_length=1, max_length=500)
    body_md: str = Field(..., min_length=1, max_length=200_000)
    frontmatter: dict[str, Any] | None = None
    source_url: str | None = None


class WikiPageUpdate(BaseModel):
    """Update a wiki page (blocked on immutable)."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    body_md: str | None = Field(default=None, min_length=1, max_length=200_000)
    frontmatter: dict[str, Any] | None = None
    status: str | None = None


class WikiPageResponse(BaseModel):
    id: str
    folder: str
    slug: str
    title: str
    bodyMd: str
    frontmatter: dict[str, Any] | None = None
    sourceUrl: str | None = None
    status: str
    immutable: bool
    documentId: str | None = None
    createdAt: datetime
    updatedAt: datetime


class WikiLinkResponse(BaseModel):
    id: str
    fromPageId: str
    toPageId: str | None = None
    toSlug: str
    linkText: str | None = None


class WikiPageDetailResponse(WikiPageResponse):
    outgoingLinks: list[WikiLinkResponse] = Field(default_factory=list)
    incomingLinks: list[WikiLinkResponse] = Field(default_factory=list)


class WikiPageListResponse(BaseModel):
    pages: list[WikiPageResponse]
    total: int


class WikiIngestRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=200_000)
    source_url: str | None = None
    title: str | None = Field(default=None, max_length=500)


class WikiIngestResponse(BaseModel):
    rawPageId: str
    summaryPageId: str
    rippledPages: list[str]
    truncated: bool


class WikiGraphNode(BaseModel):
    id: str
    slug: str
    title: str
    folder: str
    status: str


class WikiGraphEdge(BaseModel):
    fromId: str
    toId: str | None = None
    toSlug: str


class WikiGraphResponse(BaseModel):
    nodes: list[WikiGraphNode]
    edges: list[WikiGraphEdge]


class WikiLintIssue(BaseModel):
    type: str
    pageId: str | None = None
    slug: str | None = None
    detail: str


class WikiLintResponse(BaseModel):
    issues: list[WikiLintIssue]
    fixesApplied: int = 0
