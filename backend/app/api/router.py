"""Main API router aggregating all module routers."""

from fastapi import APIRouter, Depends

from app.core.health_details import build_health_details, verify_health_details_token
from app.modules.admin.router import router as admin_router
from app.modules.agent.router import router as agent_router
from app.modules.ai.routers.models import router as ai_models_router
from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.feature_limits.router import router as feature_limits_router
from app.modules.integrations.router import router as integrations_router
from app.modules.logs.router import router as logs_router
from app.modules.memory.router import router as memory_router
from app.modules.rag.router import router as rag_router
from app.modules.settings.router import router as settings_router
from app.modules.teams.router import router as teams_router
from app.modules.tenants.router import router as tenants_router
from app.modules.usage.router import router as usage_router
from app.modules.users.router import router as users_router
from app.modules.wiki.router import router as wiki_router
from app.modules.workspace_config.router import router as workspace_config_router

api_router = APIRouter()


@api_router.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


# Detailed health endpoint for Ops Monitor (bearer-token protected)
@api_router.get(
    "/health/details",
    tags=["Health"],
    dependencies=[Depends(verify_health_details_token)],
)
async def health_check_details() -> dict:
    """
    Detailed health check for Ops Monitor.

    Reports per-component status (database, cache, storage, frontend) per the
    ops-monitor health schema contract. Requires ``Authorization: Bearer
    <HEALTH_DETAILS_TOKEN>``.

    Returns:
        Health details response (schema_version, status, components, ...)
    """
    return await build_health_details()


api_router.include_router(admin_router)
api_router.include_router(agent_router)
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(billing_router)
api_router.include_router(feature_limits_router)
api_router.include_router(logs_router, prefix="/logs", tags=["Logs", "Monitoring"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(settings_router, prefix="/me/settings", tags=["Settings"])
api_router.include_router(tenants_router)
api_router.include_router(teams_router)
api_router.include_router(workspace_config_router)
api_router.include_router(ai_models_router, prefix="/ai", tags=["AI Models"])
api_router.include_router(integrations_router)
api_router.include_router(memory_router)
api_router.include_router(rag_router)
api_router.include_router(wiki_router)
api_router.include_router(usage_router)

try:
    from app.modules.two_factor.router import router as two_factor_router

    api_router.include_router(
        two_factor_router,
        prefix="/two-factor",
        tags=["Two-Factor Authentication", "Security", "WebAuthn", "TOTP"],
    )
except ImportError:
    pass
