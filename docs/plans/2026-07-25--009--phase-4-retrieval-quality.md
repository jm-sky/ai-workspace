# Plan 009 — Faza 4: jakość retrievalu (embeddingi, hybrid, reranker, eval)

**Status:** `planned`
**Data:** 2026-07-25
**Obszar:** backend (`rag`, `memory`, `agent/tools`, `common`, `cli`, `evals`) + frontend (strona Knowledge)
**Parent:** [004 Second Brain](2026-07-23--004--second-brain-wiki.md)
**Poprzednie wycinki:** [005 Memory UPDATE](2026-07-23--005--memory-update.md) ✅ · [006 RAG basics](2026-07-23--006--rag-retrieval-chunks.md) ✅
**Research:** [008 Embeddingi, RAG i Second Brain](../research/2026-07-25--008--embeddings-rag-second-brain.md)
**Następne:** [010 Second Brain wiki](2026-07-25--010--phase-4-5-second-brain-wiki.md) · [011 Memory graph](2026-07-25--011--memory-graph-graphiti.md)

> **Wykonawca:** Claude Sonnet. Ten plan jest samowystarczalny — wszystkie potrzebne ścieżki, nazwy i progi są niżej. Research 008 czytaj tylko po uzasadnienia „dlaczego".

## Cel

Podnieść **jakość** retrievalu zbudowanego w planie 006 i domknąć operacyjne braki ingestu. Cztery osie:

1. **Embeddingi** — model multilingual (PL/EN) + wersjonowanie wektorów + batch/retry/cache.
2. **Retrieval** — hybrid (dense + lexical + RRF) oraz reranker za interfejsem.
3. **Ingest** — chunker świadomy struktury, ingest poza cyklem HTTP, załączniki czatu jako źródło.
4. **Pomiar** — złoty zbiór PL/EN, RAGAS offline, DeepEval jako bramka CI.

Plus produkt: strona Knowledge (dziś RAG jest dostępny tylko przez API i tool).

Po tym planie plan 010 (wiki) **konsumuje ten pipeline** — nie buduje własnego retrievalu.

## Stan obecny (reuse)

| Element | Gdzie | Uwaga |
|---------|-------|-------|
| Klient embeddingów | `backend/app/common/embeddings.py` | `EmbeddingService.embed(text)` — **jeden tekst**, bez retry/cache/batcha |
| Interfejs retrievalu | `backend/app/modules/rag/types.py` | `RetrievalAcl`, `RetrievalHit`, `ChunkRetriever` (Protocol) |
| Vector search + ACL | `backend/app/modules/rag/repositories.py:176` (`search_chunks`), `PgChunkRetriever` (`:229`) | ACL w `WHERE` **przed** `ORDER BY <=>` — **nie ruszać tej własności** |
| Chunker | `backend/app/modules/rag/chunker.py` (`split_text`) | okna znakowe 1200/150, cap 200 |
| Serwis RAG | `backend/app/modules/rag/services/rag_service.py` | `ingest_paste()` — embeduje chunki **sekwencyjnie w pętli, w cyklu HTTP** |
| Router RAG | `backend/app/modules/rag/router.py` | `POST/GET/DELETE /rag/documents`, `POST /rag/search` |
| Tool | `backend/app/modules/agent/tools/rag.py` (`rag_search`) | gate na `ragEnabled`; nie w `CORE_TOOL_NAMES` |
| Pamięć | `backend/app/modules/memory/` | `MemoryRepository.search_similar`, `MemoryService.build_injection_context` |
| Załączniki czatu | migracja `062`, `backend/app/modules/agent/services/chat_attachment_service.py` | ekstrakcja tekstu + PDF (`pypdf`) — **nie trafia do chunków** |
| Config AI | `backend/app/core/config.py` (`AISettings`, ~746–806) | `memory_embedding_*`, `rag_chunk_*`, `rag_similarity_threshold`, `rag_search_limit`, `AI_CACHE_TTL_EMBED` (**nieużywany**) |
| UI pamięci (wzorzec dla Knowledge) | `src/modules/workspace/` → `pages/WorkspaceMemoryPage.vue`, `services/memoryApiService.ts`, `composables/useMemoryBrowser.ts`, `types/memory.ts`, `config/routes.ts` | |
| CLI | `backend/cli/` (Typer), grupy w `backend/cli/commands/` | wzorzec: `db.py`, `agent.py` |
| Testy | `backend/tests/modules/test_rag.py`, `test_memory.py` | `EmbeddingService` mockowany |
| Migracje | ostatnia: `064_agents.py` | ten plan → **`065`** |

