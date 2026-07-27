# Plan 011 — Memory graph: facade + cutover na Graphiti

**Status:** `in progress`
**Data:** 2026-07-25
**Obszar:** backend (`memory`, `agent`), infra (compose, FalkorDB)
**Parent:** [004 Second Brain](2026-07-23--004--second-brain-wiki.md) — realizuje todo `later-graphiti-memory`
**Wymaga:** [009](2026-07-25--009--phase-4-retrieval-quality.md) i [010](2026-07-25--010--phase-4-5-second-brain-wiki.md) — ten plan jest **ostatni** w Fazie 4
**Research:** [008](../research/2026-07-25--008--embeddings-rag-second-brain.md) §6

> **Wykonawca:** Claude Sonnet.
> **⚠️ Plan bramkowany.** Etapy **1–2** wykonaj. Etapy **3+** wymagają **jawnej zgody użytkownika** po przedstawieniu wyników bramki. Nie przechodź dalej samodzielnie.

## Cel

Przygotować warstwę pamięci na podmianę backendu i **zmierzyć**, czy Graphiti (temporalny graf wiedzy) jest tego wart — zamiast zakładać, że jest.

1. **Etap 1** — `MemoryService` jako facade nad `MemoryBackend` Protocol. Wartość sama w sobie, zero zmiany zachowania.
2. **Etap 2** — spike Graphiti + FalkorDB z twardymi metrykami → **bramka go/no-go**.
3. **Etap 3+** — migracja, dual-read, cutover, rollback. **Tylko po zielonej bramce.**

## Dlaczego w ogóle

Dzisiejsze `memory_entries` to płaska lista faktów z wektorem. Dwie rzeczy, których pgvector nie da (research 008 §6):

- **Temporalność** — „co ustaliliśmy" vs „co ustaliliśmy *wtedy*". Fakty wygasają i są zastępowane, zamiast kumulować się jako sprzeczne duplikaty. To wprost adresuje otwarty punkt `MVP.md` „pamięć jako lifecycle / decay".
- **ACL przez `group_id`** — mapuje się 1:1 na `tenant_id:user_id`.

Koszt jest jednak realny: kontener FalkorDB, drugi store, ingest przez LLM. A benchmarki są **sporne**: Mem0 zmierzył footprint Zepa na >600k tokenów per rozmowa (vs 1764 dla Mem0) i 65.99% LoCoMo; Zep odpowiedział, że pomiar był błędnie skonfigurowany, i podał 75.14%. **Nie ufamy żadnej z tych liczb** — mierzymy sami. Stąd bramka.

## Stan obecny (reuse)

| Element | Gdzie | Uwaga |
|---------|-------|-------|
| Serwis pamięci | `backend/app/modules/memory/services/memory_service.py` | `create_entry`, `search`, `list_entries`, `update_entry`, `delete_entry`, `build_injection_context` |
| Repozytorium | `backend/app/modules/memory/repositories.py` | `search_similar`, `_scope_filter_sql`, ACL `tenant_id`+`user_id`+scope |
| Model | `backend/app/modules/memory/db_models.py` (`MemoryEntry`) | kolumna `embedding` **nie jest zmapowana w ORM** — raw SQL |
| Typy | `backend/app/modules/memory/types.py` | `MemoryScope` (`session`/`user`/`agent`), `MemorySource` |
| Toole | `backend/app/modules/agent/tools/memory.py` | `memory_search` / `memory_save` / `memory_update` |
| Injection | `backend/app/modules/agent/services/agent_run_service.py:330-341` | `build_injection_context()` w system prompcie |
| Router | `backend/app/modules/memory/router.py` | `GET/POST/PATCH/DELETE /memory`, `POST /memory/search` |
| UI | `src/modules/workspace/pages/WorkspaceMemoryPage.vue` | |
| Testy | `backend/tests/modules/test_memory.py` (14) | |
| Porty zajęte | app `8003`, Postgres `5435`, Redis `6382`, Vite `5176` | FalkorDB → **`6383`** (nie `6382`!) |

## Decyzje

