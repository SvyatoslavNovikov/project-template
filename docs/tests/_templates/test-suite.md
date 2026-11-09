---
id: PRJ-T-N
type: test-suite
title: ""
status: draft
owner: ""
priority: should
tags: []
links:
  - type: contains
    to: PRJ-T-N
  - type: relates-to
    to: PRJ-N
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# PRJ-T-N-ts-slug

Каталог: `docs/tests/suites/`. Сьюит не владеет кейсами и не покрывает требования.

Канонический ID: `PRJ-T-<n>` (реестр [`../_registry.md`](../_registry.md)).

`status`: `draft` | `review` | `approved` | `obsolete`

Канонические связи:

- `contains` → `test-case` (`PRJ-T-<n>`; один кейс может входить в несколько сьюитов)
- `relates-to` → эпик или стори (`PRJ-<n>`; навигация и признак пакета приёмки, не покрытие)

Обратную `member-of` на кейсе не пишем.

## Цель прогона

Зачем этот набор (smoke, регресс, проверка фичи).

## Состав

Дублирует `contains` в frontmatter:

- `PRJ-T-N` — название кейса
