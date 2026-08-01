# Issue 029 — Wiki: RWD / czytelność na mobile

**Data:** 2026-07-29  
**Status:** `todo`  
**Obszar:** frontend (`workspace` / Wiki)  
**Powiązane:** Faza 4.5 Second Brain (`MVP.md`), plan [010](../plans/2026-07-25--010--phase-4-5-second-brain-wiki.md), `DESIGN.md`

## Problem

Widok Wiki (`/workspace/wiki`) jest nieczytelny na mobile: layout (foldery / lista / podgląd / graf) nie składa się sensownie na wąskim ekranie — treść, nawigacja i panele konkurują o miejsce albo się ściskają.

## Oczekiwanie

- Jedna czytelna ścieżka na telefonie (np. stack / drawer / bottom sheet zamiast 2–3 kolumn naraz)
- Lista stron i podgląd Markdown używalne bez zoomu / poziomego scrolla
- Graf: sensowny fallback na mobile (ukryty, pełnoekranowy, lub uproszczony)
- Zgodność z tokenami Fazy 1.5 (`DESIGN.md`)

## Notatki

Zgłoszone przy dogfoodingu ingestu `docs/.temp/` — UI desktop działa, mobile nie.