| # | Temat | Decyzja |
|---|-------|---------|
| 1 | Facade | `MemoryBackend` Protocol; `PgVectorMemoryBackend` = dzisiejsza implementacja przeniesiona 1:1. Toole, router i injection wołają **wyłącznie** facade |
| 2 | Flaga | `MEMORY_BACKEND=pgvector\|graphiti`, default **`pgvector`** |
| 3 | Zakaz | **Nigdy dwa aktywne write-pathy pamięci na produkcji** (z planu 004). Dual-**read** tak, dual-**write** nie |
| 4 | Izolacja | Graphiti `group_id` = `f"{tenant_id}:{user_id}"`. Zero zapytań bez `group_id` |
| 5 | Infra | Jedna instancja + namespace. **Nie** mnożymy kontenerów per tenant |
| 6 | Port | FalkorDB host **`6383`**, kontener `ai-workspace-graphiti`, `COMPOSE_PROJECT_NAME` izolowany |
| 7 | Okno read-only | Po cutoverze `memory_entries` read-only przez **14 dni**, dopiero potem archiwizacja |
| 8 | Rollback | Flip `MEMORY_BACKEND=pgvector`. Dane w `memory_entries` nietknięte do końca okna. Po archiwizacji rollback = restore z backupu DB (świadomie) |
| 9 | Injection | Graphiti nie wstrzykuje sam — `build_injection_context()` woła jego search API, tak jak dziś woła pgvector |
| 10 | Scope ↔ graf | `MemoryScope` (`session`/`user`/`agent`) mapowany na atrybuty epizodu; `group_id` pokrywa **tylko** tenant+user |

## Etap 1 — facade (wykonaj)

**To jest bezpieczny refaktor bez zmiany zachowania.** Ma wartość niezależnie od losu Graphiti: bez niego każda podmiana backendu oznacza przepisanie serwisu, tooli i injection.

```python
# app/modules/memory/backends/base.py
class MemoryBackend(Protocol):
    async def create(self, *, tenant_id: str, user_id: str, scope: MemoryScope,
                     content: str, agent_key: str | None, session_id: str | None,
                     source: MemorySource, metadata: dict | None) -> MemoryEntryDTO: ...
    async def search(self, *, tenant_id: str, user_id: str, query: str,
                     scope: MemoryScope | None, limit: int,
                     min_similarity: float) -> list[MemoryHit]: ...
    async def update(self, *, entry_id: str, tenant_id: str, user_id: str,
                     content: str | None, scope: MemoryScope | None) -> MemoryEntryDTO | None: ...
    async def delete(self, *, entry_id: str, tenant_id: str, user_id: str) -> bool: ...
    async def list_entries(self, ...) -> tuple[list[MemoryEntryDTO], int]: ...
```

- `app/modules/memory/backends/pgvector.py` — `PgVectorMemoryBackend`, przeniesienie dzisiejszej logiki z `MemoryService` + `MemoryRepository`. **Zero zmiany SQL i zachowania.**
- `MemoryService` staje się cienką warstwą: wybór backendu po `settings.ai.memory_backend` + `build_injection_context()` (formatowanie sekcji promptu zostaje tutaj — jest wspólne dla backendów).
- Toole, router i `agent_run_service` **bez zmian w wywołaniach**.

**Kryterium done etapu 1:** wszystkie 14 istniejących testów `test_memory.py` przechodzą **bez modyfikacji asercji**. Jeśli test trzeba zmienić, refaktor zmienił zachowanie — cofnij.

## Etap 2 — spike Graphiti (wykonaj, potem STOP)

Osobny compose (`docker-compose.graphiti.yml`), **nie** dopisywać do `docker-compose.dev.yml`.

| Usługa | Kontener | Port hosta |
|--------|----------|-----------|
| FalkorDB | `ai-workspace-graphiti` | **6383** |

Zakres spike'u:
- `GraphitiMemoryBackend` implementujący `MemoryBackend` (minimalnie: `create` + `search`)
- ingest ~10 realnych rozmów per user, 2 userów × 2 tenantów
- pomiar metryk z bramki

### Bramka go/no-go

