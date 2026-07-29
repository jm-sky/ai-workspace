"""Persistence for usage events and period aggregates."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.id_utils import generate_id
from app.modules.usage.db_models import UsageEventDB, UsagePeriodTotalDB
from app.modules.usage.types import FundingSource, UsagePurpose, UsagePurposeGroup


class UsageRepository:
    """Data access for usage ledger."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def insert_event(
        self,
        *,
        tenant_id: str,
        user_id: str,
        purpose: UsagePurpose | str,
        model: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float | None,
        cost_estimated_usd: float | None,
        openrouter_generation_id: str | None,
        agent_run_id: str | None,
        funding_source: FundingSource | str,
        metadata: dict[str, Any] | None,
        occurred_at: datetime | None = None,
    ) -> UsageEventDB:
        event = UsageEventDB(
            id=generate_id(),
            occurred_at=occurred_at or datetime.now(UTC),
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=str(purpose),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            cost_estimated_usd=cost_estimated_usd,
            openrouter_generation_id=openrouter_generation_id,
            agent_run_id=agent_run_id,
            funding_source=str(funding_source),
            event_metadata=metadata,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def bump_period_total(
        self,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
        purpose_group: UsagePurposeGroup | str,
        cost_delta: float,
        token_delta: int,
    ) -> None:
        now = datetime.now(UTC)
        stmt = insert(UsagePeriodTotalDB).values(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            purpose_group=str(purpose_group),
            cost_usd_sum=cost_delta,
            token_sum=token_delta,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                UsagePeriodTotalDB.tenant_id,
                UsagePeriodTotalDB.period_start,
                UsagePeriodTotalDB.period_end,
                UsagePeriodTotalDB.purpose_group,
            ],
            set_={
                "cost_usd_sum": UsagePeriodTotalDB.cost_usd_sum + cost_delta,
                "token_sum": UsagePeriodTotalDB.token_sum + token_delta,
                "updated_at": now,
            },
        )
        await self.db.execute(stmt)

    async def get_period_total(
        self,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
        purpose_group: UsagePurposeGroup | str,
    ) -> tuple[float, int]:
        stmt = select(UsagePeriodTotalDB).where(
            UsagePeriodTotalDB.tenant_id == tenant_id,
            UsagePeriodTotalDB.period_start == period_start,
            UsagePeriodTotalDB.period_end == period_end,
            UsagePeriodTotalDB.purpose_group == str(purpose_group),
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return 0.0, 0
        return float(row.cost_usd_sum), int(row.token_sum)

    async def sum_run_cost_usd(self, agent_run_id: str) -> float:
        stmt = select(func.coalesce(func.sum(UsageEventDB.cost_usd), 0.0)).where(
            UsageEventDB.agent_run_id == agent_run_id,
        )
        result = await self.db.execute(stmt)
        return float(result.scalar_one())

    async def breakdown_by_purpose(
        self,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> list[tuple[str, float, int]]:
        stmt = (
            select(
                UsageEventDB.purpose,
                func.coalesce(func.sum(UsageEventDB.cost_usd), 0.0),
                func.coalesce(
                    func.sum(UsageEventDB.prompt_tokens + UsageEventDB.completion_tokens),
                    0,
                ),
            )
            .where(
                UsageEventDB.tenant_id == tenant_id,
                UsageEventDB.occurred_at >= period_start,
                UsageEventDB.occurred_at < period_end,
                UsageEventDB.funding_source == FundingSource.PLATFORM.value,
            )
            .group_by(UsageEventDB.purpose)
        )
        result = await self.db.execute(stmt)
        return [(row[0], float(row[1]), int(row[2])) for row in result.all()]
