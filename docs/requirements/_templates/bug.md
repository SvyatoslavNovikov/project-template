---
id: PRJ-N
type: bug
title: ""
status: open
severity: major
parent: ""
children: []
owner: ""
priority: must
tags: []
affects_releases: []
releases: []
environment: ""
found_in: PRJ-T-N
found_on: PRJ-T-N
links:
  - type: defects
    to: PRJ-N
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# PRJ-N-bug-slug

Каталог: `docs/requirements/bugs/`. Не входит в дерево эпик → стори → SR.

`status`: `open` | `in-progress` | `fixed` | `verified` | `closed` | `rejected`

`severity`: `blocker` | `major` | `minor` | `trivial`

`affects_releases` — где воспроизвели (Affects Version). `releases` — куда чиним (Fix Version). Ключи из [`../_catalogs/releases.md`](../_catalogs/releases.md).

`environment` — ключ из [`../_catalogs/environments.md`](../_catalogs/environments.md).

`found_in` / `found_on` — прогон и кейс, где впервые поймали. На строке результата того прогона поле `defect` должно указывать на этот ID.

`defects` → SR или NFR, которое ломается. Баг не покрывает требование и не заменяет `verifies`.

## Воспроизведение

1. …

## Фактический результат

- …

## Ожидаемый результат

- …
