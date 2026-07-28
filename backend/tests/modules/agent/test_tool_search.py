"""Tests for tool search (issue 022)."""

from typing import Any
from unittest.mock import patch

import pytest

from app.modules.agent.tools.base import AgentTool, AgentToolDefinition, AgentToolRegistry
from app.modules.agent.tools.tool_search import ToolSearchTool, search_tools

_MOCK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "github_search_repositories",
            "description": "Search GitHub repositories accessible to the user.",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search_issues",
            "description": "Search GitHub issues and pull requests.",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search_code",
            "description": "Search code across GitHub repositories.",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_get_user",
            "description": "Get a GitHub user profile by login.",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search stored memories semantically.",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_save",
            "description": "Save a fact or preference into memory.",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jira_get_issue",
            "description": "Get a Jira issue by key.",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_search_by_jira_key",
            "description": "Find GitLab MRs and issues linked to a Jira key.",
        },
    },
]


class _StubTool(AgentTool):
    def __init__(self, name: str, description: str):
        self._definition = AgentToolDefinition(
            name=name,
            description=description,
            parameters={"type": "object", "properties": {}},
        )

    @property
    def definition(self) -> AgentToolDefinition:
        return self._definition

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "name": self._definition.name}


def test_search_tools_github_repositories_recall():
    result = search_tools(_MOCK_TOOLS, "search github repositories", top_k=2)
    names = [t["function"]["name"] for t in result]
    assert "github_search_repositories" in names, names


def test_search_tools_memory_recall():
    result = search_tools(_MOCK_TOOLS, "search stored memories", top_k=2)
    names = [t["function"]["name"] for t in result]
    assert "memory_search" in names, names


def test_search_tools_code_recall():
    result = search_tools(_MOCK_TOOLS, "search code across repositories", top_k=2)
    names = [t["function"]["name"] for t in result]
    assert "github_search_code" in names, names


def test_search_tools_empty_query_returns_first_k():
    result = search_tools(_MOCK_TOOLS, "", top_k=3)
    assert len(result) == 3


def test_search_tools_top_k_limit():
    result = search_tools(_MOCK_TOOLS, "github search", top_k=3)
    assert len(result) <= 3


def test_registry_pass_all_when_no_active_subset():
    registry = AgentToolRegistry(
        tools=[
            _StubTool("memory_search", "Search memories"),
            _StubTool("github_search_repositories", "Search repos"),
        ]
    )
    assert len(registry.openai_tools()) == 2
    assert registry.deferred_openai_tools() == []
    assert not registry.has_deferred()


def test_registry_deferred_and_activate():
    tools = [
        _StubTool("memory_search", "Search stored memories semantically."),
        _StubTool("memory_save", "Save a fact into memory."),
        _StubTool(
            "github_search_repositories",
            "Search GitHub repositories accessible to the user.",
        ),
        _StubTool("github_search_code", "Search code across GitHub repositories."),
    ]
    registry = AgentToolRegistry(tools=tools)
    registry.register(ToolSearchTool(registry=registry, top_k=2))
    registry.set_active(["tool_search", "memory_search", "memory_save"])

    active_names = {t["function"]["name"] for t in registry.openai_tools()}
    assert active_names == {"tool_search", "memory_search", "memory_save"}
    assert registry.has_deferred()
    deferred_names = {t["function"]["name"] for t in registry.deferred_openai_tools()}
    assert deferred_names == {"github_search_repositories", "github_search_code"}


@pytest.mark.asyncio
async def test_tool_search_activates_deferred_tools():
    tools = [
        _StubTool("memory_search", "Search stored memories semantically."),
        _StubTool("memory_save", "Save a fact into memory."),
        _StubTool(
            "github_search_repositories",
            "Search GitHub repositories accessible to the user.",
        ),
        _StubTool("github_search_code", "Search code across GitHub repositories."),
        _StubTool("jira_get_issue", "Get a Jira issue by key."),
    ]
    registry = AgentToolRegistry(tools=tools)
    search_tool = ToolSearchTool(registry=registry, top_k=2)
    registry.register(search_tool)
    registry.set_active(["tool_search", "memory_search", "memory_save"])

    result = await search_tool.execute({"query": "search github repositories"})

    assert "github_search_repositories" in result["activated"]
    active_names = {t["function"]["name"] for t in registry.openai_tools()}
    assert "github_search_repositories" in active_names
    assert "tool_search" in active_names


