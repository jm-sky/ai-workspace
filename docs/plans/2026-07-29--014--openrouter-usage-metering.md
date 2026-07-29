# Plan 014 — OpenRouter usage metering and limits

**Status:** done (2026-07-29)
**Obszar:** backend `usage`, `billing/entitlements`, agent loop, embeddings, billing/limits API, frontend billing card

## Cel

Jedno źródło prawdy o zużyciu OpenRouter (chat, embeddings, web search server) oraz `EffectiveQuota` (plan ∩ kaskada workspace), przygotowane pod Stripe Pro (plan [015](2026-07-29--015--stripe-pro-workspace.md)).

## Zrealizowane

- Tabele `usage_events`, `usage_period_totals` (migracja 067)
- Moduł `backend/app/modules/usage/` — recorder, guard, quota resolver, `/usage/summary`
- `PlanEntitlements` w `billing/entitlements.py` (współdzielony katalog planów)
- OpenRouter client z `HTTP-Referer` / `X-OpenRouter-Title`
- Agent loop + embeddings + RAG ingest — zapis usage; guard przed runem i embedem
- Rozszerzenie `GET /billing/limits` o bieżące zużycie workspace
- UI: `WorkspaceUsageCard` na stronie billing

## Konfiguracja

| ENV | Opis |
|-----|------|
| `OPENROUTER_APP_URL` | Atrybucja OpenRouter (Referer) |
| `OPENROUTER_APP_TITLE` | Tytuł aplikacji w OpenRouter |

Kaskada workspace (opcjonalnie): `monthly_cost_cap_usd`, `monthly_web_search_cap`.

## Interim billing

`plan_tier` z subskrypcji **ownera tenanta**; okres ze Stripe `current_period_*` lub miesiąc kalendarzowy UTC.
