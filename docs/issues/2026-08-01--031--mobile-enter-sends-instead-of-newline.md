# Issue 031 — Enter na telefonie wysyła wiadomość zamiast nowego wiersza

**Data:** 2026-08-01  
**Status:** `todo`  
**Obszar:** frontend (`workspace` / `ChatComposer.vue`)  
**Powiązane:** `src/modules/workspace/components/ChatComposer.vue:75-80` (`handleKeydown`)

## Problem

`handleKeydown` w `ChatComposer.vue` wysyła wiadomość na sam `Enter` (chyba że wciśnięty `Shift`) niezależnie od urządzenia:

```ts
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
  }
}
```

Na telefonie klawiatura ekranowa zwykle nie ma wygodnego `Shift+Enter`, więc każdy Enter = wysłana wiadomość. Użytkownik chciał nowy wiersz, dostał wysłaną (niedokończoną) wiadomość. Claude Code i ChatGPT (aplikacja mobilna/web na wąskim viewport) traktują Enter jako nowy wiersz na mobile — wysyłka tylko przez przycisk Send.

## Oczekiwanie

- Na viewportach mobilnych (albo ogólniej: gdy nie ma fizycznej klawiatury / touch-primary) `Enter` wstawia nowy wiersz, nie wysyła.
- Wysyłka na mobile wyłącznie przez przycisk Send.
- Desktop: zachowanie bez zmian (`Enter` = wyślij, `Shift+Enter` = nowy wiersz) — chyba że po dyskusji zdecydujemy inaczej.
- Detekcja: rozważyć `matchMedia('(pointer: coarse)')` lub istniejący breakpoint z `DESIGN.md`, nie tylko szerokość ekranu (tablet z klawiaturą fizyczną).

## Notatki

Zgłoszone przez użytkownika 2026-08-01, przy pisaniu z telefonu.
