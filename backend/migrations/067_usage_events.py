"""Migration: OpenRouter usage ledger and period aggregates.

Usage:
    python migrations/067_usage_events.py upgrade
    python migrations/067_usage_events.py downgrade
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
    print("Applying usage events migration...")

    async with engine.begin() as conn:
        if not await table_exists(conn, "usage_events"):
            await conn.execute(text("""
                CREATE TABLE usage_events (
                    id VARCHAR(36) PRIMARY KEY,
                    occurred_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
                    tenant_id VARCHAR(36) NOT NULL
                        REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id VARCHAR(36) NOT NULL
                        REFERENCES users(id) ON DELETE CASCADE,
                    purpose VARCHAR(32) NOT NULL,
                    model VARCHAR(255),
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL,
                    cost_estimated_usd REAL,
                    openrouter_generation_id VARCHAR(128),
                    agent_run_id VARCHAR(36)
                        REFERENCES agent_runs(id) ON DELETE SET NULL,
                    funding_source VARCHAR(16) NOT NULL DEFAULT 'platform',
                    metadata JSONB
                )
            """))
            await conn.execute(text(
                "CREATE INDEX idx_usage_events_tenant_occurred ON usage_events(tenant_id, occurred_at DESC)"
            ))
            await conn.execute(text(
                "CREATE INDEX idx_usage_events_agent_run ON usage_events(agent_run_id)"
            ))
            print("✓ Created usage_events table")
        else:
            print("✓ usage_events table already exists")

        if not await table_exists(conn, "usage_period_totals"):
            await conn.execute(text("""
                CREATE TABLE usage_period_totals (
                    tenant_id VARCHAR(36) NOT NULL
                        REFERENCES tenants(id) ON DELETE CASCADE,
                    period_start TIMESTAMPTZ NOT NULL,
                    period_end TIMESTAMPTZ NOT NULL,
                    purpose_group VARCHAR(32) NOT NULL,
                    cost_usd_sum REAL NOT NULL DEFAULT 0,
                    token_sum BIGINT NOT NULL DEFAULT 0,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
                    PRIMARY KEY (tenant_id, period_start, period_end, purpose_group)
                )
            """))
            print("✓ Created usage_period_totals table")
        else:
            print("✓ usage_period_totals table already exists")


async def downgrade() -> None:
    print("Reverting usage events migration...")
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS usage_period_totals"))
        await conn.execute(text("DROP TABLE IF EXISTS usage_events"))
    print("✓ Dropped usage tables")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    if cmd == "upgrade":
        asyncio.run(upgrade())
    elif cmd == "downgrade":
        asyncio.run(downgrade())
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
