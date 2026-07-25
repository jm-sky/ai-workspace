# Research 008 — Embeddingi, RAG i Second Brain (Faza 4)

**Data:** 2026-07-25
**Status:** `done`
**Obszar:** backend (`memory`, `rag`, `agent`), infra (pgvector), docs
**Powiązane:** MVP dec. **#12** (pamięć), **#17** (baza wektorowa); plany [004](../plans/2026-07-23--004--second-brain-wiki.md), [005](../plans/2026-07-23--005--memory-update.md), [006](../plans/2026-07-23--006--rag-retrieval-chunks.md)
**Domyka otwarte punkty MVP:** „Model embeddingów + reranker", „Eval RAG", „Graph RAG tylko lazy/incremental"

Ten dokument jest **bazą decyzyjną** dla trzech planów implementacji: [009](../plans/2026-07-25--009--phase-4-retrieval-quality.md) (jakość retrievalu), [010](../plans/2026-07-25--010--phase-4-5-second-brain-wiki.md) (Second Brain wiki), [011](../plans/2026-07-25--011--memory-graph-graphiti.md) (memory graph).

---

## 1. Stan obecny w repo (audyt 2026-07-25)

Faza 4 ma **fundament**, brakuje **warstwy jakości i produktu**.

### Co działa

| Element | Gdzie | Uwaga |
|---------|-------|-------|
| pgvector + HNSW | migracje `059_memory_entries.py`, `063_document_chunks.py` | `vector_cosine_ops`, defaulty pgvector (`m=16`, `ef_construction=64`) |
| Wspólny klient embeddingów | `backend/app/common/embeddings.py` | OpenRouter, `openai/text-embedding-3-small`, 1536d |
| Pamięć: CRUD + search + ACL | `backend/app/modules/memory/` | scope `session`/`user`/`agent`, ACL `tenant_id`+`user_id` |
| Auto-injection pamięci | `agent_run_service.py:330-341` | `build_injection_context()`, limit 5, próg 0.55, cicha degradacja na wyjątku |
| RAG: chunki + retrieval | `backend/app/modules/rag/` | `split_text()`, `RagService`, `PgChunkRetriever` |
| ACL przed rankingiem | `rag/repositories.py:176` (`search_chunks`) | `WHERE tenant_id AND user_id` **przed** `ORDER BY <=>` — spełnia wymóg permissions-aware retrieval |
| Toole agenta | `agent/tools/memory.py`, `agent/tools/rag.py` | `memory_search` / `memory_save` / `memory_update` (CORE) + `rag_search` (profil `rag`) |
| Kaskada `ragEnabled` | `workspace_config` → tool i API | tool no-op + `message` gdy `false` |
| UI pamięci | `src/modules/workspace/pages/WorkspaceMemoryPage.vue` | lista, edycja, `ILIKE` filtr |
| Testy | `backend/tests/modules/test_memory.py` (14), `test_rag.py` (11) | `EmbeddingService` mockowany |

### Czego brakuje

| Luka | Konsekwencja | Adresuje plan |
|------|--------------|---------------|
| Brak rerankera | top-8 z czystego cosine; typowe zapytania wieloaspektowe gubią trafny chunk | 009 |
| Brak hybrid search (lexical) | zapytania z nazwą własną / ID / symbolem kodu (`generate_id`, numer ticketu) trafiają słabo — embeddingi są złe w exact-match | 009 |
| `text-embedding-3-small` na treściach PL | model anglocentryczny; treści w repo i u użytkownika są dwujęzyczne | 009 |
| `embed()` obsługuje 1 tekst, brak batcha/retry/cache | ingest 200 chunków = 200 sekwencyjnych roundtripów **w cyklu HTTP**; `AI_CACHE_TTL_EMBED` istnieje w configu i jest nieużywany | 009 |
| Splitter znakowy 1200/150 | tnie w połowie zdania i tabeli; chunk bez nagłówka traci kontekst | 009 |
| `source_type="attachment"` / `"wiki"` = martwy kod | załączniki czatu (migracja `062`, `chat_attachment_service.py`, ekstrakcja PDF przez `pypdf`) **nie** trafiają do `document_chunks` | 009 |
| Brak evala RAG | zmiana chunkera/modelu/progu = zgadywanie; nie wiadomo czy jest lepiej | 009 |
| Brak UI Knowledge | RAG istnieje tylko przez API i tool — użytkownik nie ma jak zarządzać źródłami | 009 |
| Brak dedupe/decay pamięci | agent zapisuje duplikaty; jedyna mitygacja to podpowiedź w opisie `memory_update` | 009 |
| Brak `wiki_pages` | Second Brain nie istnieje | 010 |
| `MemoryService` bez facade | podmiana backendu pamięci = przepisanie serwisu i tooli | 011 |
| `AI_MEMORY_*` / `AI_RAG_*` nieudokumentowane w `.env.example` | niedomknięte todo `docs-touch` z planu 006 | 009 |

