# Plan 010 — Faza 4.5: Second Brain (wiki + bibliotekarz), pgvector-only

**Status:** `planned`
**Data:** 2026-07-25
**Obszar:** backend (`wiki` nowy moduł, `rag`, `agent/tools`) + frontend (przeglądarka folderów)
**Parent:** [004 Second Brain](2026-07-23--004--second-brain-wiki.md) — realizuje todo `path-mcp-or-pages`, `wiki-folder-browser`; **zamyka** `spike-docker-mcp` i `decide-path`
**Wymaga:** [009 Jakość retrievalu](2026-07-25--009--phase-4-retrieval-quality.md) — ten plan konsumuje jego pipeline chunków
**Research:** [008](../research/2026-07-25--008--embeddings-rag-second-brain.md) §7

> **Wykonawca:** Claude Sonnet. Schemat i flow pochodzą z planu 004 — tutaj są doprecyzowane do implementacji.

## Cel

Second Brain w AI Workspace: **wiki/wiedza** — przeglądarka z folderami + agent-bibliotekarz, bez Obsidiana i **bez zewnętrznego silnika retrieval**.

1. `wiki_pages` + `wiki_links` z ACL per-user w tenancie.
2. Toole bibliotekarza: `wiki_ingest`, `wiki_query`, `wiki_lint`.
3. Strony wiki indeksowane **tym samym pipeline'em** co reszta RAG (plan 009) — jeden retrieval, jedna ścieżka ACL.
4. UI: foldery + podgląd Markdown + graf.

## Decyzja wstępna: LightRAG odrzucony (zamyka `decide-path`)

Plan 004 przewidywał spike LightRAG (1–2 dni, porty 9621/8010) z bramką go/no-go. **Rezygnujemy ze spike'u i idziemy prosto do ścieżki no-go** („retrieval tylko u nas, pgvector na wiki/chunkach").

Uzasadnienie (pełne w research 008 §7):

1. **Duplikacja store'u** — LightRAG trzyma własny KV + wektor + graf. Po planie 009 mamy hybrid search z rerankerem. Drugi zbiór wektorów tej samej treści to dokładnie ten „drugi mózg", którego plan 004 zabrania w warstwie pamięci.
2. **ACL** — u nas `tenant_id`+`user_id` idzie w `WHERE` **przed** rankingiem i jest testowany. Przeniesienie tego do zewnętrznego silnika (namespace w warstwie aplikacji) to regres w modelu bezpieczeństwa.
3. **Ops** — nowy kontener na VPS, pin obrazu, vendor drift; za funkcję, którą `wiki_links` + `[[wikilinks]]` pokrywają dla naszego use-case'u.

**Zakres decyzji:** dotyczy wyłącznie warstwy **wiedzy**. Graphiti (pamięć życiowa) to osobna sprawa — plan [011](2026-07-25--011--memory-graph-graphiti.md).

Porty `9621` / `8010` zarezerwowane w planie 004 dla LightRAG — **zwalniamy**.

## Stan obecny (reuse)

| Element | Gdzie | Jak używamy |
|---------|-------|-------------|
| Pipeline chunków + retrieval | `app/modules/rag/` (po planie 009) | strona wiki → `rag_documents` `source_type="wiki"` |
| `RetrievalAcl` / `RetrievalHit` | `app/modules/rag/types.py` | bez zmian |
| Rejestr narzędzi | `app/modules/agent/tools/__init__.py` (`build_tool_registry`) | nowy profil `wiki` |
| Profile agentów | `app/modules/agent/registry.py` | dopisać `wiki` tam, gdzie jest `rag` |
| `generate_id` | `app/common/id_utils.py` | PK stron i linków |
| Wzorzec UI listy | `src/modules/workspace/pages/WorkspaceMemoryPage.vue` | wzorzec dla przeglądarki |
| Migracje | ostatnia w planie 009: `065` | ten plan → **`066`** |

## Decyzje

