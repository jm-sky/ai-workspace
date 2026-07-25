# Plan 008 — Faza 3: Konfigurowalność (edytor agentów + routing + bloki)

**Status:** `done`  
**Data:** 2026-07-23  
**Obszar:** backend (`agent`, `tenants`) + frontend (`workspace`, `settings`)  
**Referencje:** MVP dec. #9–11, #14; issue [#023](../issues/2026-07-20--023--agent-routing.md); research [#006](../research/2026-07-08--006--ai-kancelaria-comparison.md) (skille), [#007](../research/2026-07-10--007--chatgpt-settings-reference.md) (custom instructions)

## Postęp implementacji (2026-07-23)

| Chunk | Status | Uwagi |
|-------|--------|--------|
| **A** | ✅ | Rejestr, `ExplicitAgentRouter`, picker, `GET /agent/agents`, `routingReason` w metadata |
| **B** | ✅ | Tabela `agents`, seed, CRUD tenant owner/admin, `/settings/agents`, runtime z DB |
| **C** | ✅ | Chart blocks — `RichBlock.type="chart"`, konwencja `{"chart": {...}}` w wyniku toola, `AgentChartBlock.vue` (Unovis/`ui/chart`) |

Rozstrzygnięte: B7 tenant-admin; seed per tenant; trzeci agent `general`.

## Cel

