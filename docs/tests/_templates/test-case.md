---
id: PRJ-T-N
type: test-case
title: ""
status: draft
owner: ""
priority: must
tags: []
level: ui
links:
  - type: verifies
    to: PRJ-N
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# PRJ-T-N-tc-slug

Каталог: `docs/tests/cases/`. Не класть в дерево эпик → стори → SR и не класть в папку сьюита.

Канонический ID: `PRJ-T-<n>` (реестр [`../_registry.md`](../_registry.md)).

`status`: `draft` | `review` | `approved` | `automated` | `obsolete`

`level`: `unit` | `api` | `ui` | `e2e`

Покрытие начинается со статуса `approved` или `automated`. `verifies` только на `system-requirement` или `nfr` (`PRJ-<n>`). Между кейсами допустим `depends-on` (`PRJ-T-<n>`).

## Цель

Что именно подтверждаем.

## Предусловия

- …

## Шаги

1. …
2. …

## Ожидаемый результат

- …
