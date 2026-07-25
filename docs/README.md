# Dokumentacja AI Workspace — indeks

Punkt wejścia do planu MVP i wyników researchu. Plan MVP jest ustalony, research (runda 1) zrobiony. **Krok 0 (bootstrap) — ✅** (2026-07-05). **Faza 0 (fundament) — ✅** (2026-07-07). **Faza 1 (Jira 360° end-to-end) — ✅** (2026-07-09). **Faza 1.5 (design pass) — 🔄 w toku.** Caddy + DNS na `ai-workspace.dev-made.it` — ✅ wdrożone na VPS.

## Nawigacja

### Wizja
- [`../README.md`](../README.md) — wizja produktu (AI Workspace / AI Operating System).

### Plan MVP
- [`MVP.md`](MVP.md) — **główny dokument planu**: 17 decyzji architektonicznych, schemat agenta, sekwencja budowy (fazy) i otwarte punkty. Zacznij tutaj.
- [`IMPLEMENTATION_KICKOFF.md`](IMPLEMENTATION_KICKOFF.md) — **prompt startowy** dla sesji Claude Code (Opus) rozpoczynającej implementację (bootstrap + Faza 0/1).

### Design
- [`../DESIGN.md`](../DESIGN.md) — **brief wizualny** (ChatGPT + Linear jako referencje), zasady implementacji, aktualny dla Fazy 1.5 (design pass, 🔄 w toku).
- [`design/README.md`](design/README.md) — zebrane materiały refero.design (`chatgpt/`, `linear/`: `DESIGN.md` + `tailwind.css`).

### Katalogi robocze
- [`issues/README.md`](issues/README.md) — błędy, usprawnienia, dług techniczny
- [`reviews/README.md`](reviews/README.md) — przeglądy (security, jakość kodu, UX, performance)
- [`research/README.md`](research/README.md) — analizy, spike'i, porównania przed decyzją
- [`plans/README.md`](plans/README.md) — plany implementacji funkcji i większych zmian
- [`deployment/README.md`](deployment/README.md) — wdrożenie na VPS (Caddy, domeny, deploy)

### Deployment
- [`deployment/README.md`](deployment/README.md) — indeks: domeny `ai-workspace.dev-made.it` / `api.ai-workspace.dev-made.it`, porty, ścieżki na serwerze
- [`deployment/CADDY_DEPLOYMENT.md`](deployment/CADDY_DEPLOYMENT.md) — instrukcja wdrożenia Caddy
- [`deployment/ai-workspace.caddy`](deployment/ai-workspace.caddy) — plik konfiguracyjny vhostów (kopiowany do `/etc/caddy/sites-available/`)

### Research (`research/`)
Indeks: [`research/README.md`](research/README.md). Skrót:
- [`research/2026-07-04--000--implications.md`](research/2026-07-04--000--implications.md) — **synteza: research → wnioski dla planu** (czytać razem z `MVP.md`).
- [`research/2026-07-04--001--enterprise-comparables.md`](research/2026-07-04--001--enterprise-comparables.md) — 8 platform enterprise.
- [`research/2026-07-04--002--ai-techniques.md`](research/2026-07-04--002--ai-techniques.md) — techniki AI: RAG, routing, context engineering, pamięć.
- [`research/2026-07-04--003--agent-frameworks.md`](research/2026-07-04--003--agent-frameworks.md) — frameworki agentowe: SDK Anthropic vs LangGraph.
- [`research/2026-07-04--004--knowledge-sources.md`](research/2026-07-04--004--knowledge-sources.md) — kuratorowana baza źródeł / „best of AI".
- [`research/2026-07-06--005--model-selection.md`](research/2026-07-06--005--model-selection.md) — wybór domyślnego modelu na OpenRouter (Gemini Flash).
- [`research/2026-07-08--006--ai-kancelaria-comparison.md`](research/2026-07-08--006--ai-kancelaria-comparison.md) — porównanie z repo siostrzanym ai-kancelaria: co warto przenieść.
- [`research/2026-07-10--007--chatgpt-settings-reference.md`](research/2026-07-10--007--chatgpt-settings-reference.md) — referencja UX ustawień aplikacji AI (ChatGPT) + architektura pamięci wielopoziomowej.
- [`research/2026-07-25--008--embeddings-rag-second-brain.md`](research/2026-07-25--008--embeddings-rag-second-brain.md) — **Faza 4**: embeddingi multilingual/PL, chunking, hybrid + reranker, eval RAG, memory graph, Second Brain (LightRAG odrzucony).

## Skrót decyzji (z `MVP.md`)

| # | Obszar | Decyzja |
|---|--------|---------|
| 1–2 | Rdzeń agenta | Agentowy; **OpenRouter (OpenAI-compatible) + własna pętla tool-calling** + narzędzia jako **MCP**; model domyślny TBD (cost-sensitive); bez LiteLLM; LangGraph przy multi-agent |
| 3 | Auth | **Per-user OAuth** (Jira, GitLab, Google, Microsoft) |
| 4 | Backend | **Reuse rdzenia gear-stack** (FastAPI, users, OAuth, RBAC, multi-tenancy) |
| 5 | Integracje | **Własne cienkie serwery MCP** per dostawca |
| 6–7 | UI | **Chat-first**; **reuse Vue z gear-stack** |
| 8 | Konfiguracja | **Kaskada z sufitami/allow-listami** (App→Tenant→Zespół→Użytkownik) |
| 9–11 | Agenci | Routing **hybrydowy** (start jawny wybór); **edytor agentów dla adminów**; schemat agenta |
| 12 | Pamięć | Zakresy sesja/użytkownik/agent; **RAG-owa** (semantic + narzędzie na żądanie) |
| 13 | Audyt | **Lekki Task/Run + trace**; audyt w czacie z kopiowaniem runu/kroku |
| 14 | Wyjście | **SSE** + Markdown + bogate bloki (karty/tabele/wykresy) |
| 15 | Multi-tenancy | **A teraz** (tenant-aware), **B wkrótce**; user w wielu tenantach (M:N) |
| 16 | Repo i stack | **Monorepo**, layout jak gear-stack (frontend w roocie + `backend/`); kopia gear-stack → własne życie; Postgres/Docker |
| 17 | Baza wektorowa | **pgvector** (reuse Postgresa, permissions-aware filter w SQL); swap na Qdrant za interfejsem |

Scenariusz MVP (od 2026-07-11): **otwarty multi-tool workspace** (ChatGPT/Claude-like) z pamięcią i zakresami tenant/team, bez sztywnego pipeline'u. Pierwsza instancja: **GitHub Developer Workspace**. Jira/GitLab/Teams odłożone (brak dostępu); Gmail zostaje jako cel Fazy 2. Pierwotny scenariusz „Jira → Klient → fan-out GitLab/Gmail/Teams" — zapis historyczny w `MVP.md`.

## Zasady dla dokumentacji
- Konwencja plików w `issues/`, `reviews/`, `research/`, `plans/`: `YYYY-MM-DD--NNN--slug.md` (`NNN` — trzycyfrowy numer w obrębie katalogu).
- Nowe wpisy: utwórz plik, dodaj wiersz w `README.md` danego katalogu.
- Decyzje i otwarte punkty aktualizować w `MVP.md`.
