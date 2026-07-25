# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Agent**: chart rich block (`RichBlock.type="chart"`) alongside card/table/markdown — any tool can opt in via a `{"chart": {...}}` convention in its result; rendered with Unovis (Faza 3, plan 008 — now `done`)
- **RAG**: embedding versioning (`embedding_model`/`embedding_version`), batched/retried/cached `EmbeddingService`, hybrid dense+lexical search (RRF), pluggable `Reranker` (Noop default, Hosted behind a flag), structure-aware markdown chunker, async ingest (`POST /rag/documents` → 202/pending, background embedding), attachment ingest (`POST /rag/documents/from-attachment`)
- **Memory**: `memory_save` dedupes near-identical content (`AI_MEMORY_DEDUPE_THRESHOLD`), returning `duplicateOf` instead of writing a duplicate row
- **CLI**: `python -m cli rag reembed [--batch] [--dry-run]` — resumable re-embed after a model change
- **Workspace**: Knowledge page (`/workspace/knowledge`) — list/add/preview/delete RAG documents with live status
- **Evals**: `backend/evals/rag/` — retrieval-quality harness (hit rate, MRR, context precision/recall) against a 34-question PL/EN golden set (Faza 4, plan 009 — infrastructure done, model choice pending a live eval run)

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
