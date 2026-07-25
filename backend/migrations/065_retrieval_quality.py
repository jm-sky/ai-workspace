"""Migration: retrieval quality — embedding versioning, lexical search, async ingest status.

Usage:
    python migrations/065_retrieval_quality.py upgrade
    python migrations/065_retrieval_quality.py downgrade
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.core.database import engine


async def column_exists(conn, table_name: str, column_name: str) -> bool:
    result = await conn.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = :table_name
                AND column_name = :column_name
            );
        """),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.scalar() is True


async def index_exists(conn, index_name: str) -> bool:
    result = await conn.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE schemaname = 'public'
                AND indexname = :index_name
            );
        """),
        {"index_name": index_name},
    )
    return result.scalar() is True


async def _add_embedding_versioning_columns(conn, table_name: str) -> None:
    if not await column_exists(conn, table_name, "embedding_model"):
        await conn.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN embedding_model VARCHAR(120)")
        )
        print(f"✓ Added {table_name}.embedding_model")
    else:
        print(f"✓ {table_name}.embedding_model already exists")

    if not await column_exists(conn, table_name, "embedding_version"):
        await conn.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN embedding_version INTEGER NOT NULL DEFAULT 1")
        )
        print(f"✓ Added {table_name}.embedding_version")
    else:
        print(f"✓ {table_name}.embedding_version already exists")


async def upgrade() -> None:
    print("Applying retrieval quality migration...")

    async with engine.begin() as conn:
        await _add_embedding_versioning_columns(conn, "document_chunks")
        await _add_embedding_versioning_columns(conn, "memory_entries")

        if not await column_exists(conn, "document_chunks", "content_tsv"):
            await conn.execute(text("ALTER TABLE document_chunks ADD COLUMN content_tsv tsvector"))
            print("✓ Added document_chunks.content_tsv")
        else:
            print("✓ document_chunks.content_tsv already exists")

        if not await index_exists(conn, "idx_document_chunks_content_tsv"):
            await conn.execute(
                text("""
                    CREATE INDEX idx_document_chunks_content_tsv
                    ON document_chunks USING gin (content_tsv)
                    """)
            )
            print("✓ Created idx_document_chunks_content_tsv (GIN)")
        else:
            print("✓ idx_document_chunks_content_tsv already exists")

        if not await index_exists(conn, "idx_document_chunks_embedding_version"):
            await conn.execute(
                text("""
                    CREATE INDEX idx_document_chunks_embedding_version
                    ON document_chunks (embedding_version)
                    """)
            )
            print("✓ Created idx_document_chunks_embedding_version")
        else:
            print("✓ idx_document_chunks_embedding_version already exists")

        if not await column_exists(conn, "rag_documents", "status"):
            await conn.execute(
                text("ALTER TABLE rag_documents ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'ready'")
            )
            print("✓ Added rag_documents.status")
        else:
            print("✓ rag_documents.status already exists")

        if not await column_exists(conn, "rag_documents", "error"):
            await conn.execute(text("ALTER TABLE rag_documents ADD COLUMN error TEXT"))
            print("✓ Added rag_documents.error")
        else:
            print("✓ rag_documents.error already exists")

    print("✓ Retrieval quality migration complete")


async def downgrade() -> None:
    print("Reverting retrieval quality migration...")
    async with engine.begin() as conn:
        await conn.execute(text("DROP INDEX IF EXISTS idx_document_chunks_embedding_version"))
        await conn.execute(text("DROP INDEX IF EXISTS idx_document_chunks_content_tsv"))
        await conn.execute(text("ALTER TABLE rag_documents DROP COLUMN IF EXISTS error"))
        await conn.execute(text("ALTER TABLE rag_documents DROP COLUMN IF EXISTS status"))
        await conn.execute(text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS content_tsv"))
        await conn.execute(text("ALTER TABLE memory_entries DROP COLUMN IF EXISTS embedding_version"))
        await conn.execute(text("ALTER TABLE memory_entries DROP COLUMN IF EXISTS embedding_model"))
        await conn.execute(text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_version"))
        await conn.execute(text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_model"))
    print("✓ Reverted retrieval quality migration")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("upgrade", "downgrade"):
        print("Usage: python migrations/065_retrieval_quality.py [upgrade|downgrade]")
        sys.exit(1)
    asyncio.run(upgrade() if sys.argv[1] == "upgrade" else downgrade())
