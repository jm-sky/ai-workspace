# Issues

Błędy, usprawnienia i dług techniczny — elementy do naprawy.

## Status values

`todo` · `planned` · `in progress` · `done` · `verification needed`

## Priorytety (kolejka 2026-07-20)

Ustalenie po re-weryfikacji vs ai-kancelaria (po `git pull`). Memory injection **już mamy** (i Kancelaria też — fakty inject #046). Poniżej kolejka implementacji:

| P | ID | Temat | Uwagi |
|---|----|-------|-------|
| **P0** | [#022](2026-07-20--022--tool-search.md) | **Tool search** | `done` — core + meta *tool search*; poniżej progu → wszystkie |
| **P0** | [#023](2026-07-20--023--agent-routing.md) | **Agent routing** | `done` — jawny wybór + 3 agenci; auto-router LLM → Faza 5 |
| **P1** | [#024](2026-07-20--024--chat-attachments-vision.md) | **Załączniki + vision** | Plan [#020](2026-07-09--020--chat-attachments-plan.md) / [plan 002](../plans/2026-07-09--002--chat-attachments.md); wzorzec Kancelarii #012 |
| P2 | [#016](2026-07-10--016--model-picker-performance.md) | Model picker performance | `done` |
| P3 | [#005](2026-07-07--005--guest-layout-nav-z-index.md) | Guest layout z-index | `done` |

**Kolejność pracy:** #022 → #023 (routing korzysta z profili tooli / search) → #024. Ewentualnie #024 równolegle, jeśli wolimy najpierw dogfooding UX.

## Index

| ID | File | Summary | Status |
|----|------|---------|--------|
| 001 | [2026-07-06--001--cli-users-list-wide.md](2026-07-06--001--cli-users-list-wide.md) | CLI `users list` — `--wide` jak ops-monitor | `done` |
| 002 | [2026-07-06--002--cli-users-delete-soft-hard.md](2026-07-06--002--cli-users-delete-soft-hard.md) | CLI `users delete` — soft/hard jak family-recipes | `done` |
| 003 | [2026-07-07--003--oauth-facebook-button-visibility.md](2026-07-07--003--oauth-facebook-button-visibility.md) | OAuth Facebook — przycisk widoczny tylko przy własnej konfiguracji | `done` |
| 004 | [2026-07-07--004--oauth-github-login.md](2026-07-07--004--oauth-github-login.md) | OAuth GitHub — logowanie (źródło backportu) | `done` |
| 005 | [2026-07-07--005--guest-layout-nav-z-index.md](2026-07-07--005--guest-layout-nav-z-index.md) | GuestLayout — pasek locale/dark mode pod logo (z-index) | `done` |
| 006 | [2026-07-09--006--pytest-jsonb-sqlite-compile-error.md](2026-07-09--006--pytest-jsonb-sqlite-compile-error.md) | pytest — JSONB nie kompiluje się na SQLite (dług test-infra) | `done` |
| 007 | [2026-07-09--007--audit-sheet-no-padding.md](2026-07-09--007--audit-sheet-no-padding.md) | Audyt/Trace (sheet) — brak paddingu treści | `done` |
| 008 | [2026-07-09--008--memory-page-no-canvas-background.md](2026-07-09--008--memory-page-no-canvas-background.md) | Strona Pamięci — brak tła (canvas) | `done` |
| 009 | [2026-07-09--009--multi-turn-chat-sessions-kickoff.md](2026-07-09--009--multi-turn-chat-sessions-kickoff.md) | MVP kickoff — sesje wieloturowe + kontekst użytkownika | `done` |
| 010 | [2026-07-09--010--two-tier-agent-audit.md](2026-07-09--010--two-tier-agent-audit.md) | Audyt dwuwarstwowy agenta (redacted + admin raw) | `done` |
| 011 | [2026-07-09--011--source-routing-guard.md](2026-07-09--011--source-routing-guard.md) | Source routing guard — ochrona kontekstu źródeł | `done` |
| 012 | [2026-07-09--012--design-faza-1-5-chat-tokens.md](2026-07-09--012--design-faza-1-5-chat-tokens.md) | Faza 1.5 krok 1 — tokeny powierzchni, Inter | `done` |
| 013 | [2026-07-09--013--github-oauth-token-refresh.md](2026-07-09--013--github-oauth-token-refresh.md) | GitHub OAuth — automatyczne odświeżanie tokena | `done` |
| 014 | [2026-07-10--014--model-picker-combobox-cards.md](2026-07-10--014--model-picker-combobox-cards.md) | Model picker — combobox z kartami (moc, cena) | `done` |
| 015 | [2026-07-10--015--openrouter-model-browser.md](2026-07-10--015--openrouter-model-browser.md) | Przeglądarka modeli OpenRouter + filtry | `done` |
| 016 | [2026-07-10--016--model-picker-performance.md](2026-07-10--016--model-picker-performance.md) | Model picker — wydajność otwarcia (lazy load) | `done` |
| 017 | [2026-07-09--017--design-faza-1-5-chat-shell.md](2026-07-09--017--design-faza-1-5-chat-shell.md) | Faza 1.5 krok 2 — shell czatu | `done` |
| 018 | [2026-07-09--018--design-faza-1-5-tool-steps.md](2026-07-09--018--design-faza-1-5-tool-steps.md) | Faza 1.5 krok 3 — inline tool steps | `done` |
| 019 | [2026-07-09--019--design-faza-1-5-rich-blocks.md](2026-07-09--019--design-faza-1-5-rich-blocks.md) | Faza 1.5 krok 4 — rich blocks | `done` |
| 020 | [2026-07-09--020--chat-attachments-plan.md](2026-07-09--020--chat-attachments-plan.md) | Plan załączników w czacie (attachments) | `done` |
| 021 | [2026-07-08--021--backport-2fa-shared-core.md](2026-07-08--021--backport-2fa-shared-core.md) | Backport 2FA i shared-core UX z gear-stack | `done` |
| 022 | [2026-07-20--022--tool-search.md](2026-07-20--022--tool-search.md) | Tool search — core + profil agenta / próg „wszystkie” | `done` |
| 023 | [2026-07-20--023--agent-routing.md](2026-07-20--023--agent-routing.md) | Agent routing — auto-router + 2–3 agenci | `done` |
| 024 | [2026-07-20--024--chat-attachments-vision.md](2026-07-20--024--chat-attachments-vision.md) | Załączniki w czacie + vision (OpenRouter) | `planned` |
| 025 | [2026-07-20--025--backport-shared-core-security-fixes.md](2026-07-20--025--backport-shared-core-security-fixes.md) | Backport: rate limiting, admin auth bypass, WebAuthn login (shared core) | `done` |
| 026 | [2026-07-22--026--oauth-session-and-state-backport.md](2026-07-22--026--oauth-session-and-state-backport.md) | Backport: OAuth session/2FA parity + CSRF state store (gear-stack 036+037) | `done` |
| 027 | [2026-07-11--027--chat-tool-memory-step-disappears.md](2026-07-11--027--chat-tool-memory-step-disappears.md) | Chat — krok narzędzia (memory) znika po zakończeniu runu | `todo` |
| 028 | [2026-07-29--028--gmail-rich-blocks-markdown.md](2026-07-29--028--gmail-rich-blocks-markdown.md) | Gmail → rich blocks (card/table) + styl Markdown w czacie | `done` |

When adding a new issue: pick next `NNN`, create `YYYY-MM-DD--NNN--slug.md`, add a row here.
