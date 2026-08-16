---
id: PRJ-T-N
type: test-run
title: ""
status: planned
outcome: ""
mode: manual
release: ""
revision: ""
build: ""
environment: ""
executor: ""
started: YYYY-MM-DD
finished: ""
links:
  - type: executes
    to: PRJ-T-N
results:
  - case: PRJ-T-N
    status: not-run
    comment: ""
    defect: ""
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# PRJ-T-N-tr-slug

Каталог: `docs/tests/runs/PRJ-T-N-tr-slug/`.

Канонический ID: `PRJ-T-<n>` (реестр [`../_registry.md`](../_registry.md)). Result своего ID не имеет: ключ — этот run + `case`.

`status`: `planned` | `in-progress` | `completed` | `aborted`

`outcome` (считается по results, когда статус `completed`): `passed` | `failed` | `blocked`

`mode`: `manual` | `automated`

`release`: ключ из [`docs/requirements/_catalogs/releases.md`](../../requirements/_catalogs/releases.md). Один прогон — одна версия. Пусто, если прогон не сертифицирует поставку.

`environment`: ключ из [`docs/requirements/_catalogs/environments.md`](../../requirements/_catalogs/environments.md).

`revision`: git commit этого репозитория на старте прогона. Нужен с `in-progress`, чтобы восстановить шаги кейсов. Не путать с `build` (сборка продукта).

`results[].defect`: ID бага (`PRJ-<n>`), если статус `failed` или `blocked` и баг уже заведён.

`results[].status`: `passed` | `failed` | `blocked` | `skipped` | `not-run`

Состав кейсов — снимок на старт прогона. Живой `contains` сьюита после старта не перечитываем.

Короткий прогон: таблица `results` в этом файле. Длинный отчёт по кейсу: `results/PRJ-T-N.md` (имя = ID кейса).

## Сводка

- Сьюит:
- Релиз:
- Окружение:
- Revision:
- Сборка:

## Результаты

| Case | Status | Defect | Comment |
|---|---|---|---|
| `PRJ-T-N` | not-run | | |
