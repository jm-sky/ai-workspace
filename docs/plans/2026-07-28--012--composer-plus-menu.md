# Plan 012 — Composer „+” menu (ChatGPT-style)

**Status:** `done`  
**Data:** 2026-07-28  
**Obszar:** frontend (`workspace`) + soft context w wiadomości agenta (bez nowego storage)

## Cel

Zamienić paperclip w composerze na menu **`+`** w stylu ChatGPT:

- Dodaj zdjęcia i pliki (istniejący upload)
- GitHub / Gmail — soft context gdy połączone, OAuth connect gdy nie
- Knowledge — soft hint (bez doc pickera)
- Więcej… → Settings → Integrations

**Poza zakresem v1:** Atlassian, prawdziwe pickery repo/mail/doc, first-class context attachments.

## Implementacja

| Element | Ścieżka |
|---------|---------|
| Plus menu | `ChatComposerPlusMenu.vue` |
| Context chip | `ChatContextChip.vue` |
| State | `useComposerContextHints.ts` |
| Dyrektywy → agent | `contextHints.ts` → prefix w `sendMessage` |
| i18n | `workspace.composer.plus.*` |

Outbound: dyrektywy EN prependowane do `message` w streamie; UI pokazuje czysty tekst + chipy.
