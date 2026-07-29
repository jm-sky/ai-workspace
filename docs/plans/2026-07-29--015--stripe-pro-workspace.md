# Plan 015 — Stripe Pro workspace (faza 2)

**Status:** planned
**Data:** 2026-07-29
**Zależność:** [014 OpenRouter usage](2026-07-29--014--openrouter-usage-metering.md)

## Cel

Subskrypcja i rozliczenie na poziomie **tenanta** (Stripe Customer per workspace), spójne z ledgerem `usage_events` / `usage_period_totals`.

## Zakres (do implementacji)

1. `subscriptions.tenant_id` (UNIQUE) + `billing_contact_user_id`; migracja z per-user.
2. Stripe Products/Prices → `PlanEntitlements` (jeden katalog, bez duplikatu w `BillingService`).
3. Webhooki: sync `plan_tier`, `current_period_start/end` → ten sam okres co `UsageGuard`.
4. Checkout / portal w kontekście aktywnego tenanta.
5. Opcjonalnie: metered overage z `usage_period_totals` → Stripe Usage Records.
6. UI Pro: feature flags z entitlements (web, RAG, advanced).

## Poza zakresem

- Gear `itemsLimit` / `containersLimit` (legacy) — osobna decyzja produktowa.
