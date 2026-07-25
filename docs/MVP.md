# AI Workspace — MVP: Ustalenia

> Dokument roboczy. Zapisuje decyzje podejmowane wspólnie podczas ustalania MVP.
> Status: w trakcie ustaleń.

## North Star / kontekst

- **Odbiorca MVP:** dział IT w firmie (kancelaria podatkowa z wieloma oddziałami/departamentami jako potencjalny showcase) **+ pojedynczy developer** (dogfooding — właściciel projektu jako pierwszy użytkownik). Docelowo platforma ma być **generyczna i konfigurowalna**; multi-tenant i single-user to dwa punkty na tej samej osi, nie dwa różne produkty.
- **Kierunek (od 2026-07-11):** nie jeden „wow"-scenariusz z ustalonym przepływem, tylko **otwarty workspace w stylu ChatGPT/Claude z wieloma narzędziami**, pamięcią i zakresami tenant/team — użytkownik rozmawia, agent sięga po dostępne narzędzia i pamięć wedle potrzeby, bez sztywnego pipeline'u kroków.
- **Pierwsza konkretna instancja:** **GitHub Developer Workspace** — agent pomaga developerowi (na start: właścicielowi projektu) eksplorować repozytoria, issues, PR-y, z pamięcią międzysesyjną. Już częściowo zaimplementowany (`github-workspace` agent, Faza 1).

