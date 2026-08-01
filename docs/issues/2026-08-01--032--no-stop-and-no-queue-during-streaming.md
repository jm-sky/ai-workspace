# Issue 032 — Brak przycisku Stop i nie da się wysłać kolejnej wiadomości podczas myślenia LLM

**Data:** 2026-08-01  
**Status:** `todo`  
**Obszar:** frontend (`workspace` / czat), `useAgentChat.ts`, `agentApiService.ts`  
**Powiązane:** `src/modules/workspace/composables/useAgentChat.ts:90-97` (`sendMessage` early-return na `isLoading`), `src/modules/workspace/services/agentApiService.ts:79` (`fetch` streamu bez `AbortController`/`signal`)

## Problem

1. **Brak Stop.** `streamAgentChat` w `agentApiService.ts` odpala `fetch(...)` do `/agent/chat/stream` bez żadnego `AbortController`/`signal` — nie ma technicznej możliwości przerwania trwającego streamu z UI. Nie ma też przycisku Stop w `ChatComposer`/`WorkspaceChatPage`.
2. **Brak wysyłki w trakcie.** `sendMessage` w `useAgentChat.ts` ma twardy early-return `if (... || isLoading.value) return undefined` — więc nie da się ani wysłać kolejnej wiadomości, ani jej zakolejkować, dopóki poprzedni run się nie zakończy.

## Do ustalenia (user, przed implementacją)

- **Stop — jasne, robimy:** dodać `AbortController` do `streamAgentChat`, przycisk Stop widoczny gdy `isStreaming`, backend musi obsłużyć zerwane połączenie (czy dotychczasowy częściowy output zostaje zapisany jako run?).
- **Wysyłka w trakcie myślenia — do decyzji, dwie opcje:**
  - **Queue:** wiadomość ląduje w kolejce i wysyła się automatycznie po zakończeniu bieżącego runu (jak ChatGPT — input nie blokuje się, ale odpowiedź przychodzi sekwencyjnie).
  - **Instant/interrupt:** wysłanie nowej wiadomości od razu przerywa bieżący stream (jak Stop + Send w jednym), tylko jeden aktywny run naraz.
  - Trzeba zdecydować, zanim zacznie się implementacja — wpływa na kontrakt backendu (czy `/agent/chat/stream` musi wspierać przerwanie w locie, czy tylko klient przestaje słuchać).

## Notatki

Zgłoszone przez użytkownika 2026-08-01. Techniczna baza: brak `signal` w `fetch` (agentApiService.ts:79) i brak jakiegokolwiek queue w `useAgentChat.ts` — to nie jest tylko UI, wymaga zmiany w warstwie stream/composable, ewentualnie API kontraktu z backendem.
