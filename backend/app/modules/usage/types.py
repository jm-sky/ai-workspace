"""Usage metering types."""

from enum import StrEnum


class UsagePurpose(StrEnum):
    AGENT_CHAT = "agent_chat"
    EMBEDDING = "embedding"
    LEGACY_CHAT = "legacy_chat"
    CATALOG = "catalog"
    EVAL = "eval"


class UsagePurposeGroup(StrEnum):
    """Aggregates for fast quota checks."""

    PLATFORM = "platform"
    WEB_SEARCH = "web_search"


class FundingSource(StrEnum):
    PLATFORM = "platform"
    BYOK = "byok"
