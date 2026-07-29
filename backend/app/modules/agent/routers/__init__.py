"""Agent API routers."""

from app.modules.agent.routers.agents import router as agents_router
from app.modules.agent.routers.attachments import router as attachments_router
from app.modules.agent.routers.chat import router as chat_router
from app.modules.agent.routers.runs import router as runs_router
from app.modules.agent.routers.sessions import router as sessions_router

__all__ = [
    "agents_router",
    "attachments_router",
    "chat_router",
    "runs_router",
    "sessions_router",
]
