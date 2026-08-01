# Issue 030 — Brak przycisku "copy to clipboard" na blokach code/quote/pre w odpowiedziach LLM

**Data:** 2026-08-01  
**Status:** `todo`  
**Obszar:** frontend (`workspace` / czat, Markdown rendering)  
**Powiązane:** `src/modules/workspace/components/AgentMarkdown.vue`, `src/shared/utils/markdownPostProcess.ts`

## Problem

Odpowiedzi LLM renderowane przez `AgentMarkdown.vue` zawierają bloki `<pre>`/`<code>` i `<blockquote>`, ale nie ma żadnego sposobu skopiowania ich zawartości poza ręcznym zaznaczeniem tekstu myszką. Konkurencja (ChatGPT, Claude.ai, Claude Code) ma mały icon-only przycisk "copy" w rogu każdego takiego bloku.

## Oczekiwanie

- Mały przycisk icon-only (np. `Copy`/`Check` z lucide, toggle po kliknięciu na 1-2s) w prawym górnym rogu każdego bloku kodu, cytatu (`blockquote`) i `pre`.
- Kopiuje surową treść bloku (bez dodanego formatowania/HTML), przez `navigator.clipboard.writeText`.
- Widoczny na hover (desktop) / zawsze widoczny (mobile, brak hover).
- Spójny z tokenami Fazy 1.5 (`DESIGN.md`).

## Notatki

Zgłoszone przez użytkownika 2026-08-01 przy normalnym korzystaniu z czatu.
