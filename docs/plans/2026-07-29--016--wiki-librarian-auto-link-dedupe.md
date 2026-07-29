# Plan 016 — Wiki librarian: auto-link + dedupe przy wiki_ingest

**Status:** `done`
**Data:** 2026-07-29
**Obszar:** backend (`wiki`, `agent/tools`)
**Parent:** [010 Second Brain](2026-07-25--010--phase-4-5-second-brain-wiki.md)

## Cel

Przy `wiki_ingest` bibliotekarz:

1. **Dedupe** encji/konceptów — merge do aktywnej strony o tym samym slug w tym samym folderze (zamiast `slug-2`).
2. **Auto-wikilink** znanych stron (entities/concepts/summaries) w body summary i rippled pages.

## Decyzje

| # | Temat | Decyzja |
|---|-------|---------|
| 1 | Merge scope | Tylko ten sam folder (`entities`/`concepts`). Cross-folder → tylko `[[slug]]`, bez merge treści |
| 2 | Raw/Summary | Nadal zawsze create (`-2` OK) |
| 3 | RIPPLE_MAX_PAGES | Liczy tylko nowo utworzone rippled pages; merge nie zużywa limitu |
| 4 | Auto-link katalog | Active entities + concepts + summaries; priorytet slug: entities > concepts > summaries |
| 5 | Limity | min match ≥ 4, max 20/stronę, longest-first, bez code/`[[…]]`/self-link |
| 6 | API | Additive: `mergedPages`, `autoLinksApplied` |

## Poza zakresem

LLM linking, backfill/`relink=true`, migracje DB, update MVP.md bez osobnego potwierdzenia.
