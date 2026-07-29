"""Usage summary and metering API."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.agent.dependencies import AgentTenantContext
from app.modules.usage.schemas import UsagePurposeBreakdown, UsageSummaryResponse
from app.modules.usage.service import UsageSummaryService

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Workspace OpenRouter usage summary",
)
async def get_usage_summary(
    tenant_ctx: AgentTenantContext,
    db: AsyncSession = Depends(get_db),
) -> UsageSummaryResponse:
    service = UsageSummaryService(db)
    summary = await service.get_summary(tenant_ctx)
    return UsageSummaryResponse(
        periodStart=summary.period_start,
        periodEnd=summary.period_end,
        planTier=summary.plan_tier,
        monthlyIncludedUsd=summary.monthly_included_usd,
        usedUsd=summary.used_usd,
        webSearchUsed=summary.web_search_used,
        webSearchCap=summary.web_search_cap,
        breakdown=[
            UsagePurposeBreakdown(purpose=p.purpose, costUsd=p.cost_usd, tokens=p.tokens)
            for p in summary.breakdown
        ],
    )
