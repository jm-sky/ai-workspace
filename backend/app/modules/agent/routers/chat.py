"""SSE chat endpoint for workspace agent."""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.modules.agent.dependencies import AgentTenantContext
from app.modules.agent.exceptions import (
    AgentError,
    AgentNotConfiguredError,
    AgentToolsDisabledError,
    AgentVisionRequiredError,
)
from app.modules.agent.schemas import AgentChatRequest
from app.modules.agent.services.agent_run_service import AgentRunService
from app.modules.auth.dependencies import CurrentUser
from app.modules.billing.exceptions import FreeTrierRequiresBYOKError
from app.modules.integrations.repositories import (
    IntegrationTokenRepository,
    get_integration_token_repository,
)
from app.modules.integrations.service import IntegrationTokenService
from app.modules.usage.exceptions import UsageLimitExceededError

router = APIRouter(prefix="/chat", tags=["agent-chat"])


def _get_agent_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    token_repo: Annotated[IntegrationTokenRepository, Depends(get_integration_token_repository)],
) -> AgentRunService:
    return AgentRunService(db, IntegrationTokenService(token_repo))


@router.post("/stream")
async def agent_chat_stream(
    request: AgentChatRequest,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[AgentRunService, Depends(_get_agent_service)],
) -> StreamingResponse:
    """Stream agent execution via Server-Sent Events."""
    if not settings.ai.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI features are disabled",
        )

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in service.run_stream(
                tenant_ctx=tenant_ctx,
                message=request.message,
                agent_key=request.agentKey,
                model=request.model,
                session_id=request.sessionId,
                attachment_ids=request.attachmentIds,
            ):
                payload = json.dumps(event.data, default=str)
                yield f"event: {event.event}\ndata: {payload}\n\n"
        except (AgentNotConfiguredError, AgentToolsDisabledError, AgentVisionRequiredError) as exc:
            payload = json.dumps({"message": str(exc)})
            yield f"event: error\ndata: {payload}\n\n"
        except UsageLimitExceededError as exc:
            payload = json.dumps({"message": str(exc), "code": exc.code})
            yield f"event: error\ndata: {payload}\n\n"
        except FreeTrierRequiresBYOKError as exc:
            payload = json.dumps({"message": str(exc), "code": "byok_required"})
            yield f"event: error\ndata: {payload}\n\n"
        except AgentError as exc:
            payload = json.dumps({"message": str(exc)})
            yield f"event: error\ndata: {payload}\n\n"
        except Exception as exc:
            payload = json.dumps({"message": str(exc)})
            yield f"event: error\ndata: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
