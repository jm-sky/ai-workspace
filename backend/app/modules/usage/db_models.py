"""Database models for OpenRouter usage metering."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UsageEventDB(Base):
    """Append-only ledger row for a single OpenRouter billable operation."""

    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_estimated_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    openrouter_generation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    funding_source: Mapped[str] = mapped_column(String(16), default="platform", nullable=False)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)


class UsagePeriodTotalDB(Base):
    """Rolling totals per tenant billing period and purpose group."""

    __tablename__ = "usage_period_totals"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    purpose_group: Mapped[str] = mapped_column(String(32), primary_key=True)
    cost_usd_sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    token_sum: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