**Brakuje:** wersjonowania wektorów, batcha/retry/cache embeddingów, lexical search, rerankera, structure-aware chunkera, ingestu asynchronicznego, ingestu załączników, evala, UI Knowledge, dedupe pamięci.

## Decyzje

| # | Temat | Decyzja |
|---|-------|---------|
| 1 | Model embeddingów | **Multilingual @1536d** (matryoshka). Kandydaci: `cohere/embed-v4`, `google/gemini-embedding-001`. Finalny wybór **po pomiarze** na złotym zbiorze — dlatego `eval-harness` idzie **przed** `embed-swap`. |
| 2 | Wymiar wektora | **Zostaje 1536.** Migracja = re-embed, **nie** zmiana typu kolumny i przebudowa HNSW. |
| 3 | Wersjonowanie | Kolumny `embedding_model` + `embedding_version` na `memory_entries` i `document_chunks`. Bez tego re-embed nie jest wznawialny, a mieszanie wektorów z dwóch modeli daje ciche złe wyniki. |
| 4 | Nazwa configu | Nowy `AI_EMBEDDING_MODEL` / `AI_EMBEDDING_DIMENSIONS`; stare `AI_MEMORY_EMBEDDING_*` **zostają jako alias** (deprecated) — nie łamiemy działającego `.env` na VPS. |
| 5 | Dostawca | Najpierw OpenRouter (`/embeddings`). Jeśli model nie jest w katalogu → druga implementacja `EmbeddingService` z SDK dostawcy **za tym samym interfejsem**. Zero zmian u konsumentów. |
| 6 | Lexical | Wbudowany `tsvector` + `ts_rank_cd`. **Nie** dokładamy `pg_textsearch` ani innego rozszerzenia do obrazu DB. |
| 7 | Konfiguracja FTS | Wykryj dostępność `polish` w `pg_ts_config`; brak → fallback `'simple'`. **Nigdy nie wywalaj ingestu** z tego powodu. |
| 8 | Fuzja | RRF, `score = Σ 1/(k + rank_i)`, `k=60`. Flaga `AI_RAG_HYBRID_ENABLED` (default **true**). |
| 9 | Reranker | `Reranker` Protocol. `NoopReranker` **default**, `HostedReranker` (HTTP) za flagą. Zero nowych kontenerów na VPS. |
| 10 | Pipeline | `retrieve top-N (default 50) → rerank → top-K (default 8)`. Gdy reranker = Noop, `top-N` schodzi do `top-K` (bez marnowania zapytania). |
| 11 | ACL | **Bez zmian w modelu.** ACL zostaje w `WHERE` przed rankingiem — w **obu** gałęziach hybrydy. Reranker działa wyłącznie na już przefiltrowanym zbiorze. |
| 12 | Chunker | Structure-aware (markdown: nagłówki / akapity / bloki kodu), nagłówek sekcji doklejany do chunku. Cap 200 bez zmian. `split_text` zostaje jako fallback dla tekstu bez struktury. |
| 13 | Contextual retrieval | **Poza zakresem tego planu.** Wraca po evalu — koszt LLM liniowy w liczbie chunków. |
| 14 | Ingest | Asynchroniczny: `rag_documents.status` (`pending`/`ready`/`failed`), `POST` zwraca **202**, klient odpytuje `GET`. |
| 15 | Załączniki | Załącznik czatu z wyekstrahowanym tekstem → `rag_documents` z `source_type="attachment"`, `source_ref` = id załącznika. **Opt-in użytkownika**, nie automat na każdy upload. |
| 16 | Eval | RAGAS offline + **DeepEval jako bramka CI**. Złoty zbiór w repo (JSONL), PL+EN. |
| 17 | Dedupe pamięci | `memory_save` sprawdza podobieństwo; ≥ `AI_MEMORY_DEDUPE_THRESHOLD` → **nie zapisuje**, zwraca istniejący wpis + sugestię `memory_update`. |
| 18 | UI | Strona Knowledge **wchodzi** w ten plan (w 006 była świadomie odłożona). |

