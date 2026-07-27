"""Migration: wiki_pages + wiki_links tables for Second Brain.

Usage:
    python migrations/066_wiki_pages.py upgrade
    python migrations/066_wiki_pages.py downgrade
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.core.database import engine


async def table_exists(conn, table_name: str) -> bool:
    result = await conn.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            );
        """),
        {"table_name": table_name},
    )
    return result.scalar() is True


async def upgrade() -> None:
    print("Applying wiki_pages migration (066)...")

    async with engine.begin() as conn:
        if not await table_exists(conn, "wiki_pages"):
            await conn.execute(text("""
                CREATE TABLE wiki_pages (
                    id VARCHAR(36) PRIMARY KEY,
                    tenant_id VARCHAR(36) NOT NULL
                        REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id VARCHAR(36) NOT NULL
                        REFERENCES users(id) ON DELETE CASCADE,
                    folder VARCHAR(20) NOT NULL,
                    slug VARCHAR(200) NOT NULL,
                    title TEXT NOT NULL,
                    body_md TEXT NOT NULL,
                    frontmatter JSONB,
                    source_url TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    immutable BOOLEAN NOT NULL DEFAULT false,
                    document_id VARCHAR(36)
                        REFERENCES rag_documents(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
                    CONSTRAINT chk_wiki_folder CHECK (
                        folder IN ('raw', 'inbox', 'entities', 'concepts', 'summaries', 'meta')
                    ),
                    CONSTRAINT chk_wiki_status CHECK (
                        status IN ('active', 'deprecated')
                    ),
                    CONSTRAINT uq_wiki_pages_slug
                        UNIQUE (tenant_id, user_id, folder, slug)
                )
            """))
            await conn.execute(text("""
                CREATE INDEX idx_wiki_pages_tenant_user_folder
                ON wiki_pages(tenant_id, user_id, folder)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_wiki_pages_tenant_user_updated
                ON wiki_pages(tenant_id, user_id, updated_at DESC)
            """))
            print("✓ Created wiki_pages table")
        else:
            print("✓ wiki_pages table already exists")

        if not await table_exists(conn, "wiki_links"):
            await conn.execute(text("""
                CREATE TABLE wiki_links (
                    id VARCHAR(36) PRIMARY KEY,
                    tenant_id VARCHAR(36) NOT NULL,
                    user_id VARCHAR(36) NOT NULL,
                    from_page_id VARCHAR(36) NOT NULL
                        REFERENCES wiki_pages(id) ON DELETE CASCADE,
                    to_page_id VARCHAR(36)
                        REFERENCES wiki_pages(id) ON DELETE SET NULL,
                    to_slug VARCHAR(200) NOT NULL,
                    link_text TEXT
                )
            """))
            await conn.execute(text("""
                CREATE INDEX idx_wiki_links_tenant_user
                ON wiki_links(tenant_id, user_id)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_wiki_links_from_page
                ON wiki_links(from_page_id)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_wiki_links_to_slug
                ON wiki_links(to_slug)
            """))
            print("✓ Created wiki_links table")
        else:
            print("✓ wiki_links table already exists")

    print("Wiki pages migration (066) complete.")


async def downgrade() -> None:
    print("Reverting wiki_pages migration (066)...")
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS wiki_links CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS wiki_pages CASCADE;"))
    print("✓ Dropped wiki_links and wiki_pages")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    if command == "upgrade":
        asyncio.run(upgrade())
    elif command == "downgrade":
        asyncio.run(downgrade())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
