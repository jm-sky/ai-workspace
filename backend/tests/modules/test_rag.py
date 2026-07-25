"""Tests for RAG chunker, ACL search gate, and rag_search tool."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.rag.chunker import looks_like_markdown, split_markdown, split_text
from app.modules.rag.db_models import RagDocument
from app.modules.rag.services.rag_service import RagService
from app.modules.rag.types import RetrievalAcl, RetrievalHit
from app.modules.tenants.service import TenantContext


def test_split_text_basic_overlap():
    text = "a" * 2500
    chunks = split_text(text, chunk_size=1000, overlap=100, max_chunks=10)
    assert len(chunks) == 3
    assert all(len(c) <= 1000 for c in chunks)


def test_split_text_skips_whitespace_only():
    assert split_text("   \n\t  ") == []


def test_split_text_respects_max_chunks():
    text = "x" * 10_000
    chunks = split_text(text, chunk_size=500, overlap=0, max_chunks=3)
    assert len(chunks) == 3


def test_split_text_rejects_bad_overlap():
    with pytest.raises(ValueError, match="overlap"):
        split_text("hello", chunk_size=10, overlap=10)


def test_looks_like_markdown_detects_heading():
    assert looks_like_markdown("# Title\n\nSome text") is True


def test_looks_like_markdown_false_for_plain_text():
    assert looks_like_markdown("Just a plain paragraph, nothing special.") is False


def test_split_markdown_prefixes_heading_path():
    text = "# A\n\n## B\n\nSome content under B."
    chunks = split_markdown(text, chunk_size=1000, overlap=0, max_chunks=10)
    assert len(chunks) == 1
    assert chunks[0].startswith("A > B\n\n")
    assert chunks[0].endswith("Some content under B.")


def test_split_markdown_does_not_break_code_fence():
    code = "```python\n" + "\n".join(f"line_{i} = {i}" for i in range(30)) + "\n```"
    text = f"# Title\n\nIntro paragraph.\n\n{code}\n\nOutro paragraph."
    # Fence fits comfortably within chunk_size — should stay a single, intact block.
    chunks = split_markdown(text, chunk_size=600, overlap=0, max_chunks=20)

    fence_chunks = [c for c in chunks if "```python" in c]
    assert len(fence_chunks) == 1
    assert fence_chunks[0].count("```") == 2
    assert "line_0 = 0" in fence_chunks[0]
    assert "line_29 = 29" in fence_chunks[0]


def test_split_markdown_falls_back_to_split_text_for_oversized_block():
    long_paragraph = "word " * 500  # far exceeds chunk_size
    text = f"# Title\n\n{long_paragraph.strip()}"
    chunks = split_markdown(text, chunk_size=100, overlap=10, max_chunks=50)

    assert len(chunks) > 1
    assert all(c.startswith("Title\n\n") for c in chunks)


def test_split_markdown_respects_max_chunks():
    text = "\n\n".join(f"## Section {i}\n\nParagraph text {i}." for i in range(50))
    chunks = split_markdown(text, chunk_size=30, overlap=0, max_chunks=5)
    assert len(chunks) == 5


def test_split_markdown_empty_returns_empty():
    assert split_markdown("   \n\t  ") == []


def _tenant_ctx(tenant_id: str = "tenant-a", user_id: str = "user-a") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, user_id=user_id, tenant_role="member")


@pytest.mark.asyncio
async def test_search_returns_empty_when_rag_disabled():
    service = RagService(AsyncMock())
    service._embedding = MagicMock()
    service._embedding.embed = AsyncMock(return_value=[0.1])
    service.retriever = MagicMock()
    service.retriever.search = AsyncMock()

    hits = await service.search(
        tenant_ctx=_tenant_ctx(),
        query="anything",
        rag_enabled=False,
    )

    assert hits == []
    service._embedding.embed.assert_not_awaited()
    service.retriever.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_maps_retriever_hits():
    service = RagService(AsyncMock())
    service._embedding = MagicMock()
    service._embedding.embed = AsyncMock(return_value=[0.2, 0.3])
    service.retriever = MagicMock()
    service.retriever.search = AsyncMock(
        return_value=[
            RetrievalHit(
                id="chunk-1",
                content="Hello world",
                score=0.9,
                document_id="doc-1",
                metadata={"title": "Doc", "chunkIndex": 0},
            )
        ]
    )

    hits = await service.search(
        tenant_ctx=_tenant_ctx(),
        query="hello",
        limit=5,
        rag_enabled=True,
    )

    assert len(hits) == 1
    assert hits[0].documentId == "doc-1"
    assert hits[0].title == "Doc"
    service.retriever.search.assert_awaited_once()
    call_kwargs = service.retriever.search.await_args.kwargs
    assert call_kwargs["acl"] == RetrievalAcl(tenant_id="tenant-a", user_id="user-a")
    assert call_kwargs["limit"] == 5


@pytest.mark.asyncio
async def test_ingest_paste_creates_pending_document_without_embedding():
    """Async ingest (plan 009 dec. #14): POST creates a pending doc and
    returns immediately; embedding happens later via run_chunk_ingest."""
    db = AsyncMock()
    service = RagService(db)
    now = datetime.now(UTC)
    doc = RagDocument(
        id="doc-1",
        tenant_id="tenant-a",
        user_id="user-a",
        title="Note",
        source_type="paste",
        source_ref=None,
        metadata_=None,
        status="pending",
        error=None,
        created_at=now,
        updated_at=now,
    )
    service.repo = MagicMock()
    service.repo.create_document = AsyncMock(return_value=doc)
    service._embedding = MagicMock()
    service._embedding.embed_batch = AsyncMock()

    with patch(
        "app.modules.rag.services.rag_service.split_text",
        return_value=["chunk-a", "chunk-b"],
    ):
        response, chunks = await service.ingest_paste(
            tenant_ctx=_tenant_ctx(),
            title="Note",
            content="ignored body",
        )

    assert response.status == "pending"
    assert response.chunkCount == 0
    assert chunks == ["chunk-a", "chunk-b"]
    service._embedding.embed_batch.assert_not_awaited()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_paste_rejects_content_with_no_chunks():
    service = RagService(AsyncMock())
    service.repo = MagicMock()

    with (
        patch("app.modules.rag.services.rag_service.split_text", return_value=[]),
        pytest.raises(ValueError, match="no chunks"),
    ):
        await service.ingest_paste(tenant_ctx=_tenant_ctx(), title="Note", content="   ")

    service.repo.create_document.assert_not_called()


@pytest.mark.asyncio
async def test_run_chunk_ingest_embeds_and_marks_ready():
    db = AsyncMock()
    service = RagService(db)
    service.repo = MagicMock()
    service.repo.insert_chunk = AsyncMock(return_value="chunk-id")
    service.repo.set_document_status = AsyncMock()
    service._embedding = MagicMock()
    service._embedding.model = "test-embedding-model"
    service._embedding.embed_batch = AsyncMock(side_effect=lambda texts: [[float(len(t))] for t in texts])

    await service.run_chunk_ingest(
        document_id="doc-1",
        tenant_id="tenant-a",
        user_id="user-a",
        chunks=["chunk-a", "chunk-b"],
    )

    assert service.repo.insert_chunk.await_count == 2
    service.repo.set_document_status.assert_awaited_once_with("doc-1", status="ready")
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_chunk_ingest_marks_failed_on_error():
    db = AsyncMock()
    service = RagService(db)
    service.repo = MagicMock()
    service.repo.set_document_status = AsyncMock()
    service._embedding = MagicMock()
    service._embedding.embed_batch = AsyncMock(side_effect=RuntimeError("embedding provider down"))

    await service.run_chunk_ingest(
        document_id="doc-1",
        tenant_id="tenant-a",
        user_id="user-a",
        chunks=["chunk-a"],
    )

    db.rollback.assert_awaited_once()
    service.repo.set_document_status.assert_awaited_once_with(
        "doc-1", status="failed", error="embedding provider down"
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_document_acl_miss():
    db = AsyncMock()
    service = RagService(db)
    service.repo = MagicMock()
    service.repo.delete_document = AsyncMock(return_value=False)

    deleted = await service.delete_document(
        tenant_ctx=_tenant_ctx(tenant_id="other", user_id="other"),
        document_id="doc-1",
    )

    assert deleted is False
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_rag_search_tool_disabled():
    from app.modules.agent.tools.rag import RagSearchTool

    tool = RagSearchTool(
        tenant_ctx=_tenant_ctx(),
        db=AsyncMock(),
        rag_enabled=False,
    )
    result = await tool.execute({"query": "test"})
    assert result["hits"] == []
    assert "disabled" in result["message"].lower()


@pytest.mark.asyncio
async def test_rag_search_tool_requires_query():
    from app.modules.agent.tools.rag import RagSearchTool

    tool = RagSearchTool(
        tenant_ctx=_tenant_ctx(),
        db=AsyncMock(),
        rag_enabled=True,
    )
    assert await tool.execute({}) == {"error": "query is required"}


class _FakeAttachment:
    def __init__(self, *, original_filename: str, extracted_text: str | None):
        self.original_filename = original_filename
        self.extracted_text = extracted_text


@pytest.mark.asyncio
async def test_ingest_from_attachment_returns_none_when_not_owned():
    service = RagService(AsyncMock())
    with patch(
        "app.modules.agent.services.chat_attachment_service.ChatAttachmentService.get_owned",
        new=AsyncMock(return_value=None),
    ):
        result = await service.ingest_from_attachment(
            tenant_ctx=_tenant_ctx(), attachment_id="att-1", title=None
        )
    assert result is None


@pytest.mark.asyncio
async def test_ingest_from_attachment_rejects_empty_extracted_text():
    service = RagService(AsyncMock())
    attachment = _FakeAttachment(original_filename="notes.pdf", extracted_text="   ")
    with (
        patch(
            "app.modules.agent.services.chat_attachment_service.ChatAttachmentService.get_owned",
            new=AsyncMock(return_value=attachment),
        ),
        pytest.raises(ValueError, match="no extracted text"),
    ):
        await service.ingest_from_attachment(tenant_ctx=_tenant_ctx(), attachment_id="att-1", title=None)


@pytest.mark.asyncio
async def test_ingest_from_attachment_creates_pending_document():
    db = AsyncMock()
    service = RagService(db)
    now = datetime.now(UTC)
    doc = RagDocument(
        id="doc-1",
        tenant_id="tenant-a",
        user_id="user-a",
        title="notes.pdf",
        source_type="attachment",
        source_ref="att-1",
        metadata_=None,
        status="pending",
        error=None,
        created_at=now,
        updated_at=now,
    )
    service.repo = MagicMock()
    service.repo.create_document = AsyncMock(return_value=doc)
    attachment = _FakeAttachment(original_filename="notes.pdf", extracted_text="Some extracted body text.")

    with (
        patch(
            "app.modules.agent.services.chat_attachment_service.ChatAttachmentService.get_owned",
            new=AsyncMock(return_value=attachment),
        ),
        patch(
            "app.modules.rag.services.rag_service.split_text",
            return_value=["chunk-a"],
        ),
    ):
        result = await service.ingest_from_attachment(
            tenant_ctx=_tenant_ctx(), attachment_id="att-1", title=None
        )

    assert result is not None
    response, chunks = result
    assert response.sourceType == "attachment"
    assert response.status == "pending"
    assert chunks == ["chunk-a"]
    create_kwargs = service.repo.create_document.await_args.kwargs
    assert create_kwargs["source_ref"] == "att-1"
    assert create_kwargs["title"] == "notes.pdf"
    db.commit.assert_awaited_once()
