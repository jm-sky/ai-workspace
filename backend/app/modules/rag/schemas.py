"""Pydantic schemas for RAG API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RagDocumentCreate(BaseModel):
    """Ingest a pasted text document."""

    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1, max_length=100_000)


class RagDocumentResponse(BaseModel):
    """Document metadata (no embeddings)."""

    id: str
    title: str
    sourceType: str
    sourceRef: str | None = None
    metadata: dict[str, Any] | None = None
    chunkCount: int = 0
    status: str = "ready"
    error: str | None = None
    createdAt: datetime
    updatedAt: datetime


class RagFromAttachmentRequest(BaseModel):
    """Ingest a chat attachment's extracted text as a RAG document (opt-in)."""

    attachmentId: str = Field(..., min_length=1)
    title: str | None = Field(default=None, max_length=500)


class RagDocumentListResponse(BaseModel):
    documents: list[RagDocumentResponse]
    total: int


class RagChunkResponse(BaseModel):
    id: str
    chunkIndex: int
    content: str
    tokenEstimate: int | None = None


class RagDocumentDetailResponse(RagDocumentResponse):
    chunks: list[RagChunkResponse] = Field(default_factory=list)


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=50)
    hybrid: bool | None = Field(default=None, description="Override AI_RAG_HYBRID_ENABLED (debug)")
    rerank: bool | None = Field(default=None, description="Override AI_RAG_RERANK_ENABLED (debug)")


class RagSearchHit(BaseModel):
    id: str
    content: str
    score: float
    documentId: str
    title: str
    chunkIndex: int


class RagSearchResponse(BaseModel):
    hits: list[RagSearchHit]
    total: int
