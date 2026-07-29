"""Types for workspace cascade configuration."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ConfigScope(StrEnum):
    APP = "app"
    TENANT = "tenant"
    TEAM = "team"
    USER = "user"


class ConfigKey(StrEnum):
    ALLOWED_MODELS = "allowed_models"
    DEFAULT_MODEL = "default_model"
    MAX_TOKENS = "max_tokens"
    RAG_ENABLED = "rag_enabled"
    TOOLS_ENABLED = "tools_enabled"
    WEB_SEARCH_ENABLED = "web_search_enabled"
    MONTHLY_COST_CAP_USD = "monthly_cost_cap_usd"
    MONTHLY_WEB_SEARCH_CAP = "monthly_web_search_cap"


class EffectiveWorkspaceConfig(BaseModel):
    """Resolved configuration after applying cascade rules."""

    # An empty list means "unrestricted" (the whole model catalog), not "no
    # models". Every consumer must treat it that way.
    allowedModels: list[str] = Field(default_factory=list)
    defaultModel: str | None = None
    maxTokens: int | None = None
    ragEnabled: bool = False
    toolsEnabled: bool = True
    webSearchEnabled: bool = True
    monthlyCostCapUsd: float | None = None
    monthlyWebSearchCap: int | None = None


class ConfigEntryRequest(BaseModel):
    key: ConfigKey
    value: dict | list | str | int | bool


class ConfigEntryResponse(BaseModel):
    scope: ConfigScope
    scopeId: str | None = None
    tenantId: str | None = None
    key: ConfigKey
    value: dict | list | str | int | bool