**Uwaga architektoniczna:** indeks HNSW jest globalny, nie partycjonowany po tenancie. Przy dużej liczbie tenantów filtr ACL w `WHERE` może obniżyć recall (HNSW przechodzi graf i dopiero potem filtruje). Dziś nieistotne, ale to znany próg skali — do obserwacji, nie do naprawy teraz.

---

## 2. Embeddingi

### Problem

`openai/text-embedding-3-small` (1536d) jest tani i szybki, ale w benchmarkach multilingual (MMTEB) i polskich (PL-MTEB) wypada wyraźnie poniżej czołówki. Nasz korpus jest **dwujęzyczny PL/EN** (dokumentacja, notatki, wiadomości, kod), więc to nie jest różnica kosmetyczna.

### Kandydaci (stan MMTEB / PL-MTEB, lipiec 2026)

| Model | Wymiary | Matryoshka | Języki | Hosting | Uwaga |
|-------|---------|------------|--------|---------|-------|
| `openai/text-embedding-3-small` (dziś) | 512/1536 | ✅ | anglocentryczny | API | ~64.6 MTEB; tani ($0.02/M tok), 8k ctx |
| **Cohere `embed-v4`** | 256/512/1024/**1536** | ✅ | 100+ | API | zachowuje nasz `vector(1536)`; mocny multilingual |
| **`gemini-embedding-001`** | 768/**1536**/3072 | ✅ | multilingual | API | ~68.3 MTEB; #1 wśród API przez długi czas |
| Qwen3-Embedding-8B | do 4096 (od 32) | ✅ | 100+ | self-host / API | **najlepszy wynik na PL-MTEB**, ale 8B ⇒ GPU |
| KaLM-Embedding-Gemma3-12B | — | ✅ | multilingual | self-host | #1 MMTEB (72.32, VII 2026) — 12B, nierealne u nas |
| Llama-Embed-Nemotron-8B | — | ✅ | 250+ | self-host | open-weight, 8B ⇒ GPU |

### Rekomendacja

> **Migracja na model multilingual z matryoshką ustawioną na 1536 wymiarów.**
> Kandydaci pierwszego wyboru: `cohere/embed-v4` lub `google/gemini-embedding-001`.

Uzasadnienie:

1. **VPS OVH nie ma GPU** — modele 8B/12B (Qwen3, KaLM, Nemotron) odpadają jako self-host, mimo najlepszych wyników. Zostają API.
2. **1536d to nie przypadek** — obie tabele (`memory_entries`, `document_chunks`) mają `vector(1536)`. Model z matryoshką przycięty do 1536 oznacza, że migracja to **re-embed danych, a nie zmiana typu kolumny i przebudowa indeksu HNSW**. To różnica między jednym skryptem CLI a migracją z downtime.
3. **Wybór finalny po pomiarze, nie z tabelki** — MTEB v2 (2026) nie jest porównywalny z v1, a rankingi różnią się między boardami (English v2 vs MMTEB). Decyduje wynik na **naszym** złotym zbiorze (sekcja 5), nie średnia z benchmarku.