Zamienić hardcodowane `AGENT_PROMPTS` / `AGENT_TOOL_PROFILES` na **konfigurowalne obiekty Agent** (dec. #10–11), z **jawnym wyborem** w czacie (dec. #9) i domknięciem **bogatych bloków** o wykresy (dec. #14).

Efekt dogfoodingu: **tenant owner/admin** definiuje / edytuje agenta w swoim tenancie → członek wybiera go w czacie → run używa promptu, modelu, tool profile i zakresów pamięci z definicji.

## Stan obecny (reuse)

| Element | Gdzie | Uwaga |
|---------|-------|--------|
| Prompt per key | `agent_run_service.AGENT_PROMPTS` | `github-workspace`, `jira-360` |
| Tool profile | `tools/__init__.py` `AGENT_TOOL_PROFILES` | bucket'y: github/gmail/jira/… |
| Tool search | `#022` done | deferral po progu |
| `agentKey` w API / sesji / runie | `schemas`, `chat_sessions`, `agent_runs` | FE zawsze `"github-workspace"` |
| Model | cascade `workspace_config` | **nie** per-agent |
| Bogate bloki | `card` \| `table` \| `markdown` | brak `chart` |
| Role tenanta | `tenant_memberships.role` + JWT `trol` | `owner` / `admin` / `member` (wzór: create team) |
| Settings UI | `src/modules/settings/` | account/security/connections/storage — **brak agentów** |
| App `/admin` | gear-stack leftovers | **nie** miejsce edytora agentów (Control Tower = Faza 5+) |
| Router abstrakcja | — | brak (`Explicit` / `Auto`) |

**Brakuje:** tabela/definicja Agent, CRUD dla tenant-admin, lista agentów dla pickera, `AgentRouter`, model per-agent, wykresy.

## Strategia: 3 chunki

Pionowy plaster najpierw (działający wybór + 2–3 agenci), potem persystencja/edytor, na końcu bloki.

| Chunk | Nazwa | Cel | Zależności |
|-------|-------|-----|------------|
| **A** | Rejestr + jawny routing | 2–3 agenci w rejestrze kodowym, `ExplicitAgentRouter`, picker UI | — |
| **B** | Model DB + edytor tenant-admin | Tabela `agents`, CRUD (owner/admin), seed z A, run czyta z DB | A |
| **C** | Bogate bloki — chart | Typ `chart` + renderer FE | niezależne od B (może równolegle po A) |

**Auto-router LLM** → Faza 5 (w A opcjonalnie stub `AutoAgentRouter` keyword → fallback; pełny LLM poza tym planem).  
**Control Tower** (app-admin: inventory cross-tenant + raw audit + polityki) → Faza 5+; **nie** mylić z edytorem tenantowym w B.

```
Chunk A                         Chunk B                              Chunk C
┌─────────────────────┐         ┌────────────────────────────────┐   ┌──────────────┐
│ AgentRegistry (code)│ ──────► │ agents table + tenant CRUD     │   │ chart block  │
│ ExplicitAgentRouter │         │ Settings UI (tenant owner/admin)│   │ FE renderer  │
│ Chat agent picker   │         │ Resolve from DB                │   └──────────────┘
└─────────────────────┘         └────────────────────────────────┘
```

---

## Chunk A — Rejestr + jawny routing (issue #023)

### Decyzje (propozycje)

| # | Temat | Decyzja |
|---|--------|---------|
| A1 | Forma rejestru | `AgentDefinition` dataclass/TypedDict w kodzie (key, name, description, system_prompt, tool_profile, memory_scopes, routing_hints, default_model?, is_default). Jedno źródło zamiast osobnych dictów prompt/tools. |
| A2 | Zestaw seed | (1) `github-workspace` — jak dziś (+ gmail/memory/rag); (2) `general` — rozmowa + memory (+ rag opcjonalnie), bez GitHub/Gmail; (3) `jira-360` — zachować jako legacy/disabled albo widoczny tylko gdy flaga — **propozycja: widoczny, bez soft-delete**. |
| A3 | Router | Interfejs `AgentRouter.resolve(message, *, explicit_key, session_key) → ResolvedAgent`. Start: tylko `ExplicitAgentRouter` (request > sesja > default). |
| A4 | Sesja | `agent_key` ustawiany przy create sesji; zmiana agenta w trwającej sesji = **nowa sesja** albo jawny „switch” z potwierdzeniem (propozycja MVP: **picker tylko przy nowej sesji / empty chat**; istniejąca sesja pokazuje key read-only). |
| A5 | API listy | `GET /agent/agents` (auth) — lista widocznych definicji `{ key, name, description, isDefault }` dla pickera. Bez promptów w liście. |
| A6 | Trace | W run/trace zapisać `agentKey` + `routingReason: "explicit" \| "session" \| "default"`. |
| A7 | Auto | Stub opcjonalny: `keyword` na description/hints → fallback default. **Nie** blokuje done chunka A. |

### Architektura A

```
ChatRequest.agentKey ──► ExplicitAgentRouter.resolve
                              │
                              ├─ lookup AgentRegistry.get(key)
                              ├─ build_tool_registry(profile)
                              └─ system_prompt + optional model override
FE: AgentPicker ──► GET /agent/agents ──► nowa sesja z agentKey
```

### Pliki (orientacyjnie)

| Warstwa | Pliki |
|---------|--------|
| BE | `agent/registry.py` (nowy), refaktor `agent_run_service.py` / `tools/__init__.py`, `routers/agents.py` lub list w `router.py`, `routing.py` |
| FE | `AgentPicker` w `ChatToolbar` / empty state, `useAgentChat` bez hardcode, `agentApiService.listAgents`, i18n |
| Docs | issue #023 → `in progress` / `done` |

### Todos A

| ID | Treść |
|----|--------|
| a-registry | `AgentDefinition` + rejestr 2–3 agentów; usunąć rozproszone dicty |
| a-router | `ExplicitAgentRouter` + `routingReason` w run |
| a-api-list | `GET /agent/agents` |
| a-fe-picker | Picker + wiring `agentKey` przy nowej sesji |
| a-tests | Unknown key → 4xx; default gdy brak key; lista nie leakuje promptu |
| a-docs | #023 status; ten plan chunk A ✅ |

### Kryteria done A

- [ ] ≥2 agenci w rejestrze, różne prompt + tool profile  
- [ ] Picker w UI przy nowej rozmowie  
- [ ] Run używa wybranego promptu/profilu  
- [ ] Trace ma `agentKey` + powód routingu  

---

## Chunk B — Model DB + edytor tenant-admin (dec. #10–11)

### Decyzje (propozycje)

| # | Temat | Decyzja |
|---|--------|---------|
| B1 | Scope | Agenci **tenant-scoped** (`tenant_id`). Seed systemowy kopiowany przy onboardingu tenanta **albo** wiersze `is_builtin` z `tenant_id` nullable (app-level) widoczne we wszystkich tenantach. **Propozycja MVP:** tylko tenant-scoped + migracja seed dla istniejących tenantów z definicji chunka A. |
| B2 | Klucz | `key` = slug (`^[a-z0-9]+(?:-[a-z0-9]+)*$`, max 100), **immutable** po create. `id` = `generate_id`. Unikalność `(tenant_id, key)`. |
| B3 | Pola (MVP) | `name`, `description`, `system_prompt`, `model` (nullable = cascade default), `effort` (nullable), `tool_profile` (JSONB `string[]` bucketów), `memory_scopes` (JSONB, default `["session","user","agent"]`), `rag_enabled` (bool), `routing_hints` (JSONB: triggers/examples), `visibility` (`tenant` \| `team` — MVP tylko `tenant`), `team_id` nullable, `is_enabled`, `is_default`, `created_by`, timestamps. |
| B4 | Poza MVP w schemacie | Kolumna `limits` JSONB nullable (placeholder); `guardrails` JSONB nullable (placeholder — research). Nie budować UI. |
| B5 | Model | `model` z definicji ∩ `allowedModels` z cascade; jeśli puste allow → dowolny z katalogu; jeśli agent.model poza allow → **fallback** na effective default + warning w trace (nie 500). |
| B6 | Tool profile | Lista **bucketów** (`github`, `gmail`, `memory`, `rag`, …) — jak dziś. Nie per-tool allow-lista w MVP (tool search i tak deferuje). |
| B7 | Auth CRUD | **Tenant owner/admin** aktywnego workspace (`CurrentTenantContext` + `membership.role in ("owner", "admin")`) — wzór jak `POST` teams. Zwykły `member`: tylko `GET` listy (meta bez pełnego promptu w liście; detail z promptem też tylko owner/admin). **App `AdminUser` / `/admin` — poza zakresem** (Control Tower Faza 5+). |
| B8 | Resolve runtime | `AgentRegistry` staje się fasadą: DB first → fallback builtin seed in-code tylko w migracji; po B **brak** hardcodu promptów w Pythonie (prompty w DB). Opcja: pliki `prompts/*.py` tylko jako źródło seed migracji. |
| B9 | Soft delete | `is_enabled=false` zamiast hard delete; sesje ze starym `agent_key` dalej działają (read-only definicja) albo 410 przy run — **propozycja: disabled → 400 „agent disabled” przy nowym runie**. |
| B10 | Default | Co najwyżej jeden `is_default=true` per tenant (unique partial index / service enforce). |
| B11 | Skille | Biblioteka skilli (Kancelaria) — **poza zakresem** Fazy 3; ewentualny follow-up jako „user templates”, nie mylić z Agent. |

### Schema (szkic)

```sql
CREATE TABLE agents (
  id            VARCHAR(26) PRIMARY KEY,
  tenant_id     VARCHAR(26) NOT NULL REFERENCES tenants(id),
  key           VARCHAR(100) NOT NULL,
  name          VARCHAR(200) NOT NULL,
  description   TEXT NOT NULL DEFAULT '',
  system_prompt TEXT NOT NULL,
  model         VARCHAR(200),          -- null = cascade default
  effort        VARCHAR(50),
  tool_profile  JSONB NOT NULL DEFAULT '[]',
  memory_scopes JSONB NOT NULL DEFAULT '["session","user","agent"]',
  rag_enabled   BOOLEAN NOT NULL DEFAULT false,
  routing_hints JSONB NOT NULL DEFAULT '{}',
  visibility    VARCHAR(20) NOT NULL DEFAULT 'tenant',
  team_id       VARCHAR(26),
  is_enabled    BOOLEAN NOT NULL DEFAULT true,
  is_default    BOOLEAN NOT NULL DEFAULT false,
  limits        JSONB,
  guardrails    JSONB,
  created_by    VARCHAR(26),
  created_at    TIMESTAMPTZ NOT NULL,
  updated_at    TIMESTAMPTZ NOT NULL,
  UNIQUE (tenant_id, key)
);
-- partial unique: one default per tenant WHERE is_default
```

Migracja: `064_agents.py` (numer potwierdzić vs aktualny max) + seed `github-workspace` / `general` (+ opcjonalnie `jira-360`) per tenant.

### API (szkic)

Wszystko pod prefixem agenta / workspace, w kontekście **aktywnego tenanta** z JWT (jak chat/memory). Bez mountu `/admin`.

| Method | Path | Kto |
|--------|------|-----|
| GET | `/agent/agents` | dowolny member — lista enabled (meta: key, name, description, isDefault; **bez** `system_prompt`) |
| GET | `/agent/agents/{id}` | owner/admin — detail z promptem (member → 403) |
| POST | `/agent/agents` | owner/admin — create |
| PATCH | `/agent/agents/{id}` | owner/admin — partial update (nie `key`) |
| POST | `/agent/agents/{id}/set-default` | owner/admin — atomowo |
| POST | `/agent/agents/{id}/duplicate` | owner/admin — opcjonalnie v1.1 |

Helper: `_require_tenant_agent_admin(tenant_ctx)` — `role in ("owner", "admin")`, analogicznie do create team.

### UI (tenant settings)

- `/settings/agents` — lista (name, key, model, tools chips, enabled, default); widoczna / edytowalna dla owner/admin; member nie widzi sekcji lub widzi read-only „ask admin”
- `/settings/agents/:id` (lub panel/drawer) — formularz: name, description, prompt (textarea), model (combobox jak w czacie), tool buckets (checkbox group), memory scopes, rag toggle, routing hints, enabled/default
- Nav: nowa pozycja w settings (obok connections/storage), nie w app `/admin`
- Wzorce: istniejące settings pages + tokeny Fazy 1.5; ukryj CRUD gdy `activeTenantRole` ∉ `{owner, admin}`

### Todos B

| ID | Treść |
|----|--------|
| b-migration | Tabela `agents` + seed z rejestru A |
| b-repo-service | Repository + `AgentService` (CRUD, default enforce, resolve) |
| b-runtime | `build_tool_registry` / prompt / model z DB; usunąć hardcode |
| b-api | CRUD pod `/agent/agents` + guard owner/admin; list meta dla member |
| b-fe-settings | Settings routes + lista/formularz + i18n; gate po `activeTenantRole` |
| b-tests | Uniqueness key, default partial, disabled run, model ∩ allow-list, **403 dla member na mutate/detail** |
| b-docs | Plan chunk B ✅; wzmianka MVP / CLAUDE fazy |

### Kryteria done B

- [ ] Tenant owner/admin tworzy/edytuje agenta; pojawia się w pickerze membera  
- [ ] Member dostaje 403 na mutate / detail z promptem  
- [ ] Run czyta prompt/tools/model z DB  
- [ ] Seed migracji = dotychczasowe zachowanie `github-workspace`  
- [ ] Brak `AGENT_PROMPTS` dict w runtime  
- [ ] Brak zależności od app `AdminUser` / `/admin`  


---

## Chunk C — Bogate bloki: chart

### Decyzje (propozycje)

| # | Temat | Decyzja |
|---|--------|---------|
| C1 | Typ | `type: "chart"` obok `card` / `table` / `markdown` |
| C2 | Payload | `{ chartType: "line" \| "bar", title?, xLabel?, yLabel?, series: [{ name, points: [{ x, y }] }] }` — minimalny kontrakt |
| C3 | Źródło | (1) helper w `_build_blocks_from_trace` gdy tool zwróci uzgodniony shape **lub** (2) agent emituje przez przyszły `emit_block` — **MVP: tylko (1) z jawnego JSON w wyniku toola / konwencji**; bez osobnego toola `render_chart` na start |
| C4 | FE | lekka lib już w ekosystemie **albo** SVG/CSS minimal — sprawdzić zależności repo; preferuj istniejącą (np. jeśli jest recharts/chart.js) |
| C5 | Rejestr | FE: map `block.type → component`; BE: walidacja Pydantic union |

### Todos C

| ID | Treść |
|----|--------|
| c-schema | Typ + walidacja BE/FE |
| c-renderer | `AgentChartBlock.vue` + rejestr |
| c-emit | Ścieżka build z trace / konwencja tool result |
| c-tests | Snapshot / unit payload → render props |

### Kryteria done C

- [x] Przynajmniej line chart renderuje się w czacie z mock/fixture bloku  
- [x] Nie psuje card/table  

Zrealizowane inaczej niż w pierwotnym szkicu C4: gotowa lib **`@unovis/ts`/`@unovis/vue`** była już zależnością repo (razem z nieużywanym dotąd scaffoldem `src/components/ui/chart/`) — użyto jej zamiast dokładać nową zależność. Bar chart renderuje się przez **jeden** `VisGroupedBar` z tablicowymi `y`/`color` (osobne instancje per seria nakładałyby się na siebie). Zweryfikowano wizualnie w przeglądarce (line + grouped bar + card + table na jednej stronie, light i dark) przez tymczasowy debug route (usunięty przed commitem).

---

## Poza zakresem (świadomie)

- Auto-router LLM (Faza 5)  
- Control Tower (raw audit UI, polityki, inventory cross-tenant)  
- Biblioteka skilli / custom instructions użytkownika (research #007 — osobny plan)  
- Sub-agenci / LangGraph  
- Per-tool allow-lista (tylko buckety)  
- Team-visibility egzekwowana w UI (pole w schemacie OK)  
- Zdalne agenty wykonawcze (Faza 6)  
- No-code drag&drop jak Copilot Studio  

## Ryzyka

| Ryzyko | Mitygacja |
|--------|-----------|
| Rozjazd seed vs live prompts | Seed z tych samych stringów co dziś; po B edycja tylko w DB |
| Zmiana `agent_key` łamie memory scope | Key immutable |
| Tenant-admin edytuje prompt → regresja dogfood | Duplicate + is_default tylko na sprawdzonych |
| Model spoza allow-list | Fallback + trace warning |
| Chunk B zbyt duży | Nie zaczynać B bez done A; ewentualnie B1 = read-only DB mirror bez UI |

## Otwarte punkty (do potwierdzenia przed kodem)

1. **Chunk start:** A → B → C jak wyżej? (rekomendacja: tak)  
2. **Trzeci agent:** `general` vs osobny `gmail`? Propozycja: **`general`** + Gmail zostaje w `github-workspace`.  
3. **Zmiana agenta w trwającej sesji:** zablokowana vs switch? Propozycja: **zablokowana** (read-only badge).  
4. **CRUD auth:** ~~tylko `AdminUser`?~~ → **rozstrzygnięte (2026-07-23):** tenant `owner`/`admin`; app `/admin` poza zakresem.  
5. **Builtin app-level vs seed per tenant?** Propozycja: **seed per tenant**.  
6. **Chart lib:** potwierdzić przy starcie C po audycie `package.json`.  
7. **Czy `jira-360` w pickerze?** Propozycja: tak, enabled, description „legacy / requires Jira”.  
8. **UI path:** `/settings/agents` vs osobna pozycja w workspace nav? Propozycja: **`/settings/agents`**.

## Kolejność implementacji

1. Potwierdzenie otwartych punktów (ten dokument).  
2. Chunk A (domyka #023 P0).  
3. Chunk B (właściwy edytor).  
4. Chunk C (może startować po A, równolegle do B jeśli pojemność).  
5. Status planu → `done`; skrót w `MVP.md` / `CLAUDE.md` (Faza 3).

## Kryteria done (cała Faza 3 w tym planie)

- [x] Chunk A–C spełniają swoje kryteria  
- [x] Dec. #9 (jawny wybór) + #10–11 (obiekt Agent w DB + edytor tenant-admin) + #14 (chart) pokryte w MVP-sense  
- [x] Issue #023 `done`  
- [x] Ten plan `done`; wiersz w `plans/README.md`  