> **Historia:** pierwotny scenariusz MVP („widok 360° wokół issue z Jiry") napędzał Fazę 0–1 i został tam w pełni zrealizowany (patrz sekcja niżej, zachowana jako zapis). **Porzucony 2026-07-11** — brak dostępu do instancji Jiry. Ogólny cel platformy (AI-owy workspace bogaty w narzędzia) się nie zmienił, zmienił się tylko konkretny scenariusz-nośnik.

## Scenariusz MVP (aktualny)

Bez sztywnego przepływu krok-po-kroku jak w Jira 360° — agent ma dostęp do zestawu narzędzi i pamięci, użytkownik prowadzi rozmowę swobodnie. Punkt ciężkości MVP:

- **GitHub** — przeglądanie repo/issues/PR (już zaimplementowane, `github-workspace`).
- **Pamięć** — fakty/preferencje między sesjami (już zaimplementowane, pgvector — patrz Faza 4).
- **Gmail** — readonly MCP + OAuth (Faza 2) — search/list/get messages w `github-workspace`.
- **Tenant/team scopes** — te same zakresy co wcześniej (dec. #8, #15), teraz też z sensownym trybem dla pojedynczego developera (jeden tenant „ja").

## Systemy

| System | Status |
|---|---|
| GitHub | ✅ aktywny — narzędzia + OAuth zaimplementowane |
| Gmail | ✅ aktywny — OAuth + `gmail_*` tools (readonly) |
| Jira | ⏸️ odłożone — brak dostępu do instancji |
| GitLab | ⏸️ odłożone — narzędzie istnieje (`GitLabSearchByJiraKeyTool`), ale zależy od klucza Jiry; do przeprojektowania jeśli wraca do zakresu |
| Microsoft Teams | ⏸️ odłożone — brak dostępu |

## Scenariusz MVP (pierwotny, zrealizowany w Fazie 0–1 — zapis historyczny)

- **Podmiot zapytania:** Issue z Jiry.
- **Wejście:** klucz issue (np. `IT-123`).
- **Przepływ agenta:**
  1. Pobierz issue z Jiry.
  2. Wyciągnij **Klienta** — z dedykowanego pola „Klient" w Jirze (pewne źródło).
  3. Rozejdź się po systemach **różnymi kluczami** per system:
     - **GitLab** → po ID zadania (kluczu Jiry).
     - **Gmail** → po adresie e-mail Klienta.
     - **Teams** → po nazwie Klienta w rozmowach.
  4. Złóż wszystko w jeden widok 360°.

## Decyzje architektoniczne

| # | Obszar | Decyzja |
|---|--------|---------|
| 1 | Sterowanie agenta | **Agentowe (B)** — LLM w pętli (planuje → woła narzędzia → czyta wyniki → decyduje). |
| 2 | Rdzeń pętli agenta | **OpenRouter (API zgodne z OpenAI) + własna pętla tool-calling.** Klient OpenAI SDK → OpenRouter; pętlę piszemy sami (pełna kontrola nad trace/audytem, dec. 13). Narzędzia MCP (dec. 5) konwertowane do formatu tool-calling. **Model domyślny — do ustalenia** (konfigurowalny per agent/tenant, cost-sensitive; Claude drogi). **Bez LiteLLM** (OpenRouter już robi multi-provider). **LangGraph odłożony** do multi-agent. Kompromis: tracimy helper `tool_runner` i część feature'ów Anthropic-native (prompt caching sterowany z SDK, tool search, context editing) — do odzyskania później opcjonalną ścieżką „direct Anthropic" za tą samą abstrakcją modelu. |
| 3 | Uwierzytelnianie | **Per-user OAuth** — agent działa w imieniu użytkownika (Jira, GitLab, Google, Microsoft). Wymaga bezpiecznego przechowywania + odświeżania tokenów i wstrzykiwania tokenu użytkownika do wywołań narzędzi. |
| 4 | Backend | **Reuse rdzenia gear-stack** (FastAPI, users, OAuth, 2FA, RBAC, multi-tenancy, fundament API) + dołożony moduł agenta i integracje. |
| 5 | Warstwa integracji | **Opcja 2 — własne cienkie serwery MCP** (jeden na dostawcę, opakowują REST API). Jednolity standard MCP, czyste per-user token injection, brak zależności od auth cudzych serwerów. |
| 6 | Interfejs | **Chat-first (A)** — pełny czat: użytkownik pisze zapytanie, agent odpowiada widokiem 360°, można dopytywać. Bogaty output (karta/tabela + Markdown). Ten sam silnik (tool runner + MCP) obsłuży później inne fronty. |
| 7 | Frontend | **Reuse Vue z gear-stack** (Vue 3 + shadcn-vue + TanStack Query + moduł `ai` jako fundament czatu: historia, kontekst, streaming). |
| 8 | Rozwiązywanie konfiguracji | **A — kaskada z sufitami/allow-listami (governance).** Wyższy poziom ogranicza niższy: Tenant ustala allow-listę modeli i twarde limity, Zespół zawęża, Użytkownik wybiera w ramach dozwolonego. Efektywna konfiguracja = przecięcie ograniczeń + override wartości. **Sufit app-level jest opcjonalny: pusta `allowedModels` = brak sufitu** (cały katalog OpenRouter). Pierwszy poziom, który deklaruje allow-listę, definiuje zbiór; każdy niższy może go już tylko zawężać. |
| 9 | Routing agentów | **C — hybryda, router jako abstrakcja.** Interfejs „wiadomość → agent" z wymiennymi strategiami. Start: **jawny wybór** użytkownika; **auto-router LLM** dokładany później jako druga strategia, z możliwością jawnego nadpisania. |
| 10 | Definiowanie agentów | **Edytor agentów dla adminów** — agent jest konfigurowalnym obiektem definiowanym przez admina; po zdefiniowaniu jest dostępny dla routera (i użytkowników). Agent scala: model, narzędzia (tools injection), pamięć (memory injection), prompt/personę, metadane routingu. |
| 11 | Schemat obiektu Agent | Pola: **nazwa + opis** (opis używany przez auto-router), **prompt/persona**, **model** (z allow-listy, opcj. `effort`), **narzędzia MCP** (tools injection) + flaga tool search, **zakresy pamięci** (memory injection), **RAG** (on/off + źródła), **metadane routingu** (wyzwalacze/przykłady), **widoczność/uprawnienia** (zespół/tenant), **limity** (opcjonalnie, w ramach sufitów). |
| 12 | Pamięć (memory) | **Zakresy: sesja, użytkownik, agent.** Mechanizm **B (RAG-owy):** pamięć w magazynie wektorowym; automatyczne wstrzykiwanie po przekroczeniu progu podobieństwa semantycznego **+** narzędzie dla agenta do przeszukiwania pamięci na żądanie. **Współdzieli infrastrukturę wektorową z RAG.** |
| 13 | Persystencja i audyt | **Lekki Task/Run + trace** teraz (rozmowy + per uruchomienie: kroki, wywołania modelu/narzędzi wej/wyj, pobrana wiedza, tokeny/koszt, czas, status; powiązane z tenantem/użytkownikiem). Pełny Task (replay/continuation) później. **Audyt dostępny z poziomu czatu**, z przyciskiem kopiowania **całego runu** i **każdego kroku** (łącznie z system promptem) — do debugowania. |
| 14 | Wyjście do UI | **Streaming: SSE** (serwer→klient; WebSocket później, jeśli potrzebna dwukierunkowość/interrupt). **Prezentacja: Markdown (domyślnie) + rejestr bogatych bloków** renderowanych z JSON: karty, tabele, odnośniki do źródeł oraz **wykresy** (np. przychody w roku — wykres liniowy). Katalog bloków rozszerzalny (mermaid, kanban, mapy…) później. |
| 15 | Multi-tenancy | **A na start** — dane tenant-aware i izolacja per-tenant od początku, praktycznie jeden tenant. **B wkrótce** — rejestracja tenanta, onboarding, wybór/przełączanie tenanta. **Użytkownik należy do wielu tenantów** (relacja M:N, przełączanie aktywnego tenanta). Poświadczenia OAuth per-użytkownik; dane (agenci, konfiguracja, pamięć) tenant-scoped. |
| 16 | Repo i stack | **Monorepo `ai-workspace`**, **layout jak gear-stack**: frontend Vue w roocie + `backend/` FastAPI (mirror = zero zmian ścieżek, łatwy cherry-pick z gear-stacka). Bootstrap: **kopia kodu gear-stack → własne życie** (dywergencja, bez żywej zależności). Bazowy stack: **Postgres + Docker Compose + Python/FastAPI + Vue**. |
| 17 | Baza wektorowa | **pgvector** na MVP (reuse Postgresa; filtrowanie tenant/user/ACL w SQL obok wektorów = wprost *permissions-aware retrieval*). Retrieval za **interfejsem** — swap na **Qdrant** możliwy później przy skali/wydajności. |

## Zakres platformy (rozszerzenie MVP)

MVP to nie pojedynczy agent, lecz **konfigurowalna platforma agentowa**; **GitHub Developer Workspace** jest **pierwszym agentem** na tej platformie (scenariusz Jira 360° był pierwszym, odłożony — patrz North Star). Wymagane zdolności:

- **Chat** (chat-first).
- **Routing agentów** — kierowanie zapytania do właściwego agenta.
- **Memory injection** — wstrzykiwanie pamięci do kontekstu (zakresy do ustalenia: sesja/użytkownik/zespół/organizacja/projekt/agent).
- **Tools injection** — wstrzykiwanie dostępnych narzędzi do kontekstu agenta.
- **Tool search tool** — narzędzie do dynamicznego wyszukiwania narzędzi (gdy zestaw tooli rośnie; w SDK Anthropic: `tool_search_tool_regex/bm25` + `defer_loading`).

### Konfiguracja (hierarchia)

Ustawienia na poziomach: **Aplikacja → Tenant → Zespół → Użytkownik** (docelowo też Agent). Przykładowe parametry:

- dostępne modele + model domyślny,
- limity tokenów,
- czy RAG jest dostępny,
- czy narzędzia (tools) są dostępne,
- itd.

## Research (workstream planu)

Zgodnie z README research jest pierwszym kamieniem milowym — nie kod produkcyjny. Wyniki dokumentowane w repo (`docs/research/...`). Ścieżki (do potwierdzenia/priorytetyzacji):

- **Platformy AI klasy enterprise (comparables)** — jak to robią gotowe produkty; przegląd i wnioski. Propozycja przeglądu: Glean, Microsoft 365 Copilot / Copilot Studio, Google Agentspace, Dust, Writer, Cohere North, ServiceNow AI, Salesforce Agentforce (lista do potwierdzenia).
- **Techniki pracy z AI (z README)** — RAG, Memory Injection, RAPTOR, Graph RAG, Agentic RAG, Hybrid Search, Query/Model/Prompt/Tool Routing, Context Engineering, Prompt Engineering, Long-term Memory, Context Compression/Caching, Semantic search, Knowledge graphs.
- **Frameworki agentowe (porównanie)** — SDK Anthropic (wybrany rdzeń) vs LangGraph vs inne; kiedy co.
- **Źródła wiedzy / „best of AI"** — przegląd wartościowych stron/kolekcji i papers.

**Deliverable:** notatki i podsumowania w `docs/research/`, stopniowo budujące bazę wiedzy projektu.

## Sekwencja budowy (fazy)

Zasada: **pionowy plaster najpierw** (jedna ścieżka end-to-end), potem generalizacja na żywym szkielecie.

- **Faza 0 — Fundament (reuse gear-stack):** auth, użytkownicy, model danych Tenant/Zespół/Użytkownik + izolacja, RBAC, kaskada konfiguracji, plumbing per-user OAuth (magazyn tokenów).
- **Faza 1 — Pionowy plaster:** rdzeń agenta + trace/audyt, czat (reuse Vue `ai`) + SSE, pierwsze integracje MCP → działający agent na wąskim zakresie. Zrealizowane pierwotnie jako **Jira 360° end-to-end** (Jira + GitLab); scenariusz-nośnik odłożony 2026-07-11 (brak dostępu do Jiry), zastąpiony przez **GitHub Developer Workspace** (agent `github-workspace` — GitHub + memory), zbudowany przy tej samej okazji.
- **Faza 1.5 — Design pass:** wdrożenie języka wizualnego z `DESIGN.md` (ChatGPT + Linear) na czat i widok 360° + inline tool steps + bogate bloki dopięte do systemu wizualnego. Jeden spójny przebieg na żywym szkielecie Fazy 1 (żeby nie przerabiać UI dwa razy). Szczegóły: `docs/IMPLEMENTATION_KICKOFF.md`.
- **Faza 2 — Gmail:** własny cienki MCP Gmail (per-user token injection) — ✅ v1 readonly (`gmail_search_messages` / `gmail_list_messages` / `gmail_get_message`). Teams odłożony (brak dostępu). GitHub już gotowy z Fazy 1.
- **Faza 3 — Konfigurowalność: ✅** edytor agentów (tenant owner/admin, `/settings/agents`), abstrakcja routera (`ExplicitAgentRouter`, jawny wybór + picker), tools injection z DB, bogate bloki karty/tabele/**wykresy** (`RichBlock.type="chart"`, konwencja `{"chart": {...}}` w wyniku dowolnego toola). Plan [008](plans/2026-07-23--008--phase-3-agent-editor.md).
- **Faza 4 — Pamięć + RAG:** magazyn wektorowy, memory injection (semantic + tool), RAG. **Fundament ✅** — pamięć (embeddingi + `memory_search`/`memory_save`/`memory_update`) + document RAG (`rag_documents`/`document_chunks`, `rag_search`, ACL tenant/user); patrz plany [005](plans/2026-07-23--005--memory-update.md), [006](plans/2026-07-23--006--rag-retrieval-chunks.md). **Jakość — plan [009](plans/2026-07-25--009--phase-4-retrieval-quality.md):** embeddingi multilingual (PL/EN) + wersjonowanie wektorów, hybrid search (`tsvector` + RRF), reranker za interfejsem, async ingest + załączniki jako źródło, eval (RAGAS offline + DeepEval w CI), UI Knowledge. Podstawa decyzyjna: [research 008](research/2026-07-25--008--embeddings-rag-second-brain.md).
- **Faza 4.5 — Second Brain:** wiki/wiedza — `wiki_pages`/`wiki_links`, toole bibliotekarza (`wiki_ingest`/`wiki_query`/`wiki_lint`), przeglądarka folderów + graf. **pgvector-only** — strony wiki idą tym samym pipeline'em chunków co reszta RAG; **LightRAG: no-go** (research 008 §7). Plan [010](plans/2026-07-25--010--phase-4-5-second-brain-wiki.md). Osobno, bramkowany: memory graph / Graphiti — plan [011](plans/2026-07-25--011--memory-graph-graphiti.md).
- **Faza 5 — Rozszerzenia:** auto-router LLM, tool search, onboarding tenantów (multi-tenancy B), więcej bloków.
- **Faza 6 (kandydat, nierozplanowana) — Zdalne agenty wykonawcze:** orkiestracja agentów kodujących na własnych serwerach użytkownika (np. Claude Code na VPS, wiele projektów) — planowanie/dispatch pracy z poziomu Workspace + tracking statusu. Rozszerza ideę „Control Tower" (patrz Otwarte punkty) o realną egzekucję, nie tylko audyt. Wymaga osobnego researchu/decyzji przed wejściem do sekwencji faz.

## Rozstrzygnięcia

- **Domyślny model (OpenRouter)** (2026-07-11) — **`qwen/qwen3.7-plus`** (`WORKSPACE_DEFAULT_MODEL`). Odbiega od pierwotnej rekomendacji „Gemini Flash" z `docs/research/2026-07-06--005--model-selection.md` — decyzja świadoma, nie A/B; zamyka poprzedni otwarty punkt. App-level allow-lista jest teraz opcjonalna (pusta = brak sufitu, cały katalog OpenRouter — patrz dec. #8 update), więc dotyczy to tylko domyślnie zaznaczonego modelu, nie ograniczonej listy. Skonfigurowane w `backend/app/core/config.py` / `.env.example`.
- **Zmiana scenariusza MVP** (2026-07-11) — Jira 360° odłożony (brak dostępu do Jiry); nowy kierunek: otwarty multi-tool workspace (ChatGPT/Claude-like) z pamięcią i zakresami tenant/team, pierwsza instancja = GitHub Developer Workspace. GitLab i Teams odłożone razem z Jirą (GitLab-owe narzędzie było zależne od klucza Jiry). Gmail zostaje jako aktywny cel Fazy 2. Szczegóły: sekcja „North Star / kontekst" wyżej.
- **Model embeddingów + reranker + Second Brain** (2026-07-25) — zamyka otwarty punkt „Model embeddingów + reranker" oraz `decide-path` z planu [004](plans/2026-07-23--004--second-brain-wiki.md). Podstawa: [research 008](research/2026-07-25--008--embeddings-rag-second-brain.md).
  - **Embeddingi:** migracja z `openai/text-embedding-3-small` na model **multilingual z matryoshką przyciętą do 1536d** (kandydaci: `cohere/embed-v4`, `google/gemini-embedding-001`) — korpus jest dwujęzyczny PL/EN. Wymiar 1536 zostaje, więc migracja to **re-embed, nie zmiana typu kolumny**; dochodzą `embedding_model`/`embedding_version`. Finalny wybór modelu **po pomiarze na złotym zbiorze**, nie z rankingu MTEB.
  - **Retrieval:** hybrid **dense + `tsvector`/`ts_rank_cd` + RRF (`k=60`)** na wbudowanym Postgresie — bez nowych rozszerzeń. ACL nadal w `WHERE` **przed** rankingiem, w obu gałęziach.
  - **Reranker:** `Reranker` **Protocol**, `NoopReranker` domyślnie, hosted API (Cohere/Voyage/Jina) za feature flagiem. VPS nie ma GPU — self-host `bge-reranker-v2-m3` zostaje opcją na później, za tym samym interfejsem.
  - **Eval:** RAGAS offline (strojenie) + **DeepEval jako bramka CI** na złotym zbiorze 100–200 pytań PL/EN. Zamyka punkt „Eval RAG".
  - **Second Brain / LightRAG: NO-GO** — spike odwołany. Wiki dostaje `wiki_pages`/`wiki_links` u nas, a retrieval idzie tym samym pipeline'em chunków co reszta RAG. Powody: duplikacja store'u, ACL w warstwie aplikacji zamiast w SQL, koszt ops. Porty `9621`/`8010` zwolnione.
  - **Memory graph / Graphiti:** **bramkowany**. Etap 1 (facade `MemoryBackend` + flaga `MEMORY_BACKEND`) wchodzi bezwarunkowo; Graphiti dopiero po spike'u z twardymi metrykami (0 wycieków `group_id`, p95 < 3 s, RSS < 2 GB, < 25k tok/rozmowę). No-go jest pełnoprawnym wynikiem. Zawęża wcześniejszy punkt „Graph RAG tylko lazy/incremental" do warstwy **pamięci** — dla wiedzy graf realizują `wiki_links`.
- **Sesje vs runy** (2026-07-09) — **jedna sesja = wiele runów**. Model `chat_sessions` (tenant+user, tytuł z pierwszej wiadomości, `last_message_at`); `agent_runs.session_id` FK. Historia poprzednich tur (para user/assistant, bez replay tool-calli) wstrzykiwana do pętli, aby umożliwić dopytywanie w tym samym kontekście (scenariusz 360°). Nawigacja czatu przełączona na `?session=`. Zamyka P0 #1 z `docs/research/2026-07-08--006--ai-kancelaria-comparison.md`.

## Otwarte punkty (do ustalenia)
- **Zdalne agenty wykonawcze** (2026-07-11, nowy pomysł) — Workspace jako panel do planowania/dispatchowania pracy dla agentów kodujących uruchomionych na własnej infrastrukturze użytkownika (np. Claude Code na serwerze OVH, wiele projektów), z trackingiem statusu. Nie doprecyzowane: model integracji (nowy typ „toola"/konektora vs osobna warstwa orkiestracji), auth do zdalnych środowisk, relacja do audytu Task/Run (dec. #13) i do przyszłego „Control Tower" (patrz niżej). Kandyduje na Fazę 6 — wymaga osobnego researchu przed wejściem do sekwencji.

### Z researchu (patrz `docs/research/2026-07-04--000--implications.md`)

- **Permissions-aware retrieval** — ✅ **zrealizowane** (plan 006): ACL `tenant_id`+`user_id` w `WHERE` przed `ORDER BY <=>`, z testami izolacji. Plan 009 utrzymuje tę własność w **obu** gałęziach hybrydy; reranker działa wyłącznie na przefiltrowanym zbiorze.
- **Warstwa modelu pod wielu dostawców** — mimo startu na SDK Anthropic zaprojektować abstrakcję LLM (trend „hub wielu modeli"); spójne z „dostępne modele" w konfiguracji.
- **Pamięć jako lifecycle** — ADD/UPDATE/DELETE ✅ (plany 005/006). Dedupe → plan 009 (`memory-dedupe`), facade pod podmianę backendu → plan 011. **Nadal open:** polityka **decay/konsolidacji** — do rozstrzygnięcia po bramce Graphiti (temporalność faktów może ją zastąpić; przy no-go trzeba ją zbudować w pgvectorze).
- **Guardrails jako przyszłe pole agenta** — step limiters, output validators (poza MVP, ale zostawić miejsce w schemacie agenta).
- **Admin „Control Tower"** — przyszły panel: inventory agentów + audyt + polityki (governance).
- **Eval RAG** — ✅ **rozplanowane** (plan 009, todo `eval-harness`): RAGAS offline + DeepEval jako bramka CI, złoty zbiór 100–200 pytań PL/EN w repo. Metryki: faithfulness, answer relevancy, context precision, context recall — czytane jako panel.
- **Graph RAG tylko lazy/incremental** — ✅ **zawężone** (2026-07-25): dla **wiedzy** graf realizują `wiki_links` u nas (plan 010), pełny GraphRAG i LightRAG odrzucone. Dla **pamięci** graf = Graphiti, bramkowany (plan 011).