| # | Temat | Decyzja |
|---|-------|---------|
| 1 | Moduł | Nowy `backend/app/modules/wiki/` (nie puchnąć `rag`) |
| 2 | Migracja | **`066_wiki_pages.py`** |
| 3 | ACL | **Per-user w tenancie**: `tenant_id` + `user_id`. Brak `team_id` w schemacie MVP (z planu 004) |
| 4 | Retrieval | **Brak własnego.** Strona → `rag_documents` (`source_type="wiki"`, `source_ref` = `wiki_pages.id`) → chunki → hybrid + rerank z planu 009 |
| 5 | Foldery | `raw` \| `inbox` \| `entities` \| `concepts` \| `summaries` \| `meta` |
| 6 | Raw immutable | Po utworzeniu strony w `raw` — update i delete **odrzucane** (409) |
| 7 | Flow ingest | `wiki_ingest` = **auto**: Raw → Summary → ripple Entities/Concepts → wpis w Log. Bez kolejki approve |
| 8 | Inbox | **Bez auto-promocji** — digest siedzi w `inbox` do jawnego `wiki_ingest` |
| 9 | Limit ripple | **15 stron / ingest** (z otwartego punktu planu 004). Przekroczenie → obcięcie + ostrzeżenie w Log |
| 10 | Usuwanie / deprecate | Agent **nie kasuje sam** — `wiki_lint` raportuje, zmiana statusu na `deprecated` wymaga potwierdzenia użytkownika (akcja w UI / jawne API) |
| 11 | Index | Strona `meta`/`index` **utrzymywana przez agenta** (nie generowana z zapytania) — propozycja z planu 004 |
| 12 | Wikilinki | Parser `[[slug]]` / `[[slug\|tekst]]` przy zapisie → pełny rebuild krawędzi dla `from_page_id`; dangling → `to_page_id = NULL` |
| 13 | Seed | Przy pierwszym użyciu w tenancie/userze: strony `meta`/`index` i `meta`/`log` |
| 14 | Eksport `.md` | Poza zakresem (otwarty punkt planu 004) |

## Schemat DB

Migracja **`066_wiki_pages.py`**.

### `wiki_pages`

| Kolumna | Typ | Uwaga |
|---------|-----|-------|
| `id` | `String(36)` PK | `generate_id()` |
| `tenant_id` | `String(36)` NOT NULL | FK `tenants` ON DELETE CASCADE |
| `user_id` | `String(36)` NOT NULL | FK `users` ON DELETE CASCADE — ACL |
| `folder` | `String(20)` NOT NULL | CHECK: `raw`\|`inbox`\|`entities`\|`concepts`\|`summaries`\|`meta` |
| `slug` | `String(200)` NOT NULL | UNIQUE `(tenant_id, user_id, folder, slug)` |
| `title` | `Text` NOT NULL | |
| `body_md` | `Text` NOT NULL | |
| `frontmatter` | `JSONB` nullable | tagi, daty, flagi `unverified` |
| `source_url` | `Text` nullable | głównie `raw` / `summaries` |
| `status` | `String(20)` NOT NULL DEFAULT `'active'` | CHECK: `active`\|`deprecated` |
| `immutable` | `Boolean` NOT NULL DEFAULT `false` | `true` dla `raw` |
| `document_id` | `String(36)` nullable | FK → `rag_documents` ON DELETE SET NULL — powiązanie z chunkami |
| `created_at` / `updated_at` | `DateTime(tz)` NOT NULL | |

Indeksy: `(tenant_id, user_id, folder)`, `(tenant_id, user_id, updated_at DESC)`.

### `wiki_links`

| Kolumna | Typ | Uwaga |
|---------|-----|-------|
| `id` | `String(36)` PK | |
| `tenant_id` / `user_id` | `String(36)` NOT NULL | denormalizacja pod ACL i graf |
| `from_page_id` | FK `wiki_pages` ON DELETE CASCADE | |
| `to_page_id` | FK `wiki_pages` ON DELETE SET NULL, nullable | `NULL` = dangling |
| `to_slug` | `String(200)` NOT NULL | cel przed resolucją |
| `link_text` | `Text` nullable | |

Indeksy: `(tenant_id, user_id)`, `(from_page_id)`, `(to_slug)`.

## Architektura

```
                    ┌── UI: przeglądarka folderów ──┐
                    │   Raw / Inbox / Wiki / meta   │
                    └───────────────┬───────────────┘
                                    │  REST
  agent ──[wiki_ingest]──►  WikiService  ◄────────────┘
                                    │
      ┌─────────────────────────────┼──────────────────────────┐
      ▼                             ▼                          ▼
  wiki_pages                   wiki_links               rag_documents
  (raw → summary                (parser                 source_type="wiki"
   → entities/concepts)          [[wikilinks]])          source_ref=page.id
                                                              │
                                                              ▼
                                                    pipeline z planu 009
                                              chunk → embed → hybrid + rerank
                                                              │
  agent ──[wiki_query]──────────────────────────────────────►─┘
                                     (rag_search zawężony do source_type="wiki")
```

