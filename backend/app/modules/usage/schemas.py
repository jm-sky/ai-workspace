"""Usage API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class UsagePurposeBreakdown(BaseModel):
    purpose: str
    costUsd: float
    tokens: int


class UsageSummaryResponse(BaseModel):
    periodStart: datetime
    periodEnd: datetime
    planTier: str
    monthlyIncludedUsd: float
    usedUsd: float
    webSearchUsed: int
    webSearchCap: int | None = None
    breakdown: list[UsagePurposeBreakdown] = Field(default_factory=list)
