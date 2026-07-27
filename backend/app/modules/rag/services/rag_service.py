"""Business logic for document RAG ingest and search."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.embeddings import EmbeddingService
from app.core.config import settings
from app.modules.rag.chunker import looks_like_markdown, split_markdown, split_text
from app.modules.rag.repositories import PgChunkRetriever, RagRepository
from app.modules.rag.schemas import (
    RagChunkResponse,
    RagDocumentDetailResponse,
    RagDocumentResponse,
    RagSearchHit,
)
from app.modules.rag.types import RagSourceType, Reranker, RetrievalAcl, resolve_reranker
from app.modules.tenants.service import TenantContext

logger = logging.getLogger(__name__)


class RagService:
    """Ingest pasted text, search chunks with ACL, manage documents."""

    def __init__(self, db: AsyncSession, *, reranker: Reranker | None = None):
        self.db = db
        self.repo = RagRepository(db)
        self.retriever = PgChunkRetriever(self.repo)
        self.reranker = reranker or resolve_reranker()
        self._embedding: EmbeddingService | None = None

    def _embedder(self) -> EmbeddingService:
        if self._embedding is None:
            self._embedding = EmbeddingService()
        return self._embedding

    async def ingest_paste(
        self,
        *,
        tenant_ctx: TenantContext,
        title: str,
        content: str,
    ) -> tuple[RagDocumentResponse, list[str]]:
        """Create the document as `pending` and return immediately.

        Chunking runs synchronously here (cheap, fails fast on empty
        content); embedding + insert happens later via `run_chunk_ingest`,
        scheduled outside the HTTP request cycle (plan 009 dec. #14).
        """
        chunker = split_markdown if looks_like_markdown(content) else split_text
        chunks = chunker(
            content,
            chunk_size=settings.ai.rag_chunk_size,
            overlap=settings.ai.rag_chunk_overlap,
            max_chunks=settings.ai.rag_max_chunks_per_document,
        )
        if not chunks:
            raise ValueError("content produced no chunks")

        doc = await self.repo.create_document(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            title=title.strip(),
            source_type=RagSourceType.PASTE.value,
            status="pending",
        )
        await self.db.commit()

        response = RagDocumentResponse(
            id=doc.id,
            title=doc.title,
            sourceType=doc.source_type,
            sourceRef=doc.source_ref,
            metadata=doc.metadata_,
            chunkCount=0,
            status=doc.status,
            error=doc.error,
            createdAt=doc.created_at,
            updatedAt=doc.updated_at,
        )
        return response, chunks

    async def ingest_from_attachment(
        self,
        *,
        tenant_ctx: TenantContext,
        attachment_id: str,
        title: str | None = None,
    ) -> tuple[RagDocumentResponse, list[str]] | None:
        """Ingest a chat attachment's extracted text (opt-in, plan 009 dec. #15).

        Returns None when the attachment doesn't exist or isn't owned by the
        caller (router maps that to 404) — mirrors ChatAttachmentService ACL.
        """
        from app.modules.agent.services.chat_attachment_service import ChatAttachmentService

        attachment = await ChatAttachmentService(self.db).get_owned(attachment_id, tenant_ctx=tenant_ctx)
        if attachment is None:
            return None

        text_content = (attachment.extracted_text or "").strip()
        if not text_content:
            raise ValueError("attachment has no extracted text")

        chunker = split_markdown if looks_like_markdown(text_content) else split_text
        chunks = chunker(
            text_content,
            chunk_size=settings.ai.rag_chunk_size,
            overlap=settings.ai.rag_chunk_overlap,
            max_chunks=settings.ai.rag_max_chunks_per_document,
        )
        if not chunks:
            raise ValueError("content produced no chunks")

        doc = await self.repo.create_document(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            title=(title or attachment.original_filename).strip(),
            source_type=RagSourceType.ATTACHMENT.value,
            source_ref=attachment_id,
            status="pending",
        )
        await self.db.commit()

        response = RagDocumentResponse(
            id=doc.id,
            title=doc.title,
            sourceType=doc.source_type,
            sourceRef=doc.source_ref,
            metadata=doc.metadata_,
            chunkCount=0,
            status=doc.status,
            error=doc.error,
            createdAt=doc.created_at,
            updatedAt=doc.updated_at,
        )
        return response, chunks

    async def run_chunk_ingest(
        self,
        *,
        document_id: str,
        tenant_id: str,
        user_id: str,
        chunks: list[str],
    ) -> None:
        """Embed + persist chunks for a pending document; flips status to
        `ready`/`failed`. Intended to run outside the HTTP request cycle."""
        try:
            embedder = self._embedder()
            embeddings = await embedder.embed_batch(chunks)
            for index, (piece, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                await self.repo.insert_chunk(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    chunk_index=index,
                    content=piece,
                    embedding=embedding,
                    token_estimate=max(1, len(piece) // 4),
                    embedding_model=embedder.model,
                    embedding_version=settings.ai.embedding_version,
                )
            await self.repo.set_document_status(document_id, status="ready")
            await self.db.commit()
        except Exception as exc:
            logger.exception("RAG ingest failed for document %s", document_id)
            await self.db.rollback()
            await self.repo.set_document_status(document_id, status="failed", error=str(exc))
            await self.db.commit()

    async def reembed_stale_chunks(self, *, batch_size: int = 100, dry_run: bool = False) -> int:
        """Re-embed document_chunks with embedding_version below the current config.

        Resumable (filters by embedding_version, commits per batch) and
        idempotent (a second run once caught up processes 0 rows).
        """
        current_version = settings.ai.embedding_version
        if dry_run:
            return await self.repo.count_chunks_needing_reembed(current_version=current_version)

        total = 0
        while True:
            chunks = await self.repo.list_chunks_needing_reembed(
                current_version=current_version,
                batch_size=batch_size,
            )
            if not chunks:
                break
            embedder = self._embedder()
            embeddings = await embedder.embed_batch([chunk.content for chunk in chunks])
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                await self.repo.update_chunk_embedding(
                    chunk.id,
                    embedding=embedding,
                    embedding_model=embedder.model,
                    embedding_version=current_version,
                )
            await self.db.commit()
            total += len(chunks)
        return total

    async def list_documents(
        self,
        *,
        tenant_ctx: TenantContext,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RagDocumentResponse], int]:
        rows, total = await self.repo.list_documents(
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            limit=limit,
            offset=offset,
        )
        items = [
            RagDocumentResponse(
                id=doc.id,
                title=doc.title,
                sourceType=doc.source_type,
                sourceRef=doc.source_ref,
                metadata=doc.metadata_,
                chunkCount=chunk_count,
                status=doc.status,
                error=doc.error,
                createdAt=doc.created_at,
                updatedAt=doc.updated_at,
            )
            for doc, chunk_count in rows
        ]
        return items, total

    async def get_document(
        self,
        *,
        tenant_ctx: TenantContext,
        document_id: str,
    ) -> RagDocumentDetailResponse | None:
        doc = await self.repo.get_document(
            document_id,
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
        )
        if doc is None:
            return None
        chunks = await self.repo.list_chunks(
            document_id,
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
        )
        return RagDocumentDetailResponse(
            id=doc.id,
            title=doc.title,
            sourceType=doc.source_type,
            sourceRef=doc.source_ref,
            metadata=doc.metadata_,
            chunkCount=len(chunks),
            status=doc.status,
            error=doc.error,
            createdAt=doc.created_at,
            updatedAt=doc.updated_at,
            chunks=[
                RagChunkResponse(
                    id=chunk.id,
                    chunkIndex=chunk.chunk_index,
                    content=chunk.content,
                    tokenEstimate=chunk.token_estimate,
                )
                for chunk in chunks
            ],
        )

    async def delete_document(
        self,
        *,
        tenant_ctx: TenantContext,
        document_id: str,
    ) -> bool:
        deleted = await self.repo.delete_document(
            document_id,
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
        )
        if deleted:
            await self.db.commit()
        return deleted

    async def search(
        self,
        *,
        tenant_ctx: TenantContext,
        query: str,
        limit: int | None = None,
        rag_enabled: bool = True,
        hybrid: bool | None = None,
        rerank: bool | None = None,
        source_types: list[str] | None = None,
    ) -> list[RagSearchHit]:
        if not rag_enabled:
            return []

        final_limit = limit or settings.ai.rag_search_limit
        use_reranker = settings.ai.rag_rerank_enabled if rerank is None else rerank
        # No point over-fetching candidates when nothing will rerank them down.
        candidate_limit = settings.ai.rag_rerank_candidates if use_reranker else final_limit

        embedder = self._embedder()
        query_embedding = await embedder.embed(query)
        hits = await self.retriever.search(
            query_embedding=query_embedding,
            acl=RetrievalAcl(
                tenant_id=tenant_ctx.tenant_id,
                user_id=tenant_ctx.user_id,
            ),
            limit=candidate_limit,
            min_similarity=settings.ai.rag_similarity_threshold,
            query_text=query if (settings.ai.rag_hybrid_enabled if hybrid is None else hybrid) else None,
            source_types=source_types,
        )

        if use_reranker:
            hits = await self.reranker.rerank(query=query, hits=hits, top_n=final_limit)

        return [
            RagSearchHit(
                id=hit.id,
                content=hit.content,
                score=hit.score,
                documentId=hit.document_id,
                title=str(hit.metadata.get("title") or ""),
                chunkIndex=int(hit.metadata.get("chunkIndex") or 0),
            )
            for hit in hits
        ]


async def run_rag_ingest_in_background(
    *,
    document_id: str,
    tenant_id: str,
    user_id: str,
    chunks: list[str],
) -> None:
    """FastAPI BackgroundTasks entrypoint — opens its own DB session since the
    request-scoped session is closed once the 202 response is sent."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = RagService(db)
        await service.run_chunk_ingest(
            document_id=document_id,
            tenant_id=tenant_id,
            user_id=user_id,
            chunks=chunks,
        )