| Kryterium | Próg go | Dlaczego |
|-----------|---------|----------|
| Izolacja `group_id` | **0 wycieków** w cross-query (2 userów × 2 tenantów) | twardy wymóg bezpieczeństwa — pojedynczy wyciek = automatyczne no-go |
| p95 `search` (VPS, warm) | **< 3 s** | pamięć jest w ścieżce injection każdego runa |
| Ingest 10 rozmów | **< 5 min** wall clock | |
| RSS kontenera | **< 2 GB** | VPS dzieli zasoby z app/db/redis |
| **Koszt ingestu** | **< 25k tokenów / rozmowę** | świadomie mierzony po sporze Mem0↔Zep (research 008 §6) |
| Jakość vs dziś | Graphiti znajduje ≥ tyle trafnych faktów co pgvector na tym samym zbiorze | inaczej płacimy za ops bez zysku |

**Wynik spike'u zapisz w `docs/research/` jako nowy wpis** (`NNN` = następny wolny) z tabelą pass/fail.

### ⛔ STOP

Po etapie 2: **przedstaw użytkownikowi wyniki bramki i zapytaj o decyzję.** Nie zaczynaj etapu 3.

**No-go = w porządku.** Wtedy: zostaje `PgVectorMemoryBackend`, facade i tak jest zyskiem, a lifecycle pamięci (decay/konsolidacja) realizujemy w pgvectorze — dedupe jest już w planie 009 (`memory-dedupe`), decay dojdzie jako osobny wycinek.

## Etapy 3+ — cutover (TYLKO po zielonej bramce i zgodzie)

Sekwencja z planu 004, bez skrótów:

3. **Migracja danych** — skrypt `python -m cli memory migrate-graphiti [--dry-run]`: eksport `memory_entries` → epizody/fakty per user. Walidacja: zgodność liczników + ręczny sample search na ≥20 wpisach.
4. **Dual-read** — write → Graphiti; read → Graphiti primary, **fallback `memory_entries`** przy miss lub błędzie. Okno zabezpieczające. **Bez dual-write.**
5. **Cutover** — write-only Graphiti; `memory_entries` **read-only** przez 14 dni (backup).
6. **Archiwizacja** — dopiero po okresie stabilności; po tym rollback możliwy już tylko z backupu DB.

**Rollback na każdym etapie 3–5:** flip `MEMORY_BACKEND=pgvector`. Dane w `memory_entries` nietknięte.

## Testy

| Case | Etap | Oczekiwanie |
|------|------|-------------|
| Regresja facade | 1 | 14 testów `test_memory.py` bez zmian asercji |
| Wybór backendu | 1 | Flaga przełącza implementację; nieznana wartość → błąd startu, nie cichy fallback |
| Injection | 1 | `build_injection_context()` daje identyczny prompt jak przed refaktorem |
| Izolacja `group_id` | 2 | Cross-query 2×2 → 0 wycieków |
| Metryki bramki | 2 | Zapisane w wpisie research jako pass/fail |
| Brak dual-write | 3–5 | Test dowodzi, że przy `MEMORY_BACKEND=graphiti` **nie ma** zapisu do `memory_entries` |
| Fallback dual-read | 4 | Miss w Graphiti → wynik z `memory_entries`; błąd Graphiti → to samo + log |
| Read-only | 5 | Próba zapisu do `memory_entries` po cutoverze → odrzucona |
| Rollback | 3–5 | Flip flagi → pełna funkcjonalność na pgvector |

## Todos

