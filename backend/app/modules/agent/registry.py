"""Built-in agent definitions (code registry — Chunk A; seed source for DB in Chunk B)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.agent.prompts.general import GENERAL_SYSTEM_PROMPT
from app.modules.agent.prompts.github_workspace import GITHUB_WORKSPACE_SYSTEM_PROMPT
from app.modules.agent.prompts.jira_360 import JIRA_360_SYSTEM_PROMPT


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Configurable agent object (MVP dec. #10–11 fields used at runtime)."""

    key: str
    name: str
    description: str
    system_prompt: str
    tool_profile: tuple[str, ...]
    memory_scopes: tuple[str, ...] = ("session", "user", "agent")
    rag_enabled: bool = False
    model: str | None = None
    effort: str | None = None
    routing_hints: dict[str, Any] = field(default_factory=dict)
    is_default: bool = False
    is_enabled: bool = True


BUILTIN_AGENTS: dict[str, AgentDefinition] = {
    "github-workspace": AgentDefinition(
        key="github-workspace",
        name="GitHub Workspace",
        description=(
            "Explore GitHub repositories, issues, and PRs; read Gmail when connected; "
            "search the web; use memory and RAG."
        ),
        system_prompt=GITHUB_WORKSPACE_SYSTEM_PROMPT,
        tool_profile=("github", "gmail", "memory", "rag", "wiki", "web"),
        rag_enabled=True,
        is_default=True,
        routing_hints={
            "triggers": ["github", "repo", "pull request", "issue", "gmail", "email"],
        },
    ),
    "general": AgentDefinition(
        key="general",
        name="General",
        description="Open conversation with memory, web search and optional RAG — no GitHub/Gmail tools.",
        system_prompt=GENERAL_SYSTEM_PROMPT,
        tool_profile=("memory", "rag", "wiki", "web"),
        rag_enabled=True,
        routing_hints={
            "triggers": ["chat", "help", "remember", "general"],
        },
    ),
    "jira-360": AgentDefinition(
        key="jira-360",
        name="Jira 360°",
        description="Legacy 360° view around a Jira issue (requires Jira + GitLab). Requires access.",
        system_prompt=JIRA_360_SYSTEM_PROMPT,
        tool_profile=("jira", "gitlab", "memory", "rag"),
        rag_enabled=True,
        routing_hints={
            "triggers": ["jira", "360", "issue key"],
        },
    ),
}


def get_builtin_agent(key: str) -> AgentDefinition | None:
    return BUILTIN_AGENTS.get(key)


def list_builtin_agents(*, enabled_only: bool = True) -> list[AgentDefinition]:
    agents = list(BUILTIN_AGENTS.values())
    if enabled_only:
        agents = [a for a in agents if a.is_enabled]
    return agents


def get_default_agent_key() -> str:
    for agent in BUILTIN_AGENTS.values():
        if agent.is_default and agent.is_enabled:
            return agent.key
    return "github-workspace"


def require_builtin_agent(key: str) -> AgentDefinition:
    agent = get_builtin_agent(key)
    if agent is None or not agent.is_enabled:
        from app.modules.agent.exceptions import AgentNotConfiguredError

        raise AgentNotConfiguredError(f"Unknown agent: {key}")
    return agent
