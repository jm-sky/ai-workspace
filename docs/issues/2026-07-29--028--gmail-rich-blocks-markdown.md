# Issue 028 — Gmail rich blocks + styl Markdown w czacie

**Data:** 2026-07-29  
**Status:** `done` (2026-07-29)  
**Obszar:** backend (`agent`), frontend (`workspace`)  
**Powiązane:** [#019](./2026-07-09--019--design-faza-1-5-rich-blocks.md), Faza 2 Gmail (`MVP.md`)

## Problem

Odpowiedzi Gmail lądowały wyłącznie jako Markdown (tabele Pole/Wartość). Klasy `prose` w `AgentMarkdown` były martwe (brak `@tailwindcss/typography`).

## Decyzja

Bez nowego typu bloku `email`. Reuse `card` / `table` jak GitHub:

- `gmail_get_message` → card (snippet jako quote)
- `gmail_search_messages` / `gmail_list_messages` → table (gdy brak get)
- Prompt: nie dublować Od/Do/Temat w Markdown
- `AgentMarkdown`: klasy `.agent-md` zamiast `prose*`

## Implementacja

- `_gmail_blocks` w `agent_loop.py` + testy
- `AgentRichBlocks.vue` — quote dla `snippet`/`fragment`
- `AgentMarkdown.vue` + `.agent-md` w `style.css`
- Prompt `github_workspace.py`
- Dopisek w `MVP.md` (Faza 2)
