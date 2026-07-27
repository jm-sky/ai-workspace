"""Build tool registry for a user session."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.agent.registry import BUILTIN_AGENTS, get_builtin_agent, get_default_agent_key
from app.modules.agent.tools.base import AgentToolRegistry
from app.modules.agent.tools.github import build_github_mcp_tools
from app.modules.agent.tools.gitlab import GitLabSearchByJiraKeyTool
from app.modules.agent.tools.gmail import build_gmail_mcp_tools
from app.modules.agent.tools.jira import JiraGetIssueTool
from app.modules.agent.tools.memory import MemorySaveTool, MemorySearchTool, MemoryUpdateTool
from app.modules.agent.tools.rag import RagSearchTool
from app.modules.agent.tools.tool_search import ToolSearchTool
from app.modules.agent.tools.wiki import WikiIngestTool, WikiLintTool, WikiQueryTool
from app.modules.integrations.service import IntegrationTokenService
from app.modules.tenants.service import TenantContext

# Backward-compatible map derived from the built-in registry (tests / callers).
AGENT_TOOL_PROFILES: dict[str, list[str]] = {
    key: list(agent.tool_profile) for key, agent in BUILTIN_AGENTS.items()
}

# Always loaded when tool search mode is active (profile tools may be deferred).
CORE_TOOL_NAMES: frozenset[str] = frozenset(
    {"tool_search", "memory_search", "memory_save", "memory_update"}
)


def _resolve_tool_profile(
    agent_key: str,
    tool_profile: Sequence[str] | None,
) -> list[str]:
    if tool_profile is not None:
        return list(tool_profile)
    agent = get_builtin_agent(agent_key)
    if agent is not None:
        return list(agent.tool_profile)
    fallback = get_builtin_agent(get_default_agent_key())
    return list(fallback.tool_profile) if fallback else ["memory"]


def build_tool_registry(
    *,
    tenant_ctx: TenantContext,
    token_service: IntegrationTokenService,
    db: AsyncSession,
    agent_key: str = "github-workspace",
    session_id: str | None = None,
    rag_enabled: bool = False,
    tool_profile: Sequence[str] | None = None,
) -> AgentToolRegistry:
    """Create in-process MCP-compatible tools with per-user token injection.

    When tool search is enabled and the profile catalog exceeds the threshold,
    only core tools (+ ``tool_search``) are exposed initially; the rest are
    deferred until discovered via search.
    """
    profile = _resolve_tool_profile(agent_key, tool_profile)
    tools = []

    if "github" in profile:
        tools.extend(build_github_mcp_tools(tenant_ctx=tenant_ctx, token_service=token_service))
    if "gmail" in profile:
        tools.extend(build_gmail_mcp_tools(tenant_ctx=tenant_ctx, token_service=token_service))
    if "jira" in profile:
        tools.append(JiraGetIssueTool(tenant_ctx=tenant_ctx, token_service=token_service))
    if "gitlab" in profile:
        tools.append(GitLabSearchByJiraKeyTool(tenant_ctx=tenant_ctx, token_service=token_service))
    if "memory" in profile:
        tools.extend(
            [
                MemorySearchTool(
                    tenant_ctx=tenant_ctx,
                    db=db,
                    agent_key=agent_key,
                    session_id=session_id,
                ),
                MemorySaveTool(
                    tenant_ctx=tenant_ctx,
                    db=db,
                    agent_key=agent_key,
                    session_id=session_id,
                ),
                MemoryUpdateTool(
                    tenant_ctx=tenant_ctx,
                    db=db,
                    agent_key=agent_key,
                    session_id=session_id,
                ),
            ]
        )
    if "rag" in profile:
        tools.append(
            RagSearchTool(
                tenant_ctx=tenant_ctx,
                db=db,
                rag_enabled=rag_enabled,
            )
        )
    if "wiki" in profile:
        tools.extend([
            WikiIngestTool(tenant_ctx=tenant_ctx, db=db),
            WikiQueryTool(tenant_ctx=tenant_ctx, db=db),
            WikiLintTool(tenant_ctx=tenant_ctx, db=db),
        ])

    registry = AgentToolRegistry(tools=tools)
    profile_count = len(tools)

    if (
        settings.ai.tool_search_enabled
        and profile_count > settings.ai.tool_search_threshold
    ):
        registry.register(
            ToolSearchTool(
                registry=registry,
                top_k=settings.ai.tool_search_top_k,
            )
        )
        core_present = [name for name in CORE_TOOL_NAMES if name in registry]
        registry.set_active(core_present)

    return registry