### Flow bibliotekarza

```
Inbox (digest / capture)  --[jawne wiki_ingest]-->  Raw (immutable)
                                                      │
                                                      ▼
                                              Summary + ripple
                                           Entities / Concepts  (max 15 stron)
                                                      │
                                                      ▼
                                              Index + Log (append)
```

### API

| Method | Path | Opis |
|--------|------|------|
| `GET` | `/wiki/pages` | filtry `folder`, `status`, `q`; ACL |
| `GET` | `/wiki/pages/{id}` | strona + linki wychodzące/przychodzące |
| `POST` | `/wiki/pages` | ręczne utworzenie (np. digest w `inbox`) |
| `PATCH` | `/wiki/pages/{id}` | edycja; **409** gdy `immutable` |
| `DELETE` | `/wiki/pages/{id}` | **409** gdy `immutable`; inaczej 204 |
| `POST` | `/wiki/pages/{id}/deprecate` | jawna zmiana statusu (dec. #10) |
| `POST` | `/wiki/ingest` | to samo co tool — wygodne do debugowania |
| `GET` | `/wiki/graph` | węzły + krawędzie do widoku grafu (ACL) |

### Agent — toole

| Tool | Parametry | Zwraca |
|------|-----------|--------|
| `wiki_ingest` | `content` \| `source_url`, `title?` | `{ rawPageId, summaryPageId, rippledPages: [...], truncated: bool }` |
| `wiki_query` | `query`, `limit?` | fragmenty **wyłącznie ze stron w scope usera**, z `pageId` + `slug` (cytaty) |
| `wiki_lint` | `scope?` (`all`\|`folder`) | raport: dangling linki, sieroty, duplikaty slugów, strony bez linków. **Fix mechaniczny** (normalizacja slugów, rebuild linków) automatycznie; rewrite treści / deprecate → propozycja do potwierdzenia |

Rejestracja: profil `"wiki"` w `AGENT_TOOL_PROFILES` (`app/modules/agent/registry.py`), wpięcie w `build_tool_registry()`. Nie w `CORE_TOOL_NAMES`.

Prompt (jedna linia w agencie `github-workspace`): krótki fakt → `memory_save`; treść ze źródła → `wiki_ingest`; pytanie o materiały → `wiki_query`.

### Frontend

Wszystko w `src/modules/workspace/`: `pages/WorkspaceWikiPage.vue` + `services/wikiApiService.ts` + `composables/useWikiBrowser.ts` + `types/wiki.ts` + wpis w `config/routes.ts` (`/workspace/wiki`).

- Lewa kolumna: drzewo folderów (`Raw` / `Inbox` / `Wiki` → `Entities`/`Concepts`/`Summaries` / `Index`+`Log`)
- Środek: lista stron (tytuł, tagi, `updated_at`, badge `deprecated`)
- Prawa / główna: podgląd Markdown + linki wychodzące i przychodzące
- Zakładka **Graf**: węzły = strony, krawędzie = `wiki_links`; dangling wyróżnione
- Akcje: nowa strona w `inbox`, ingest, deprecate (z potwierdzeniem), usuń (blokada dla `raw`)
- i18n `t('wiki.*')`

## Testy

| Case | Oczekiwanie |
|------|-------------|
| ACL — ten sam tenant | User A nie czyta ani nie mutuje stron usera B |
| ACL — inny tenant | j.w., 404 (nie 403 — nie ujawniamy istnienia) |
| Raw immutable | `PATCH` / `DELETE` na stronie `raw` → **409** |
| Wikilinki | Zapis treści z `[[a]]` i `[[b\|tekst]]` → 2 krawędzie; nieistniejący cel → `to_page_id NULL` |
| Rebuild linków | Edycja usuwająca link → krawędź znika (pełny rebuild, nie append) |
| `wiki_ingest` | Tworzy Raw + Summary + ≥1 Entity/Concept + wpis w Log (LLM mockowany) |
| Limit ripple | Ingest generujący > 15 stron → obcięcie + `truncated: true` + wpis w Log |
| Inbox | Digest w `inbox` **nie** tworzy Summary ani Entities bez jawnego ingest |
| `wiki_query` | Cytaty wyłącznie ze stron w scope usera; strona `deprecated` poza wynikami |
| Indeksacja | Zapis strony → `rag_documents` `source_type="wiki"` + chunki; usunięcie strony → dokument i chunki znikają |
| Seed | Pierwsze użycie → strony `meta`/`index` i `meta`/`log` |
| `wiki_lint` | Dangling i sieroty w raporcie; deprecate **nie** wykonuje się bez potwierdzenia |
| Migracja `066` | `upgrade` / `downgrade` czyste |

## Todos

| ID | Treść |
|----|--------|
| `wiki-migration` | Migracja **`066`**: `wiki_pages` + `wiki_links` + indeksy + CHECK |
| `wiki-module` | `app/modules/wiki/`: `db_models`, `types`, `schemas`, `repositories`, `services/wiki_service.py`, `router.py` |
| `wiki-links-parser` | Parser `[[…]]` + rebuild krawędzi przy zapisie; resolucja `to_slug` → `to_page_id` |
| `wiki-rag-bridge` | Zapis / usunięcie strony → synchronizacja `rag_documents` (`source_type="wiki"`); `wiki_query` = retrieval z planu 009 zawężony po `source_type` |
| `wiki-tools` | `wiki_ingest` / `wiki_query` / `wiki_lint`; profil `wiki`; limit ripple 15; prompt |
| `wiki-seed` | Seed stron `meta`/`index` i `meta`/`log` przy pierwszym użyciu |
| `wiki-ui` | Przeglądarka folderów + podgląd Markdown + graf + akcje |
| `wiki-tests` | Zestaw z sekcji Testy |
| `docs-close` | Plan 004: `spike-docker-mcp` / `decide-path` / `path-mcp-or-pages` / `wiki-folder-browser` → zamknięte; `MVP.md` Faza 4.5; ten plan → `done`; `CHANGELOG.md` |

## Poza zakresem

- LightRAG i każdy zewnętrzny silnik retrieval (dec. wstępna)
- Graphiti / memory graph (plan 011)
- Team-shared wiki (`team_id`, visibility) — poza MVP wg planu 004
- Eksport vaultu do `.md` (Obsidian-friendly)
- Kolejka approve/reject dla ingestu
- Wersjonowanie stron / historia zmian

## Ryzyka

| Ryzyko | Mitygacja |
|--------|-----------|
| Koszt ripple przy dużym ingeście | Twardy limit 15 stron + `truncated` w odpowiedzi + wpis w Log |
| Agent kasuje wiedzę | `wiki_lint` tylko raportuje; delete/deprecate za jawnym potwierdzeniem (dec. #10) |
| Rozjazd `wiki_pages` ↔ chunki | Synchronizacja w jednym miejscu (`wiki-rag-bridge`), transakcyjnie z zapisem strony |
| Mylenie wiki z pamięcią | Osobne toole + jedna linia w prompcie: fakt → memory, treść ze źródła → wiki |
| Kolizja slugów | UNIQUE `(tenant_id, user_id, folder, slug)`; przy konflikcie sufiks `-2` |
| Graf nie skaluje się w UI | Limit węzłów w `GET /wiki/graph` (propozycja: 300) + filtr po folderze |

## Otwarte punkty (do potwierdzenia przed kodem)

1. **Ripple sync czy async** — propozycja: **sync** w ramach `wiki_ingest` (limit 15 stron trzyma czas w ryzach); async dopiero gdy limit zacznie uwierać.
2. **Czy `wiki_query` to osobny tool, czy parametr `source_type` w `rag_search`** — propozycja: **osobny tool**, bo zwraca cytaty ze slugami stron, a nie fragmenty dokumentów; agent inaczej ich używa.
3. **Widok grafu** — propozycja: prosty force-directed na SVG bez nowej zależności; biblioteka dopiero jeśli okaże się za wolne.

## Kryteria done

- [ ] Migracja `066` (`upgrade`/`downgrade`) zielona
- [ ] CRUD stron z ACL per-user; Raw immutable (409)
- [ ] `[[wikilinks]]` → `wiki_links` z rebuildem; dangling obsłużone
- [ ] `wiki_ingest` tworzy Raw + Summary + ripple ≤ 15 + wpis w Log
- [ ] Inbox nie promuje się sam
- [ ] Strona wiki indeksowana pipeline'em z planu 009; `wiki_query` zwraca cytaty tylko ze scope usera
- [ ] Przeglądarka folderów + podgląd + graf działają
- [ ] Testy z sekcji Testy zielone
- [ ] Plan 004: todo `spike-docker-mcp`, `decide-path`, `path-mcp-or-pages`, `wiki-folder-browser` zamknięte
