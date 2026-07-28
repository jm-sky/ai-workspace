"""Pydantic schemas for agent API."""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class AgentChatRequest(BaseModel):
    """User message to the workspace agent."""

    message: str = Field(default="", max_length=8000)
    agentKey: str | None = Field(default=None, alias="agent_key")
    model: str | None = None
    sessionId: str | None = Field(default=None, alias="session_id")
    attachmentIds: list[str] = Field(default_factory=list, alias="attachment_ids", max_length=20)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def require_message_or_attachments(self) -> Self:
        if not self.message.strip() and not self.attachmentIds:
            raise ValueError("message or attachmentIds is required")
        return self


class AgentSummary(BaseModel):
    """Public agent meta for the chat picker (no system prompt)."""

    key: str
    name: str
    description: str
    isDefault: bool = False
    toolProfile: list[str] = Field(default_factory=list)


class AgentListResponse(BaseModel):
    """Available agents for the active tenant."""

    agents: list[AgentSummary]


class AgentDetail(BaseModel):
    """Full agent definition for tenant admin editor."""

    id: str
    key: str
    name: str
    description: str
    systemPrompt: str
    model: str | None = None
    effort: str | None = None
    toolProfile: list[str] = Field(default_factory=list)
    memoryScopes: list[str] = Field(default_factory=list)
    ragEnabled: bool = False
    routingHints: dict[str, Any] = Field(default_factory=dict)
    isEnabled: bool = True
    isDefault: bool = False
    createdAt: datetime
    updatedAt: datetime


class AgentCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    systemPrompt: str = Field(min_length=1, alias="system_prompt")
    model: str | None = None
    effort: str | None = None
    toolProfile: list[str] = Field(default_factory=list, alias="tool_profile")
    memoryScopes: list[str] = Field(
        default_factory=lambda: ["session", "user", "agent"],
        alias="memory_scopes",
    )
    ragEnabled: bool = Field(default=False, alias="rag_enabled")
    routingHints: dict[str, Any] = Field(default_factory=dict, alias="routing_hints")
    isEnabled: bool = Field(default=True, alias="is_enabled")
    isDefault: bool = Field(default=False, alias="is_default")

    model_config = {"populate_by_name": True}


class AgentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    systemPrompt: str | None = Field(default=None, min_length=1, alias="system_prompt")
    model: str | None = None
    effort: str | None = None
    toolProfile: list[str] | None = Field(default=None, alias="tool_profile")
    memoryScopes: list[str] | None = Field(default=None, alias="memory_scopes")
    ragEnabled: bool | None = Field(default=None, alias="rag_enabled")
    routingHints: dict[str, Any] | None = Field(default=None, alias="routing_hints")
    isEnabled: bool | None = Field(default=None, alias="is_enabled")
    isDefault: bool | None = Field(default=None, alias="is_default")

    model_config = {"populate_by_name": True}


class AgentAdminListResponse(BaseModel):
    agents: list[AgentDetail]


class RichBlock(BaseModel):
    """Rich UI block rendered alongside Markdown."""

    type: Literal["card", "table", "markdown", "chart", "sources"]
    title: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ChartPoint(BaseModel):
    """Single (x, y) sample within a chart series."""

    x: str | float | int
    y: float | int


class ChartSeries(BaseModel):
    """Named series of points within a chart block."""

    name: str
    points: list[ChartPoint]


class ChartBlockData(BaseModel):
    """Payload validated from a tool's `chart` convention (plan 008 dec. C2/C3)."""

    chartType: Literal["line", "bar"]
    xLabel: str | None = None
    yLabel: str | None = None
    series: list[ChartSeries]


class SourceItem(BaseModel):
    """One cited web source, numbered as the model saw it."""

    index: int
    url: str
    title: str | None = None
    snippet: str | None = None
    publishedAt: str | None = None


class SourcesBlockData(BaseModel):
    """Payload validated from a tool's `sources` convention (plan 013 dec. #5)."""

    items: list[SourceItem]


class AgentRunStepResponse(BaseModel):
    """Single trace step."""

    id: str
    stepIndex: int
    stepType: str
    name: str | None = None
    inputData: dict[str, Any] | None = None
    outputData: dict[str, Any] | None = None
    createdAt: datetime


class AgentRunResponse(BaseModel):
    """Completed or in-progress agent run."""

    id: str
    sessionId: str | None = None
    agentKey: str
    status: str
    inputMessage: str
    outputMessage: str | None = None
    systemPrompt: str
    model: str
    promptTokens: int
    completionTokens: int
    totalTokens: int
    costUsd: float | None = None
    blocks: list[RichBlock] = Field(default_factory=list)
    steps: list[AgentRunStepResponse] = Field(default_factory=list)
    createdAt: datetime
    completedAt: datetime | None = None


class AgentRunsListResponse(BaseModel):
    """Paginated list of runs."""

    runs: list[AgentRunResponse]
    total: int


class AgentSessionSummary(BaseModel):
    """A multi-turn chat session (conversation)."""

    id: str
    agentKey: str
    title: str | None = None
    createdAt: datetime
    lastMessageAt: datetime


class AgentSessionsListResponse(BaseModel):
    """Paginated list of chat sessions."""

    sessions: list[AgentSessionSummary]
    total: int


class AgentSessionDetail(AgentSessionSummary):
    """A chat session with its ordered runs (turns)."""

    runs: list[AgentRunResponse] = Field(default_factory=list)
