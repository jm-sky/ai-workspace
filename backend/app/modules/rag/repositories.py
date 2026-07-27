"""Persistence for RAG documents and chunks."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.embeddings import EmbeddingService
from app.common.id_utils import generate_id
from app.core.config import settings
from app.modules.rag.db_models import DocumentChunk, RagDocument
from app.modules.rag.fts import resolve_fts_config
from app.modules.rag.types import RetrievalAcl, RetrievalHit


class RagRepository:
    """CRUD + permissions-aware vector search for document chunks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_document(
        self,
        *,
        tenant_id: str,
        user_id: str,
        title: str,
        source_type: str = "paste",
        source_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "ready",
    ) -> RagDocument:
        now = datetime.now(UTC)
        doc = RagDocument(
            id=generate_id(),
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            source_type=source_type,
            source_ref=source_ref,
            metadata_=metadata,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def set_document_status(
        self,
        document_id: str,
        *,
        status: str,
        error: str | None = None,
    ) -> None:
        await self.db.execute(
            text("""
                UPDATE rag_documents
                SET status = :status, error = :error, updated_at = :updated_at
                WHERE id = :id
                """),
            {
                "id": document_id,
                "status": status,
                "error": error,
                "updated_at": datetime.now(UTC),
            },
        )

    async def insert_chunk(
        self,
        *,
        document_id: str,
        tenant_id: str,
        user_id: str,
        chunk_index: int,
        content: str,
        embedding: list[float],
        token_estimate: int | None = None,
        embedding_model: str | None = None,
        embedding_version: int = 1,
    ) -> str:
        chunk_id = generate_id()
        now = datetime.now(UTC)
        vector_literal = EmbeddingService.vector_to_pg_literal(embedding)
        await self.db.execute(
            text("""
                INSERT INTO document_chunks (
                    id, document_id, tenant_id, user_id, chunk_index,
                    content, token_estimate, embedding,
                    embedding_model, embedding_version, content_tsv, created_at
                ) VALUES (
                    :id, :document_id, :tenant_id, :user_id, :chunk_index,
                    :content, :token_estimate, CAST(:embedding AS vector),
                    :embedding_model, :embedding_version,
                    to_tsvector(CAST(:fts_config AS regconfig), :content), :created_at
                )
                """),
            {
                "id": chunk_id,
                "document_id": document_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "chunk_index": chunk_index,
                "content": content,
                "token_estimate": token_estimate,
                "embedding": vector_literal,
                "embedding_model": embedding_model,
                "embedding_version": embedding_version,
                "fts_config": await resolve_fts_config(self.db),
                "created_at": now,
            },
        )
        return chunk_id

    async def get_document(
        self,
        document_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> RagDocument | None:
        result = await self.db.execute(
            select(RagDocument).where(
                RagDocument.id == document_id,
                RagDocument.tenant_id == tenant_id,
                RagDocument.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[RagDocument, int]], int]:
        count_result = await self.db.execute(
            select(func.count())
            .select_from(RagDocument)
            .where(
                RagDocument.tenant_id == tenant_id,
                RagDocument.user_id == user_id,
            )
        )
        total = int(count_result.scalar() or 0)

        chunk_count = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == RagDocument.id)
            .correlate(RagDocument)
            .scalar_subquery()
        )
        result = await self.db.execute(
            select(RagDocument, chunk_count.label("chunk_count"))
            .where(
                RagDocument.tenant_id == tenant_id,
                RagDocument.user_id == user_id,
            )
            .order_by(RagDocument.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = [(row[0], int(row[1] or 0)) for row in result.all()]
        return rows, total

    async def list_chunks(
        self,
        document_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> list[DocumentChunk]:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.user_id == user_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(result.scalars().all())

    async def count_chunks_needing_reembed(self, *, current_version: int) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.embedding_version < current_version)
        )
        return int(result.scalar() or 0)

    async def list_chunks_needing_reembed(
        self,
        *,
        current_version: int,
        batch_size: int,
    ) -> list[DocumentChunk]:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.embedding_version < current_version)
            .order_by(DocumentChunk.created_at.asc())
            .limit(batch_size)
        )
        return list(result.scalars().all())

    async def update_chunk_embedding(
        self,
        chunk_id: str,
        *,
        embedding: list[float],
        embedding_model: str,
        embedding_version: int,
    ) -> None:
        vector_literal = EmbeddingService.vector_to_pg_literal(embedding)
        await self.db.execute(
            text("""
                UPDATE document_chunks
                SET embedding = CAST(:embedding AS vector),
                    embedding_model = :embedding_model,
                    embedding_version = :embedding_version
                WHERE id = :id
                """),
            {
                "id": chunk_id,
                "embedding": vector_literal,
                "embedding_model": embedding_model,
                "embedding_version": embedding_version,
            },
        )

    async def delete_document(
        self,
        document_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        doc = await self.get_document(document_id, tenant_id=tenant_id, user_id=user_id)
        if doc is None:
            return False
        await self.db.execute(
            delete(RagDocument).where(
                RagDocument.id == document_id,
                RagDocument.tenant_id == tenant_id,
                RagDocument.user_id == user_id,
            )
        )
        return True

    async def search_chunks(
        self,
        *,
        query_embedding: list[float],
        acl: RetrievalAcl,
        limit: int = 8,
        min_similarity: float = 0.5,
        query_text: str | None = None,
        source_types: list[str] | None = None,
    ) -> list[RetrievalHit]:
        """Dense (vector) search, fused with lexical search via RRF when hybrid is enabled.

        ACL is applied in the WHERE clause of both branches, before ranking.
        """
        dense_hits = await self._search_dense(
            query_embedding=query_embedding,
            acl=acl,
            limit=limit,
            min_similarity=min_similarity,
            source_types=source_types,
        )

        if not settings.ai.rag_hybrid_enabled or not query_text:
            return dense_hits

        lexical_hits = await self._search_lexical(query_text=query_text, acl=acl, limit=limit, source_types=source_types)
        if not lexical_hits:
            return dense_hits

        return _reciprocal_rank_fusion(
            [dense_hits, lexical_hits],
            k=settings.ai.rag_rrf_k,
            limit=limit,
        )

    async def _search_dense(
        self,
        *,
        query_embedding: list[float],
        acl: RetrievalAcl,
        limit: int,
        min_similarity: float,
        source_types: list[str] | None = None,
    ) -> list[RetrievalHit]:
        vector_literal = EmbeddingService.vector_to_pg_literal(query_embedding)
        source_filter = ""
        params: dict = {
            "tenant_id": acl.tenant_id,
            "user_id": acl.user_id,
            "query_vec": vector_literal,
            "min_similarity": min_similarity,
            "limit": limit,
        }
        if source_types:
            source_filter = " AND d.source_type = ANY(:source_types)"
            params["source_types"] = source_types
        result = await self.db.execute(
            text(f"""
                SELECT
                    c.id,
                    c.content,
                    c.document_id,
                    c.chunk_index,
                    d.title,
                    1 - (c.embedding <=> CAST(:query_vec AS vector)) AS similarity
                FROM document_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE c.tenant_id = :tenant_id
                  AND c.user_id = :user_id
                  AND c.embedding IS NOT NULL
                  AND 1 - (c.embedding <=> CAST(:query_vec AS vector)) >= :min_similarity{source_filter}
                ORDER BY c.embedding <=> CAST(:query_vec AS vector)
                LIMIT :limit
                """),
            params,
        )
        return [
            RetrievalHit(
                id=row["id"],
                content=row["content"],
                score=float(row["similarity"]),
                document_id=row["document_id"],
                metadata={"title": row["title"], "chunkIndex": row["chunk_index"]},
            )
            for row in result.mappings().all()
        ]

    async def _search_lexical(
        self,
        *,
        query_text: str,
        acl: RetrievalAcl,
        limit: int,
        source_types: list[str] | None = None,
    ) -> list[RetrievalHit]:
        fts_config = await resolve_fts_config(self.db)
        source_filter = ""
        params: dict = {
            "tenant_id": acl.tenant_id,
            "user_id": acl.user_id,
            "fts_config": fts_config,
            "query_text": query_text,
            "limit": limit,
        }
        if source_types:
            source_filter = " AND d.source_type = ANY(:source_types)"
            params["source_types"] = source_types
        result = await self.db.execute(
            text(f"""
                SELECT
                    c.id,
                    c.content,
                    c.document_id,
                    c.chunk_index,
                    d.title,
                    ts_rank_cd(c.content_tsv, plainto_tsquery(CAST(:fts_config AS regconfig), :query_text)) AS rank
                FROM document_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE c.tenant_id = :tenant_id
                  AND c.user_id = :user_id
                  AND c.content_tsv IS NOT NULL
                  AND c.content_tsv @@ plainto_tsquery(CAST(:fts_config AS regconfig), :query_text){source_filter}
                ORDER BY rank DESC
                LIMIT :limit
                """),
            params,
        )
        return [
            RetrievalHit(
                id=row["id"],
                content=row["content"],
                score=float(row["rank"]),
                document_id=row["document_id"],
                metadata={"title": row["title"], "chunkIndex": row["chunk_index"]},
            )
            for row in result.mappings().all()
        ]


def _reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievalHit]],
    *,
    k: int,
    limit: int,
) -> list[RetrievalHit]:
    """RRF: score(chunk) = sum(1 / (k + rank)) across every list it appears in."""
    scores: dict[str, float] = {}
    hit_by_id: dict[str, RetrievalHit] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked, start=1):
            scores[hit.id] = scores.get(hit.id, 0.0) + 1.0 / (k + rank)
            hit_by_id.setdefault(hit.id, hit)

    ordered_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    fused: list[RetrievalHit] = []
    for chunk_id in ordered_ids[:limit]:
        base = hit_by_id[chunk_id]
        fused.append(
            RetrievalHit(
                id=base.id,
                content=base.content,
                score=scores[chunk_id],
                document_id=base.document_id,
                metadata=base.metadata,
            )
        )
    return fused


class PgChunkRetriever:
    """ChunkRetriever backed by Postgres/pgvector."""

    def __init__(self, repo: RagRepository):
        self._repo = repo

    async def search(
        self,
        *,
        query_embedding: list[float],
        acl: RetrievalAcl,
        limit: int,
        min_similarity: float,
        query_text: str | None = None,
        source_types: list[str] | None = None,
    ) -> list[RetrievalHit]:
        return await self._repo.search_chunks(
            query_embedding=query_embedding,
            acl=acl,
            limit=limit,
            min_similarity=min_similarity,
            query_text=query_text,
            source_types=source_types,
        )
