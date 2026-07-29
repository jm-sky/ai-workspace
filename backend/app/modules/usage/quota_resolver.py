"""Effective quotas from plan entitlements and workspace cascade."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.usage.billing_period import BillingPeriod, resolve_billing_period
from app.modules.workspace_config.repositories import WorkspaceConfigRepository
from app.modules.workspace_config.resolver import WorkspaceConfigResolver
from app.modules.workspace_config.types import ConfigKey, ConfigScope


@dataclass(frozen=True)
class EffectiveQuota:
    period: BillingPeriod
    monthly_included_usd: float
    monthly_web_search_cap: int | None
    funding_requires_byok: bool


def _min_optional_float(base: float, cap: float | None) -> float:
    if cap is None:
        return base
    return min(base, cap)


def _min_optional_int(base: int | None, cap: int | None) -> int | None:
    if base is None:
        return cap
    if cap is None:
        return base
    return min(base, cap)


class EffectiveQuotaResolver:
    """Merge subscription entitlements with workspace governance caps."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.config_resolver = WorkspaceConfigResolver(WorkspaceConfigRepository(db))

    async def resolve(
        self,
        *,
        tenant_id: str,
        user_id: str,
        team_id: str | None = None,
    ) -> EffectiveQuota:
        period = await resolve_billing_period(self.db, tenant_id=tenant_id)
        ent = period.entitlements
        await self.config_resolver.resolve(
            user_id=user_id,
            tenant_id=tenant_id,
            team_id=team_id,
        )

        cascade_cost_cap = await self._read_float_cascade(
            tenant_id=tenant_id,
            user_id=user_id,
            team_id=team_id,
            key=ConfigKey.MONTHLY_COST_CAP_USD,
        )
        cascade_web_cap = await self._read_int_cascade(
            tenant_id=tenant_id,
            user_id=user_id,
            team_id=team_id,
            key=ConfigKey.MONTHLY_WEB_SEARCH_CAP,
        )

        monthly_usd = _min_optional_float(ent.monthly_included_usd, cascade_cost_cap)
        web_cap = _min_optional_int(ent.web_search_monthly_cap, cascade_web_cap)

        return EffectiveQuota(
            period=period,
            monthly_included_usd=monthly_usd,
            monthly_web_search_cap=web_cap,
            funding_requires_byok=ent.requires_byok,
        )

    async def _read_float_cascade(
        self,
        *,
        tenant_id: str,
        user_id: str,
        team_id: str | None,
        key: ConfigKey,
    ) -> float | None:
        repo = WorkspaceConfigRepository(self.db)
        values: list[float] = []
        scopes: list[tuple[ConfigScope, str | None, str | None]] = [
            (ConfigScope.TENANT, tenant_id, None),
            (ConfigScope.TEAM, team_id, None),
            (ConfigScope.USER, user_id, tenant_id),
        ]
        for scope, scope_id, tid in scopes:
            if scope_id is None and scope != ConfigScope.TENANT:
                continue
            entries = await repo.get_entries_for_scope(
                scope=scope,
                scope_id=scope_id,
                tenant_id=tid,
            )
            for entry in entries:
                if entry.config_key == key.value and isinstance(entry.config_value, (int, float)):
                    values.append(float(entry.config_value))
        if not values:
            return None
        return min(values)

    async def _read_int_cascade(
        self,
        *,
        tenant_id: str,
        user_id: str,
        team_id: str | None,
        key: ConfigKey,
    ) -> int | None:
        repo = WorkspaceConfigRepository(self.db)
        values: list[int] = []
        scopes: list[tuple[ConfigScope, str | None, str | None]] = [
            (ConfigScope.TENANT, tenant_id, None),
            (ConfigScope.TEAM, team_id, None),
            (ConfigScope.USER, user_id, tenant_id),
        ]
        for scope, scope_id, tid in scopes:
            if scope_id is None and scope != ConfigScope.TENANT:
                continue
            entries = await repo.get_entries_for_scope(
                scope=scope,
                scope_id=scope_id,
                tenant_id=tid,
            )
            for entry in entries:
                if entry.config_key == key.value and isinstance(entry.config_value, int):
                    values.append(entry.config_value)
        if not values:
            return None
        return min(values)
