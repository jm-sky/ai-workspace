"""Record OpenRouter usage into the ledger."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.utils.models_config import calculate_cost
from app.modules.usage.billing_period import resolve_billing_period
from app.modules.usage.repository import UsageRepository
from app.modules.usage.types import FundingSource, UsagePurpose, UsagePurposeGroup


def extract_cost_from_usage(
    usage: Any,
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> tuple[float | None, float]:
    """Return (api_cost_or_none, billed_cost_usd)."""
    api_cost: float | None = None
    if usage is not None:
        dumped = usage.model_dump() if hasattr(usage, "model_dump") else {}
        raw = dumped.get("cost")
        if raw is not None:
            api_cost = float(raw)
    estimated = calculate_cost(model, prompt_tokens, completion_tokens)
    billed = api_cost if api_cost is not None else estimated
    return api_cost, billed


def generation_id_from_response(response: Any) -> str | None:
    if response is None:
        return None
    gid = getattr(response, "id", None)
    return str(gid) if gid else None


@dataclass(frozen=True)
class UsageRecordContext:
    tenant_id: str
    user_id: str
    funding_source: FundingSource
    agent_run_id: str | None = None


class UsageRecorder:
    """Writes usage events and updates period aggregates."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UsageRepository(db)

    async def record_chat_completion(
        self,
        ctx: UsageRecordContext,
        *,
        purpose: UsagePurpose,
        model: str,
        usage: Any,
        response: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> float:
        prompt_tokens = 0
        completion_tokens = 0
        if usage is not None:
            prompt_tokens = usage.prompt_tokens or 0
            completion_tokens = usage.completion_tokens or 0
        api_cost, billed = extract_cost_from_usage(
            usage,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        estimated = calculate_cost(model, prompt_tokens, completion_tokens)
        period = await resolve_billing_period(self.db, tenant_id=ctx.tenant_id)
        await self.repo.insert_event(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            purpose=purpose,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=billed if ctx.funding_source == FundingSource.PLATFORM else None,
            cost_estimated_usd=estimated,
            openrouter_generation_id=generation_id_from_response(response),
            agent_run_id=ctx.agent_run_id,
            funding_source=ctx.funding_source,
            metadata=metadata,
        )
        if ctx.funding_source == FundingSource.PLATFORM:
            await self.repo.bump_period_total(
                tenant_id=ctx.tenant_id,
                period_start=period.start,
                period_end=period.end,
                purpose_group=UsagePurposeGroup.PLATFORM,
                cost_delta=billed,
                token_delta=prompt_tokens + completion_tokens,
            )
        return billed

    async def record_embedding_batch(
        self,
        ctx: UsageRecordContext,
        *,
        model: str,
        texts: list[str],
        total_prompt_tokens: int = 0,
    ) -> float:
        """Record embedding usage (token count optional; cost estimated from chars)."""
        estimated_chars = sum(len(t) for t in texts)
        prompt_tokens = total_prompt_tokens or max(1, estimated_chars // 4)
        _, billed = extract_cost_from_usage(
            None,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=0,
        )
        period = await resolve_billing_period(self.db, tenant_id=ctx.tenant_id)
        await self.repo.insert_event(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            purpose=UsagePurpose.EMBEDDING,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=0,
            cost_usd=billed if ctx.funding_source == FundingSource.PLATFORM else None,
            cost_estimated_usd=billed,
            openrouter_generation_id=None,
            agent_run_id=ctx.agent_run_id,
            funding_source=ctx.funding_source,
            metadata={"batch_size": len(texts)},
        )
        if ctx.funding_source == FundingSource.PLATFORM:
            await self.repo.bump_period_total(
                tenant_id=ctx.tenant_id,
                period_start=period.start,
                period_end=period.end,
                purpose_group=UsagePurposeGroup.PLATFORM,
                cost_delta=billed,
                token_delta=prompt_tokens,
            )
        return billed

    async def record_web_search_op(
        self,
        ctx: UsageRecordContext,
        *,
        count: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if count <= 0:
            return
        period = await resolve_billing_period(self.db, tenant_id=ctx.tenant_id)
        await self.repo.insert_event(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            purpose=UsagePurpose.AGENT_CHAT,
            model=None,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=None,
            cost_estimated_usd=None,
            openrouter_generation_id=None,
            agent_run_id=ctx.agent_run_id,
            funding_source=ctx.funding_source,
            metadata={**(metadata or {}), "web_search_op": True, "count": count},
        )
        if ctx.funding_source == FundingSource.PLATFORM:
            await self.repo.bump_period_total(
                tenant_id=ctx.tenant_id,
                period_start=period.start,
                period_end=period.end,
                purpose_group=UsagePurposeGroup.WEB_SEARCH,
                cost_delta=0.0,
                token_delta=count,
            )