## Schemat DB

Migracja **`065_retrieval_quality.py`** (poprzednia: `064_agents.py`).

### `document_chunks` — nowe kolumny

| Kolumna | Typ | Uwaga |
|---------|-----|-------|
| `embedding_model` | `String(120)` nullable | model użyty do wektora; backfill = dzisiejsza wartość z configu |
| `embedding_version` | `Integer` NOT NULL DEFAULT `1` | inkrementowana przy zmianie modelu; `reembed` wznawia po tej kolumnie |
| `content_tsv` | `tsvector` nullable | generowana w ingest (nie `GENERATED` — konfiguracja FTS jest runtime'owa, patrz dec. #7) |

Indeksy: GIN na `content_tsv`, btree na `(embedding_version)`.

### `rag_documents` — nowe kolumny

| Kolumna | Typ | Uwaga |
|---------|-----|-------|
| `status` | `String(20)` NOT NULL DEFAULT `'ready'` | `pending` \| `ready` \| `failed`; istniejące wiersze → `ready` |
| `error` | `Text` nullable | komunikat przy `failed` |

CHECK na `source_type` w migracji `063` obejmuje już `paste|attachment|wiki` — **nie wymaga zmiany**.

### `memory_entries` — nowe kolumny

`embedding_model`, `embedding_version` — jak wyżej (ten sam re-embed).

`downgrade()`: drop kolumn i indeksów w odwrotnej kolejności.

## Architektura

```
INGEST
  POST /rag/documents  ──►  document(status=pending) ──► 202 { id, status }
                                    │
                                    ▼  (task w tle)
                        chunk_markdown() ──► embed_batch() ──► insert chunks (+ content_tsv)
                                    │
                                    ▼
                             status = ready | failed

RETRIEVAL
  rag_search(query) / POST /rag/search
        │
        ▼
  RagService.search
        │
        ├─► dense:   embedding <=> :q      ─┐   WHERE tenant_id AND user_id  (ACL PRZED rankingiem)
        ├─► lexical: ts_rank_cd(content_tsv, :q) ─┤
        │                                   │
        │            RRF(k=60) ◄────────────┘
        ▼
  Reranker.rerank(query, hits, top_n=K)     ◄── NoopReranker | HostedReranker
        ▼
  top-K → { hits: [{ content, score, documentId, title, chunkIndex }] }
```

### Interfejsy (szkic)

```python
# app/common/embeddings.py
class EmbeddingService:
    model: str
    dimensions: int

    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    #   - batchuje po AI_EMBEDDING_BATCH_SIZE
    #   - retry z exponential backoff (3 próby) na 429/5xx
    #   - cache w Redis: key = sha256(model|dimensions|text), TTL = AI_CACHE_TTL_EMBED

# app/modules/rag/types.py
class Reranker(Protocol):
    async def rerank(
        self, *, query: str, hits: list[RetrievalHit], top_n: int
    ) -> list[RetrievalHit]: ...

class NoopReranker:
    """Domyślny: przycina do top_n, zachowuje kolejność wejściową."""

class HostedReranker:
    """HTTP do dostawcy (AI_RAG_RERANK_URL / _MODEL / _API_KEY).
    Na błąd lub timeout: log + degradacja do zachowania NoopReranker.
    Reranker nigdy nie wywala zapytania użytkownika."""
```

`ChunkRetriever` (Protocol) **nie zmienia sygnatury** — hybrid to implementacja wewnątrz `PgChunkRetriever`, nie nowy kontrakt.

### Chunker

```python
# app/modules/rag/chunker.py
def split_markdown(
    text: str, *, chunk_size: int, overlap: int, max_chunks: int
) -> list[str]:
    """Tnie po nagłówkach ATX i akapitach; nie rozrywa bloków ```;
    dokleja ścieżkę nagłówków ('# A > ## B') na początku chunku.
    Segment dłuższy niż chunk_size → fallback do split_text()."""
```

`split_text()` **zostaje** — jest testowany i jest fallbackiem.

### API

| Method | Path | Zmiana |
|--------|------|--------|
| `POST` | `/rag/documents` | **202** zamiast 201; body `{ id, status: "pending" }` |
| `GET` | `/rag/documents` | + `status`, `error` w odpowiedzi |
| `GET` | `/rag/documents/{id}` | j.w. |
| `DELETE` | `/rag/documents/{id}` | bez zmian |
| `POST` | `/rag/search` | + opcjonalne `hybrid`, `rerank` (override flag, do debugowania) |
| `POST` | `/rag/documents/from-attachment` | **nowy** — `{ attachmentId, title? }` → dokument `source_type="attachment"` |

### Agent

- `rag_search` bez zmiany kontraktu narzędzia — hybrid i rerank są przezroczyste dla agenta.
- Prompt: bez zmian (opis toola już mówi „wiedza ze źródeł użytkownika").
- `memory_save`: nowe pole w odpowiedzi — `{ saved: false, duplicateOf: "<id>", message: "..." }` gdy dedupe zadziała.

### Config (`AISettings`)

| Key | Default | Opis |
|-----|---------|------|
| `AI_EMBEDDING_MODEL` | *(multilingual, wybrany po evalu)* | zastępuje `AI_MEMORY_EMBEDDING_MODEL` (alias zostaje) |
| `AI_EMBEDDING_DIMENSIONS` | `1536` | musi zgadzać się z `vector(1536)` |
| `AI_EMBEDDING_VERSION` | `1` | podbić przy zmianie modelu → sygnał dla `reembed` |
| `AI_EMBEDDING_BATCH_SIZE` | `64` | rozmiar batcha w `embed_batch` |
| `AI_RAG_HYBRID_ENABLED` | `true` | dense+lexical+RRF |
| `AI_RAG_RRF_K` | `60` | stała RRF |
| `AI_RAG_FTS_CONFIG` | `auto` | `auto` \| `polish` \| `simple` |
| `AI_RAG_RERANK_ENABLED` | `false` | `true` → `HostedReranker` |
| `AI_RAG_RERANK_URL` / `_MODEL` / `_API_KEY` | — | dostawca hosted |
| `AI_RAG_RERANK_CANDIDATES` | `50` | top-N przed rerankiem |
| `AI_RAG_SEARCH_LIMIT` | `8` (jest) | top-K po reranku |
| `AI_MEMORY_DEDUPE_THRESHOLD` | `0.92` | próg dedupe przy `memory_save` |
| `AI_CACHE_TTL_EMBED` | `30` (jest) | **zacząć używać** |

Wszystkie klucze (łącznie z zaległymi `AI_MEMORY_*` / `AI_RAG_*` / `WORKSPACE_DEFAULT_RAG_ENABLED`) opisać w `backend/.env.example`.

### Frontend — strona Knowledge

Wzorzec 1:1 z pamięci, wszystko w `src/modules/workspace/`: `pages/WorkspaceKnowledgePage.vue` + `services/knowledgeApiService.ts` + `composables/useKnowledgeBrowser.ts` + `types/knowledge.ts` + wpis w `config/routes.ts` (`WorkspaceRouteName.Knowledge` / `WorkspaceRoutePath.Knowledge` = `/workspace/knowledge`).

Zakres: lista dokumentów (tytuł, źródło, liczba chunków, **status** z odświeżaniem dla `pending`), dodanie przez wklejenie tekstu, podgląd chunków, usunięcie z potwierdzeniem, pusty stan. i18n `t('knowledge.*')`.

## Testy

| Case | Oczekiwanie |
|------|-------------|
| `embed_batch` | 130 tekstów przy batchu 64 → 3 wywołania API; kolejność wyników zachowana |
| Retry | 429 → ponowienie z backoffem; po 3 nieudanych → wyjątek, dokument `failed` |
| Cache | drugi `embed` tego samego tekstu → zero wywołań API |
| Hybrid — exact match | zapytanie o rzadki token (np. `generate_id`) znajduje chunk, którego sam dense nie zwraca w top-K |
| RRF | dokument w top-1 obu list wygrywa z dokumentem w top-1 jednej |
| **ACL w hybrydzie** | user B / inny tenant → **0 hitów** w gałęzi dense **i** lexical (test osobno dla każdej) |
| FTS fallback | brak konfiguracji `polish` → ingest przechodzi, `content_tsv` zbudowany z `'simple'` |
| `NoopReranker` | przycina do `top_n`, kolejność bez zmian |
| `HostedReranker` błąd | timeout/5xx → wynik jak z Noop, log ostrzeżenia, **brak wyjątku do usera** |
| Chunker markdown | nie rozrywa bloku ```; ścieżka nagłówków w prefiksie; segment > `chunk_size` → fallback; cap 200 |
| Async ingest | `POST` → 202 + `status=pending`; po zakończeniu `ready` + chunki; błąd embeddingu → `failed` + `error` |
| Ingest z załącznika | załącznik cudzego usera → 404; własny → dokument `source_type="attachment"`, `source_ref` = id |
| Re-embed | podbicie `AI_EMBEDDING_VERSION` → CLI przetwarza tylko starsze wiersze; **drugi przebieg = 0 wierszy** (idempotencja) |
| Dedupe pamięci | zapis niemal identycznej treści → `saved=false` + `duplicateOf`; treść odmienna → zapis normalny |
| Migracja `065` | `upgrade` / `downgrade` czyste |
| Eval | runner działa na złotym zbiorze i zwraca 4 metryki; próg poniżej wartości → **exit code ≠ 0** |

Bez żywego OpenRouter: mockować `EmbeddingService.embed` / `embed_batch` (istniejący wzorzec z `test_rag.py`).

## Todos

Kolejność ma znaczenie — `eval-harness` przed `embed-swap`, bo bez pomiaru wybór modelu jest zgadywaniem.

| ID | Treść |
|----|--------|
| `eval-harness` | `backend/evals/rag/`: złoty zbiór JSONL (PL+EN, docelowo 100–200 pytań; start ≥30 z korpusu `docs/`), runner RAGAS offline, bramka DeepEval z progami, `README.md` jak dokładać pytania |
| `embed-versioning` | Migracja **`065`**: `embedding_model` / `embedding_version` na `document_chunks` i `memory_entries`; `content_tsv` + GIN; `status` / `error` na `rag_documents` |
| `embed-swap` | `EmbeddingService`: `embed_batch()`, retry z backoffem, cache Redis na `AI_CACHE_TTL_EMBED`; nowe klucze configu + aliasy; weryfikacja katalogu OpenRouter, fallback = SDK dostawcy za tym samym interfejsem |
| `reembed-cli` | `backend/cli/commands/rag.py` → `python -m cli rag reembed [--batch 100] [--dry-run]`; wznawialny po `embedding_version`, idempotentny, progres w Rich |
| `hybrid-search` | `PgChunkRetriever`: dense + `ts_rank_cd`, RRF `k=60`, ACL w obu gałęziach; detekcja konfiguracji FTS z fallbackiem `simple`; flaga `AI_RAG_HYBRID_ENABLED` |
| `reranker-iface` | `Reranker` Protocol + `NoopReranker` + `HostedReranker` w `app/modules/rag/`; wpięcie w `RagService.search` (top-50 → top-8); degradacja na błędzie |
| `chunker-v2` | `split_markdown()` obok `split_text()`; `RagService` wybiera wariant po typie treści |
| `async-ingest` | Ingest poza cyklem HTTP; `status`/`error`; `POST` → 202; `GET` zwraca status |
| `attachment-ingest` | `POST /rag/documents/from-attachment`; reuse ekstrakcji z `backend/app/modules/agent/services/chat_attachment_service.py`; ACL na załączniku |
| `memory-dedupe` | Próg `AI_MEMORY_DEDUPE_THRESHOLD` w `MemoryService.create_entry`; `memory_save` zwraca `duplicateOf` |
| `ui-knowledge` | Strona Knowledge + serwis + composable + typy + trasa + i18n |
| `docs-env` | `backend/.env.example`: wszystkie `AI_EMBEDDING_*`, `AI_RAG_*`, `AI_MEMORY_*`, `WORKSPACE_DEFAULT_RAG_ENABLED` (domyka zaległe `docs-touch` z planu 006) |
| `docs-close` | `MVP.md`: rozstrzygnięcie „model embeddingów + reranker"; ten plan → `done`; wpis w `CHANGELOG.md` |

## Poza zakresem

- Contextual retrieval / late chunking (research 008 §3 — wraca po evalu)
- `pg_textsearch` / inne rozszerzenia Postgresa
- Self-hosted reranker (kontener na VPS)
- Auto-injection RAG do system promptu (RAG zostaje agentic, przez tool)
- `wiki_pages` (plan 010), Graphiti (plan 011)
- Team-shared scope (`team_id` w ACL)
- Partycjonowanie HNSW po tenancie

## Ryzyka

| Ryzyko | Mitygacja |
|--------|-----------|
| Wybrany model nie jest w katalogu OpenRouter | Weryfikacja **na starcie** (`GET /api/v1/models`); fallback = SDK dostawcy za tym samym interfejsem (dec. #5) |
| Re-embed przerwany w połowie → mieszane wektory | `embedding_version` + wznawialne CLI; wyszukiwanie filtruje po bieżącej wersji w trakcie migracji |
| Brak słownika `polish` w obrazie Postgresa | Detekcja + fallback `'simple'` (dec. #7); test to pokrywa |
| Hosted reranker pada / timeout | Degradacja do zachowania Noop, log, zero wyjątku do użytkownika |
| Koszt embeddingów przy dużym ingeście | Cap 200 chunków (jest) + batch + cache + `dry-run` w CLI |
| Async ingest bez brokera | Start na `BackgroundTasks` FastAPI; jeśli okaże się za słabe — Redis jest w stacku, ale **nie** dokładamy Celery w tym planie |
| Eval bez ground truth staje się teatrem | Złoty zbiór budowany z realnego korpusu `docs/`, review ludzki, minimum 30 pytań na start |
| Rozjazd `AI_MEMORY_EMBEDDING_*` ↔ `AI_EMBEDDING_*` | Alias + deprecation warning; usunięcie starych kluczy dopiero po deployu |

## Otwarte punkty (do potwierdzenia przed kodem)

1. **Który model embeddingów** — `cohere/embed-v4` vs `google/gemini-embedding-001`. Propozycja: uruchomić `eval-harness` na obu i wybrać po `context recall` + `context precision`; jeśli remis — tańszy.
2. **Który dostawca rerankera** — propozycja: Cohere Rerank 4 Fast jako pierwszy strzał (pokrycie PL, latencja), zmiana bez kodu przez `AI_RAG_RERANK_URL/_MODEL`.
3. **Re-embed na produkcji** — propozycja: okno serwisowe + `--dry-run` najpierw; przy dzisiejszym wolumenie to minuty, nie godziny.

## Kryteria done

- [ ] Migracja `065` (`upgrade`/`downgrade`) zielona
- [ ] `embed_batch` + retry + cache; ingest nie robi N sekwencyjnych roundtripów
- [ ] `python -m cli rag reembed` przechodzi dwukrotnie (drugi raz: 0 wierszy)
- [ ] Hybrid + RRF działa; testy ACL zielone **osobno dla gałęzi dense i lexical**
- [ ] `Reranker` Protocol; `NoopReranker` default; `HostedReranker` degraduje na błędzie
- [ ] `split_markdown()` + testy granic
- [ ] `POST /rag/documents` → 202, status dochodzi do `ready`
- [ ] Załącznik czatu → dokument RAG (`source_type="attachment"` przestaje być martwym kodem)
- [ ] `memory_save` nie tworzy duplikatów powyżej progu
- [ ] Strona Knowledge działa (lista / dodanie / podgląd / usunięcie)
- [ ] `backend/evals/rag/` zwraca 4 metryki; bramka CI potrafi obciąć build
- [ ] `.env.example` kompletny
- [ ] `MVP.md`: otwarty punkt „Model embeddingów + reranker" → rozstrzygnięcie
