"""Factory for tenant-scoped embedding clients with usage metering."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.embeddings import EmbeddingService
from app.core.config import settings
from app.modules.usage.billing_period import resolve_funding
from app.modules.usage.guard import UsageGuard
from app.modules.usage.recorder import UsageRecorder, UsageRecordContext
from app.modules.tenants.service import TenantContext


async def create_embedding_service(
    db: AsyncSession,
    *,
    tenant_ctx: TenantContext,
    enforce_quota: bool = True,
) -> EmbeddingService:
    """Build an :class:`EmbeddingService` that records usage for the tenant."""
    if enforce_quota:
        await UsageGuard(db).assert_embedding_allowed(tenant_ctx)

    funding = await resolve_funding(
        db,
        tenant_id=tenant_ctx.tenant_id,
        user_id=tenant_ctx.user_id,
        platform_api_key=settings.ai.openrouter_api_key,
    )
    api_key = funding.api_key or settings.ai.openrouter_api_key
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured")

    usage_ctx = UsageRecordContext(
        tenant_id=tenant_ctx.tenant_id,
        user_id=tenant_ctx.user_id,
        funding_source=funding.source,
    )
    return EmbeddingService(
        api_key=api_key,
        usage_recorder=UsageRecorder(db),
        usage_ctx=usage_ctx,
    )