**Do weryfikacji na starcie implementacji:** czy OpenRouter serwuje wybrany model przez `/embeddings`. OpenRouter ma endpoint embeddings i kolekcję modeli embeddingowych, ale katalog się zmienia. Jeśli modelu nie ma — ten sam `EmbeddingService` dostaje drugą implementację z bezpośrednim SDK dostawcy; interfejs się nie zmienia.

**Konsekwencja dla schematu:** kolumna `embedding_model` + `embedding_version` na obu tabelach. Bez tego nie da się zrobić stopniowego re-embedu ani rollbacku — a mieszanie wektorów z dwóch modeli w jednym indeksie daje ciche, nieodtwarzalne złe wyniki (wektory są w różnych przestrzeniach, cosine między nimi jest bez znaczenia).

---

## 3. Chunking

### Stan

`backend/app/modules/rag/chunker.py` — `split_text()`: okna 1200 znaków, overlap 150, cap 200 chunków. Bez świadomości zdań, markdown i tokenów.

### Techniki 2026

| Technika | Na czym polega | Koszt | Zysk |
|----------|----------------|-------|------|
| Structure-aware split | granice na nagłówkach / akapitach / blokach kodu; nagłówek sekcji doklejany do chunku | zerowy (kod) | duży przy dokumentacji i markdownie — a to nasz główny korpus |
| **Contextual Retrieval** (Anthropic) | LLM generuje 50–100 tokenów kontekstu per chunk („ta sekcja opisuje X w dokumencie Y") **przed** embeddingiem | 1 wywołanie LLM per chunk (można cache'ować prompt dokumentu) | −49% retrieval failures; **−67% w połączeniu z rerankerem** |
| Late chunking (Jina) | embedduje cały dokument, dopiero potem tnie — chunki dziedziczą kontekst globalny | wymaga modelu z długim kontekstem i wsparciem po stronie embeddera | zysk rośnie z długością dokumentu |

Late chunking i contextual retrieval rozwiązują **ten sam problem** (utrata kontekstu na granicy chunku) różnymi drogami; wynik zależy mocno od modelu embeddingów.

### Rekomendacja

1. **Teraz, bez dyskusji:** splitter świadomy struktury markdown (nagłówki, akapity, bloki kodu) — czysty zysk za cenę kodu.
2. **Za flagą, domyślnie off:** contextual prefix (wariant Anthropic). Uzasadnienie flagi: to koszt LLM liniowy w liczbie chunków — dopóki eval nie pokaże zysku na naszym korpusie, nie płacimy.
3. **Late chunking:** odłożony — wymaga embeddera ze wsparciem, a my właśnie zmieniamy model. Wracamy do tematu po ustabilizowaniu wyboru.
4. Anthropic wprost zaleca łączenie contextual embeddings z **contextual BM25** — co spina się z sekcją 4.

---

## 4. Hybrid search i reranking

### 4.1 Hybrid (dense + lexical)

Czysty wektor gubi exact-match: nazwy własne, identyfikatory, symbole kodu, numery ticketów. To dokładnie nasz profil zapytań („co mówi `generate_id`", „PR 412", „`WORKSPACE_DEFAULT_MODEL`").

Postgres daje obie połowy bez nowej infrastruktury:

- **dense:** pgvector `<=>` (mamy)
- **lexical:** wbudowany `tsvector` + `ts_rank_cd` (cover density — wariacja w duchu BM25)
- **fuzja:** Reciprocal Rank Fusion, `score = Σ 1/(k + rank_i)`, `k=60` jako standardowy default

Raportowane rzędy wielkości z praktyki: sam wektor ~62% precyzji retrievalu → ~84% po dołożeniu full-text + RRF, z niemal idealnym exact-match. Traktujemy to jako kierunek, nie obietnicę — potwierdza to nasz eval.

**Opcja późniejsza:** `pg_textsearch` (Tiger Data) wnosi do Postgresa prawdziwy BM25 zamiast `ts_rank_cd`, bez wychodzenia poza jedną bazę. Nie na teraz — nowe rozszerzenie w obrazie DB to zmiana infry, a `ts_rank_cd` wystarczy, by zmierzyć czy hybrid w ogóle pomaga.

**Pułapka językowa:** `to_tsvector('polish', …)` wymaga słownika `polish` w obrazie Postgresa (nie jest domyślny). Plan 009 musi wykryć dostępność konfiguracji i degradować do `'simple'` (bez stemmingu, ale działa) zamiast wywalać ingest.

### 4.2 Reranking

Cross-encoder scoruje pary `(query, chunk)` wspólnie, więc widzi interakcję zapytania z treścią — czego bi-encoder (embedding) z definicji nie robi. Standardowy układ: **retrieve top-50 → rerank → top-8 do promptu**.

| Model | Licencja / dostęp | Języki | Uwaga |
|-------|-------------------|--------|-------|
| Cohere Rerank 4 (Pro / Fast) | API | 100+ | Pro ~1629 ELO w rankingach; Fast pod latencję |
| Zerank 2 | API | — | ~1638 ELO, czoło stawki |
| Voyage rerank-2.5 | API | — | ~595–603 ms średniej latencji; sensowne, jeśli ktoś już jest na Voyage |
| Jina Reranker v2 base multilingual | API / weights | multilingual | |
| **bge-reranker-v2-m3** | **Apache 2.0**, self-host | 100+ | zero kosztu per-call, ale potrzebuje CPU/RAM — na VPS bez GPU latencja przy top-50 jest ryzykiem |

### Rekomendacja

> **`Reranker` jako Protocol. `NoopReranker` domyślnie. `HostedReranker` (HTTP) za feature flagiem.**

Uzasadnienie: VPS nie ma GPU, a dokładanie kontenera z modelem CPU pod nieudowodniony zysk to zła kolejność. Interfejs kosztuje jeden plik, a pozwala:
- włączyć hosted API bez zmiany kodu retrievalu,
- zmierzyć zysk evalem **zanim** zapłacimy za infrastrukturę,
- podmienić na self-host `bge-reranker-v2-m3` później, jeśli koszt per-call zacznie boleć.

Kryteria wyboru dostawcy są znane i mierzalne: przyrost w evalu **na naszym korpusie**, latencja end-to-end przy top-50, licencja, pokrycie językowe PL.

---

## 5. Ewaluacja RAG

Bez evala każda zmiana w sekcjach 2–4 jest zgadywaniem. To jest warunek wstępny, nie dodatek.

### Złoty zbiór

Trójki `(pytanie, oczekiwana odpowiedź, oczekiwane chunki źródłowe)` z weryfikacją ludzką. To jest **etap, który zespoły najczęściej pomijają, i jednocześnie najważniejsza inwestycja w jakość evala**. Cel: 100–200 pytań, **dwujęzycznie PL/EN**, odzwierciedlających realne wzorce zapytań (fakt z dokumentu, exact-match po symbolu, pytanie wieloaspektowe, pytanie bez odpowiedzi w korpusie).

### Metryki

Cztery metryki czytane **jako panel**, nie pojedynczo:

| Metryka | Odpowiada na pytanie |
|---------|----------------------|
| faithfulness | czy odpowiedź stawia tylko tezy poparte kontekstem |
| answer relevancy | czy odpowiedź w ogóle dotyczy pytania |
| context precision | czy pobrane chunki są trafne (ile śmiecia w top-k) |
| context recall | czy pobraliśmy wszystko, co potrzebne |

### Narzędzia

| Narzędzie | Rola u nas |
|-----------|-----------|
| **RAGAS** | offline, przy strojeniu chunkera / modelu / progów |
| **DeepEval** | **bramka CI** — GitHub Actions, fail buildu gdy faithfulness spadnie poniżej progu |
| Langfuse / Phoenix / TruLens | obserwowalność produkcyjna — poza zakresem Fazy 4 |

Dojrzały układ to RAGAS do eksperymentów + DeepEval jako bramka na kuratorowanym złotym zbiorze. Tak też rekomendujemy.

---

## 6. Pamięć: memory graph

### Krajobraz 2026

Benchmarki: **LoCoMo**, **LongMemEval**, BEAM.

| System | Model pamięci | Wynik / koszt (deklarowany) |
|--------|---------------|------------------------------|
| **Mem0** | ekstrakcja faktów + wektor, token-efficient | 92.5% LoCoMo, 94.4% LongMemEval, **<7k tokenów** per retrieval (vs 25k+ dla full-context) |
| **Zep / Graphiti** | **temporalny graf wiedzy** — fakt ma czas i relację do wcześniejszych | Mem0 raportuje 65.99%; Zep odpowiada, że był źle skonfigurowany, i podaje 75.14% |
| **Letta** (ex-MemGPT) | „LLM jako OS": main context / recall / archival, model sam stronicuje | mocne dla agentów autonomicznych |

**Kontrowersja jest istotna, nie plotkarska.** Mem0 zmierzył footprint Zepa na **>600k tokenów per rozmowa** (vs 1764 dla Mem0); Zep zakwestionował metodologię. Wniosek dla nas: **nie ufamy żadnej z liczb bez własnego pomiaru kosztu ingestu**. To wchodzi wprost do bramki go/no-go w planie 011.

### Co to zmienia dla nas

Plan [004](../plans/2026-07-23--004--second-brain-wiki.md) zakłada Graphiti jako **następcę** dzisiejszego flat `memory_entries`. To nadal ma sens — Graphiti wnosi dwie rzeczy, których pgvector nie da:

1. **Temporalność** — „co ustaliliśmy" vs „co ustaliliśmy *wtedy*"; fakty wygasają i są zastępowane, zamiast kumulować się jako sprzeczne duplikaty. To wprost adresuje otwarty punkt „pamięć jako lifecycle / decay" (`MVP.md`).
2. **ACL przez `group_id`** — mapuje się 1:1 na nasz `tenant_id:user_id`.

Ale wnosi też **realny koszt ops**: kontener FalkorDB, drugi store, ingest przez LLM. Dlatego rekomendacja jest dwuetapowa:

> **Etap 1 (bezpieczny, wartościowy sam w sobie):** `MemoryService` jako facade nad `MemoryBackend` Protocol, `PgVectorMemoryBackend` = dzisiejsza implementacja, flaga `MEMORY_BACKEND`. Zero zmiany zachowania.
> **Etap 2 (bramkowany):** spike Graphiti + FalkorDB z twardymi metrykami. Cutover dopiero po zielonej bramce.

Twarda zasada z planu 004 zostaje: **nigdy dwa aktywne write-pathy pamięci na produkcji.** Dual-**read** tak, dual-write nie.

---

## 7. Second Brain

### Wzorzec

„LLM wiki" (Karpathy / natural20): vault Markdown + agent-bibliotekarz, który przyjmuje surowe źródła (Raw), streszcza je (Summary) i propaguje zmiany do stron encji i konceptów (ripple), utrzymując Index i Log.

Mapowanie na nasz stack (z planu 004):

| Element wzorca | U nas |
|----------------|-------|
| Obsidian (przeglądarka) | UI folderów + graf w Workspace (Vue) |
| Claude Code (bibliotekarz) | pętla agenta + toole `wiki_ingest` / `wiki_query` / `wiki_lint` |
| Vault Markdown | `wiki_pages` + `wiki_links` |
| (poza wzorcem) pamięć preferencji | `MemoryService` |

### Decyzja: LightRAG odpada

Plan 004 przewidywał spike LightRAG (1–2 dni, porty 9621/8010) jako opcjonalny silnik retrieval/grafu pod spodem. **Odrzucamy go** — bez uruchamiania spike'u.

Uzasadnienie:

1. **Duplikacja store'u.** LightRAG trzyma własny KV + wektor + graf. Po planie 009 mamy własny pipeline chunków z hybrid search i rerankerem oraz ACL wymuszonym w SQL. LightRAG oznaczałby drugi zbiór wektorów tej samej treści — czyli dokładnie ten „drugi mózg", którego plan 004 zabrania w warstwie pamięci.
2. **ACL to nasz twardy wymóg, nie ich.** Multi-tenancy w LightRAG to namespace/workspace w warstwie aplikacji. U nas filtr `tenant_id`+`user_id` idzie w `WHERE` **przed** rankingiem i jest testowany (`test_rag.py`). Przeniesienie tego do zewnętrznego silnika to regres w modelu bezpieczeństwa, nie postęp.
3. **Koszt ops bez odpowiadającego zysku.** Nowy kontener na VPS, pin obrazu, vendor drift — za funkcję (graf encji), którą `wiki_links` + `[[wikilinks]]` pokrywają dla naszego use-case'u.
4. Plan 004 sam definiował warunek no-go: „którykolwiek próg fail → retrieval tylko u nas (pgvector na wiki/chunkach)". Idziemy do tej ścieżki bezpośrednio.

Zamknięte przez tę decyzję todo z planu 004: `spike-docker-mcp`, `decide-path`.

**Graphiti to inna sprawa** — nie jest alternatywą dla LightRAG. LightRAG ≈ wiedza ze źródeł (nasze `wiki_pages` + chunki), Graphiti ≈ pamięć życiowa (sekcja 6). Odrzucenie pierwszego nie przesądza drugiego.

### Konsekwencja architektoniczna

**Wiki nie dostaje własnego retrievalu.** Strona wiki po zapisie trafia do `rag_documents` z `source_type="wiki"` i przechodzi tym samym pipeline'em chunków, hybrid search i rerankera co reszta. Jeden retrieval, jedna ścieżka ACL, jeden eval.

---

## 8. Rekomendacje → plany

| # | Wniosek | Plan | Todo |
|---|---------|------|------|
| 1 | Model multilingual @1536d + wersjonowanie wektorów | 009 | `embed-versioning`, `embed-swap`, `reembed-cli` |
| 2 | Batch + retry + cache embeddingów; ingest poza cyklem HTTP | 009 | `embed-swap`, `async-ingest` |
| 3 | Splitter świadomy markdownu; contextual prefix za flagą | 009 | `chunker-v2` |
| 4 | Hybrid dense + `ts_rank_cd` + RRF (`k=60`), fallback `simple` dla PL | 009 | `hybrid-search` |
| 5 | `Reranker` Protocol, `NoopReranker` default, hosted za flagą | 009 | `reranker-iface` |
| 6 | Złoty zbiór PL/EN + RAGAS offline + DeepEval jako bramka CI | 009 | `eval-harness` |
| 7 | Załączniki czatu → `rag_documents` (domknięcie martwego kodu) | 009 | `attachment-ingest` |
| 8 | UI Knowledge | 009 | `ui-knowledge` |
| 9 | Dedupe przy `memory_save` | 009 | `memory-dedupe` |
| 10 | `wiki_pages` / `wiki_links` + toole bibliotekarza, retrieval przez pipeline 009 | 010 | całość |
| 11 | LightRAG odrzucony bez spike'u | 010 | zamyka `spike-docker-mcp`, `decide-path` w planie 004 |
| 12 | Facade `MemoryBackend` teraz; Graphiti za bramką i flagą | 011 | całość |

---

## 9. Otwarte punkty po tym researchu

1. **Który konkretnie model embeddingów** — `cohere/embed-v4` vs `gemini-embedding-001`. Rozstrzyga pomiar na złotym zbiorze (todo `eval-harness` przed `embed-swap`), nie ten dokument. Do potwierdzenia też dostępność w katalogu OpenRouter.
2. **Który dostawca rerankera** — j.w., decyduje przyrost w evalu i latencja przy top-50.
3. **Contextual retrieval** — włączamy tylko jeśli eval pokaże zysk uzasadniający koszt LLM per chunk.
4. **Late chunking** — wracamy po ustabilizowaniu modelu embeddingów.
5. **`pg_textsearch` zamiast `ts_rank_cd`** — dopiero gdy hybrid udowodni wartość, a `ts_rank_cd` okaże się wąskim gardłem.
6. **Partycjonowanie HNSW po tenancie** — do obserwacji przy wzroście liczby tenantów; dziś nieistotne.
7. **Team-shared scope** — pamięć i dokumenty są ściśle per-user (`user_id` w każdym `WHERE`). Rozszerzenie ACL o `team_id` to osobna decyzja produktowa, poza Fazą 4.

---

## Źródła

**Embeddingi**
- [PL-MTEB: Polish Massive Text Embedding Benchmark (ACL 2026)](https://aclanthology.org/2026.findings-acl.1773.pdf)
- [Embedding Model Leaderboard: MTEB Rankings (2026)](https://awesomeagents.ai/leaderboards/embedding-model-leaderboard-mteb-april-2026/)
- [Which Embedding Model Should You Actually Use in 2026?](https://zc277584121.github.io/rag/2026/03/20/embedding-models-benchmark-2026.html)
- [Top embedding models on the MTEB leaderboard (Modal)](https://modal.com/blog/mteb-leaderboard-article)
- [Qwen3-Embedding (GitHub)](https://github.com/QwenLM/Qwen3-Embedding)
- [gemini-embedding-001: Dimensions, Pricing and Usage Guide (2026)](https://tokenmix.ai/blog/gemini-embedding-001-dimensions-pricing-guide-2026)
- [OpenRouter — Embeddings API](https://openrouter.ai/docs/api_reference/embeddings) · [kolekcja modeli embeddingowych](https://openrouter.ai/collections/embedding-models)

**Chunking**
- [Contextual Retrieval: Anthropic's Method for Cutting RAG Failures](https://medium.com/coinmonks/contextual-retrieval-anthropics-method-for-cutting-rag-failures-b28d98d57c48)
- [Late Chunking vs Contextual Retrieval (KX Systems)](https://medium.com/kx-systems/late-chunking-vs-contextual-retrieval-the-math-behind-rags-context-problem-d5a26b9bbd38)
- [RAG Chunking Strategies: A 2026 Retrieval Playbook](https://www.digitalapplied.com/blog/rag-chunking-strategies-2026-retrieval-quality-playbook)

**Hybrid search**
- [Hybrid Search in PostgreSQL: The Missing Manual (ParadeDB)](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [Building Hybrid Search for RAG: pgvector + FTS + RRF](https://dev.to/lpossamai/building-hybrid-search-for-rag-combining-pgvector-and-full-text-search-with-reciprocal-rank-fusion-6nk)
- [From ts_rank to BM25 — pg_textsearch (Tiger Data)](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres)

**Reranking**
- [Best Rerankers for RAG in 2026: 7 Models Compared](https://futureagi.com/blog/best-rerankers-for-rag-2026/)
- [Best Rerankers for RAG — Leaderboard (Agentset)](https://agentset.ai/rerankers)
- [Ultimate Guide to Choosing the Best Reranking Model (ZeroEntropy)](https://zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025/)

**Eval**
- [Ragas Alternatives in 2026: 7 Production RAG Eval Picks](https://futureagi.com/blog/ragas-alternatives-2026)
- [RAG Evaluation 2026: Methods, Metrics, Frameworks](https://datavlab.ai/post/rag-evaluation-methods-metrics-2026-guide)
- [Best RAG Evaluation Tools in 2026 (Braintrust)](https://www.braintrust.dev/articles/best-rag-evaluation-tools)

**Pamięć / Second Brain**
- [State of AI Agent Memory 2026 (Mem0)](https://mem0.ai/blog/state-of-ai-agent-memory-2026)
- [AI Agent Memory Systems in 2026: Mem0, Zep, Hindsight, Memvid — Compared](https://blog.devgenius.io/ai-agent-memory-systems-in-2026-mem0-zep-hindsight-memvid-and-everything-in-between-compared-96e35b818da8)
- [Mem0 vs Letta vs Zep: Agent Memory 2026](https://aiworkflowlab.dev/article/agent-memory-mem0-vs-letta-vs-zep-2026)
- [Graphiti MCP (Zep docs)](https://help.getzep.com/graphiti/getting-started/mcp-server)
- [Using Claude Code to set up a second brain (LLM wiki)](https://natural20.com/using-claude-code-to-setup-a-second-brain-aka-llm-wiki)
- [LightRAG (HKUDS)](https://deepwiki.com/HKUDS/LightRAG/8-examples-and-tutorials)
