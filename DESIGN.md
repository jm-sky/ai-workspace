# AI Workspace Design Brief (draft)

## Product concept

Application type:
- ChatGPT-like AI application
- Workspace-oriented, not only a chat list
- Conversation is the primary interaction model

## UX direction

Base inspiration:
- ChatGPT

Use:
- ChatGPT UX as a strong starting point
- conversation-first design
- chat history
- streaming responses
- AI interaction patterns

Approach:
- copying proven ChatGPT patterns is acceptable
- improve mainly the visual layer and workspace capabilities

## Visual references

Materiały z refero.design: [`docs/design/README.md`](docs/design/README.md).

### ChatGPT
Use for:
- overall application structure
- conversation experience
- navigation patterns
- chat workflow
- input/composer patterns
- AI interaction model

Refero: [`docs/design/refero/chatgpt/`](docs/design/refero/chatgpt/) (`DESIGN.md`, `tailwind.css`)

### Linear
Use for:
- clean interface
- excellent spacing
- minimalism
- premium SaaS feeling
- attention to small details

Refero: [`docs/design/refero/linear/`](docs/design/refero/linear/) (`DESIGN.md`, `tailwind.css`)

> **AuthKit porzucony jako referencja** (2026-07-11) — nigdy nie zebrano dla niego materiału w `docs/design/refero/`. Interesujące elementy (subtelne efekty świetlne / glow) są już objęte przez ChatGPT + § „Overall visual style" niżej.

## Reference-driven implementation process

Before implementation:

- use design references from refero.design
- analyze selected reference projects and extract:
  - DESIGN.md guidelines
  - Tailwind v4 configuration
  - design tokens
  - typography rules
  - spacing system
  - component patterns
  - visual effects
  - screenshots and UI examples

Important:
- references should be treated as design input, not copied blindly
- combine selected patterns into one coherent design system

Before coding:
- prepare a design implementation plan
- present the plan to the user
- get confirmation before starting implementation

## Overall visual style

Direction:
- premium + modern AI

Balance:
- between subtle premium and modern AI aesthetics
- avoid excessive effects

Preferred effects:
- soft shadows
- backdrop blur
- subtle gradients
- occasional animated borders / glow effects

Avoid:
- flashy neon
- gaming-style AI visuals
- distracting animations

## AI presence

The interface should clearly communicate that this is an AI product.

Possible elements:
- AI activity states
- generation indicators
- intelligent UI components
- model/tool awareness

Principle:
- AI should feel alive and present
- UI should not become distracting

## Themes

Support:
- dark mode
- light mode

Both modes are first-class:
- equally polished
- not one being an afterthought

## Composer / Input

Direction:
- premium AI composer

Characteristics:
- based on ChatGPT input experience
- improved visual quality
- floating panel style
- possible glass/blur effect
- high-quality spacing and interaction
- **plus (`+`) menu** (ChatGPT-like): primary entry for attachments and soft context sources — Add photos/files, connected integrations (GitHub, Gmail), Knowledge hint, link to more integrations. Not a full apps marketplace in v1; Atlassian/Jira stay out of scope while OAuth is deferred.

Avoid:
- excessive decoration
- paperclip-only shortcut that hides source options

## Workspace

Direction:
- workspace model instead of simple chats

Open question:
- define whether workspace is closer to:
  - ChatGPT Projects
  - AI IDE/work environment
  - Notion-style knowledge workspace
  - hybrid

## Animations

Preferred:
- subtle micro-interactions

Examples:
- hover states
- focus states
- smooth transitions
- element appearance

Avoid:
- heavy motion
- constant animations
- distracting effects