| ID | Etap | Treść |
|----|------|--------|
| `memory-facade` | 1 | `MemoryBackend` Protocol + `PgVectorMemoryBackend`; `MemoryService` jako cienka warstwa |
| `memory-flag` | 1 | `MEMORY_BACKEND` w `AISettings` + `.env.example`; walidacja wartości na starcie |
| `graphiti-compose` | 2 | `docker-compose.graphiti.yml`, FalkorDB na `6383`, pin obrazu |
| `graphiti-backend` | 2 | `GraphitiMemoryBackend` (create + search), `group_id` = `tenant:user` |
| `graphiti-metrics` | 2 | Pomiar bramki + wpis w `docs/research/` |
| `gate-decision` | 2 | **STOP** — przedstawić wyniki użytkownikowi |
| `memory-migrate` | 3 | CLI eksportu `memory_entries` → epizody, `--dry-run`, walidacja liczników |
| `dual-read` | 4 | Graphiti primary + fallback pgvector, bez dual-write |
| `cutover` | 5 | Write-only Graphiti; `memory_entries` read-only 14 dni |
| `archive` | 6 | Archiwizacja starej tabeli po stabilności |
| `docs-close` | — | Plan 004 `later-graphiti-memory` → zamknięte; `MVP.md` (punkt „memory graph cutover"); ten plan → `done` |

## Poza zakresem

- Mem0 / Letta jako alternatywne backendy (research 008 §6 — do rozważenia dopiero przy no-go Graphiti)
- Graf wiedzy dla wiki (to `wiki_links`, plan 010)
- Team-shared pamięć (`team_id` w ACL)
- Kontener per tenant (jawne no-go z planu 004)

## Ryzyka

| Ryzyko | Mitygacja |
|--------|-----------|
| Dwa aktywne write-pathy | Zakaz w dec. #3 + test dowodzący braku zapisu do `memory_entries` |
| Wyciek między tenantami | `group_id` obowiązkowy w każdym zapytaniu; test cross-query jako **twarde** kryterium bramki |
| Koszt LLM przy ingeście Graphiti | Zmierzony w bramce (<25k tok/rozmowę); przekroczenie = no-go |
| RAM na VPS | Próg RSS < 2 GB; compose osobny, łatwy do zatrzymania |
| Utrata pamięci przy migracji | `--dry-run` + walidacja liczników + okno read-only 14 dni + rollback flagą |
| Vendor drift Graphiti | Pin obrazu i wersji biblioteki; backend za `MemoryBackend` Protocol |
| Spike zjada czas Fazy 4 | Etap 2 to spike, nie wdrożenie — timebox 1–2 dni, potem decyzja niezależnie od wyniku |

## Otwarte punkty

1. **Mapowanie `MemoryScope` na graf** — `session`/`user`/`agent` nie mają odpowiednika 1:1 w epizodach. Propozycja: `group_id` = tenant+user, scope jako atrybut epizodu i filtr w search.
2. **Co z `memory_update`** — Graphiti aktualizuje fakty przez nowy epizod, nie przez UPDATE. Propozycja: `update` na backendzie Graphiti = invalidacja starego faktu + nowy epizod; kontrakt toola bez zmian.
3. **Okno read-only** — 14 dni z planu 004. Do potwierdzenia przy cutoverze.
4. **Czy w ogóle** — no-go jest pełnoprawnym wynikiem. Facade z etapu 1 zostaje tak czy inaczej.

## Kryteria done

**Etap 1 (obowiązkowy) — ✅ done (2026-07-27):**
- [x] `MemoryBackend` Protocol + `PgVectorMemoryBackend`
- [x] `MEMORY_BACKEND` w configu i `.env.example`
- [x] 16 testów `test_memory.py` zielonych **bez zmiany asercji** (było 14 w planie, jest 16 w repo)
- [x] Injection daje identyczny prompt jak przed refaktorem
- [x] Test walidacji nieznany backend → ValueError / ValidationError

**Etap 2 (obowiązkowy) — 🟡 infrastruktura gotowa, bramka czeka na klucz API:**
- [x] `docker-compose.graphiti.yml` — FalkorDB v4.20.1, port 6383
- [x] `GraphitiMemoryBackend` (create + search; update/delete/list → NotImplementedError)
- [x] Spike runner (`evals/memory_graphiti/`) — fixtures 2×2×10, metryki bramki
- [x] Wpis w `docs/research/2026-07-27--009--graphiti-spike-gate.md`
- [ ] Spike uruchomiony z kluczem API, 6 metryk bramki zmierzone
- [ ] Wyniki przedstawione użytkownikowi, decyzja podjęta

**Etapy 3+ (warunkowe):**
- [ ] Tylko po zielonej bramce i jawnej zgodzie