@pytest.mark.asyncio
async def test_tool_search_empty_deferred():
    registry = AgentToolRegistry(
        tools=[_StubTool("memory_search", "Search memories")]
    )
    search_tool = ToolSearchTool(registry=registry, top_k=2)
    registry.register(search_tool)
    # All tools active → nothing deferred
    result = await search_tool.execute({"query": "anything"})
    assert result["activated"] == []
    assert "No deferred" in result.get("message", "")


def test_build_tool_registry_below_threshold_no_search():
    from app.modules.agent.tools import build_tool_registry

    fake_ctx = object()
    fake_token = object()
    fake_db = object()

    with (
        patch("app.modules.agent.tools.build_github_mcp_tools", return_value=[]),
        patch(
            "app.modules.agent.tools.MemorySearchTool",
            side_effect=lambda **kw: _StubTool(
                "memory_search", "Search stored memories"
            ),
        ),
        patch(
            "app.modules.agent.tools.MemorySaveTool",
            side_effect=lambda **kw: _StubTool("memory_save", "Save memory"),
        ),
        patch(
            "app.modules.agent.tools.MemoryUpdateTool",
            side_effect=lambda **kw: _StubTool("memory_update", "Update memory"),
        ),
        patch(
            "app.modules.agent.tools.RagSearchTool",
            side_effect=lambda **kw: _StubTool("rag_search", "Search documents"),
        ),
        patch("app.modules.agent.tools.settings") as mock_settings,
    ):
        mock_settings.ai.tool_search_enabled = True
        mock_settings.ai.tool_search_threshold = 15
        mock_settings.ai.tool_search_top_k = 5

        # Memory + rag tools → still below threshold
        registry = build_tool_registry(
            tenant_ctx=fake_ctx,  # type: ignore[arg-type]
            token_service=fake_token,  # type: ignore[arg-type]
            db=fake_db,  # type: ignore[arg-type]
            agent_key="github-workspace",
            rag_enabled=True,
        )

    names = {t["function"]["name"] for t in registry.openai_tools()}
    assert "tool_search" not in names
    assert "memory_search" in names
    assert "memory_update" in names
    assert "rag_search" in names
    assert not registry.has_deferred()


def test_build_tool_registry_above_threshold_defers():
    from app.modules.agent.tools import build_tool_registry

    github_stubs = [
        _StubTool(f"github_tool_{i}", f"GitHub tool number {i} for testing")
        for i in range(10)
    ]

    with (
        patch(
            "app.modules.agent.tools.build_github_mcp_tools",
            return_value=github_stubs,
        ),
        patch(
            "app.modules.agent.tools.MemorySearchTool",
            side_effect=lambda **kw: _StubTool(
                "memory_search", "Search stored memories"
            ),
        ),
        patch(
            "app.modules.agent.tools.MemorySaveTool",
            side_effect=lambda **kw: _StubTool("memory_save", "Save memory"),
        ),
        patch(
            "app.modules.agent.tools.MemoryUpdateTool",
            side_effect=lambda **kw: _StubTool("memory_update", "Update memory"),
        ),
        patch(
            "app.modules.agent.tools.RagSearchTool",
            side_effect=lambda **kw: _StubTool("rag_search", "Search documents"),
        ),
        patch("app.modules.agent.tools.settings") as mock_settings,
    ):
        mock_settings.ai.tool_search_enabled = True
        mock_settings.ai.tool_search_threshold = 5
        mock_settings.ai.tool_search_top_k = 3

        registry = build_tool_registry(
            tenant_ctx=object(),  # type: ignore[arg-type]
            token_service=object(),  # type: ignore[arg-type]
            db=object(),  # type: ignore[arg-type]
            agent_key="github-workspace",
            rag_enabled=True,
        )

    active = {t["function"]["name"] for t in registry.openai_tools()}
    assert active == {
        "tool_search",
        "memory_search",
        "memory_save",
        "memory_update",
    }
    assert "rag_search" not in active
    assert registry.has_deferred()
    # 10 github + 3 gmail + 3 memory + 1 rag + 3 wiki + tool_search.
    # Web tools are absent: this test's patched settings leave web_search_mode
    # unset, so the bucket only registers tools in local mode.
    assert len(registry.all_openai_tools()) == 21
