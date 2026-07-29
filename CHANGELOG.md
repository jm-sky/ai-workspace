# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [2.50.0] - 2026-07-29

### Added
- **Wiki (Second Brain)**: `wiki` module — `wiki_pages`/`wiki_links` (migration 066), folder CRUD, `[[wikilinks]]`, librarian ingest, `wiki_query`/`wiki_lint`, graph view, REST API + agent tools; UI with folder tree, sorting, bulk delete/search/purge, resizable detail panel, expand dialog, link picker, help tooltips (Faza 4.5, plan 010)
- **Wiki**: entity-page merge on ingest and auto-wikilink of known slugs
- **Memory**: `MemoryBackend` facade (`pgvector`|`graphiti`), Graphiti spike scaffolding + gate metrics (plan 011); `memory_save` near-duplicate dedupe
- **RAG**: embedding versioning, hybrid dense+lexical (RRF), pluggable reranker, structure-aware chunker, async ingest, attachment ingest, `source_types` filter; Knowledge page; `cli rag reembed`; eval harness (Faza 4, plan 009)
- **Agent**: chart rich block (Unovis); `web_search`/`web_fetch` with hybrid `server`/`local` mode and sources block (plan 013)
- **Usage**: OpenRouter cost metering, period totals, workspace caps, web-search quotas, `GET /usage/summary`, billing limits + Usage card (plans 014/015)
- **Auth**: refresh tokens in HttpOnly cookies with silent bootstrap refresh
- **Security**: double-submit CSRF (`csrf_token` cookie + `X-CSRF-Token`)

### Changed
- Docker Compose: remove wrapper; stop overriding `DATABASE_URL`/`REDIS_URL` from host defaults
- Chat/workspace layout spacing; model picker shows name only; mobile toolbar stays in chat window
- Vite default port / `VITE_PORT` alignment

### Fixed
- Chat SSE `fetch` now sends CSRF header (production `/agent/chat/stream` 403)
- Wiki incoming links show clickable source pages
- CSRF middleware no longer double-issues `csrf_token` cookie
- 2FA backup codes normalized before mark-used
- Auth: tenant/team models imported for SQLAlchemy metadata; CLI change-password in interactive menu
- Deploy: project-local pnpm store, GHA pull from `main`, sequential type-check/build, ownership wipe
- Lint: backend ruff + frontend ESLint cleanups

### Security
- Cookie-authenticated mutations protected by CSRF
- Refresh tokens no longer stored in localStorage/JSON bodies

---

## [2.49.0] - 2026-07-23

### Added
- **Agents**: tenant-scoped agent definitions with CRUD
- **Gmail**: readonly Gmail MCP + OAuth integration
- **Chat**: image attachments (vision content parts); text/PDF extraction into model context; orphan attachment purge counted in storage usage
- **RAG**: retrieval-augmented generation features and memory update tools
- **Tools**: tool search with dynamic loading of deferred tools
- **Health**: `GET /api/health/details` for Ops Monitor
- **CLI**: `users change-password`
- Plans/docs for Second Brain wiki and memory

### Changed
- Docker Compose moved to repo root; shared compose auto-detect; footer GitHub from app config
- Default workspace model: Gemini 2.5 Flash Lite; chat UI and design-token polish

### Fixed
- Auth: unified OAuth callback `/auth/callback/:provider`; `tv`/`jti` on 2FA login/refresh; TOTP `verified`/`method`
- Deploy: remove nested step numbering from frontend sub-script
- WebAuthn RP/origin fallback and shared UX a11y backport
- Project naming casing standardized to `ai-workspace`

### Security
- Path-safe storage and OAuth state cleanup
- OAuth session tracking, 2FA challenge, CSRF state store
- Rate limiting, admin auth, and WebAuthn login hardening
- pnpm overrides for Dependabot security alerts
