# Тесты

Библиотека кейсов, сьюитов и прогонов. Покрытие требований — через `verifies` на кейсе, не через папки, сьюит или прогон.

Индексация **отдельная** от требований: [`_registry.md`](_registry.md) → `PRJ-T-<n>`.
Требования: [`../requirements/_registry.md`](../requirements/_registry.md) → `PRJ-<n>`.

Связи: [`../requirements/TRACEABILITY.md`](../requirements/TRACEABILITY.md).

## Структура

```text
docs/tests/
├── README.md
├── _registry.md
├── coverage-matrix.canvas.tsx
├── _templates/
│   ├── test-case.md
│   ├── test-suite.md
│   ├── test-run.md
│   └── test-result.md
├── cases/                              ← один файл = один кейс
│   └── PRJ-T-1-tc-....md
├── suites/                             ← наборы, кейсами не владеют
│   └── PRJ-T-2-ts-....md
└── runs/                               ← события прогона, не спецификация
    └── PRJ-T-3-tr-..../
        ├── PRJ-T-3-tr-....md
        └── results/                    ← опционально, длинный отчёт
            └── PRJ-T-1.md             ← имя = ID кейса
```

| Тип | Код в имени | YAML `type` | Папка | ID |
|---|---|---|---|---|
| Test case | `tc` | `test-case` | `cases/` | `PRJ-T-<n>` |
| Test suite | `ts` | `test-suite` | `suites/` | `PRJ-T-<n>` |
| Test run | `tr` | `test-run` | `runs/<id>-tr-slug/` | `PRJ-T-<n>` |
| Test result | — | — | строка в run или `runs/.../results/<case-id>.md` | нет, ключ `(run, case)` |

Имя файла: `PRJ-T-<n>-<тип>-<slug>.md`. Номера без ведущих нулей. `PRJ-10` и `PRJ-T-10` сосуществуют.

Ключи кейсов, сьюитов и прогонов во внешней TMS — необязательное поле `external` (правила — в [`../requirements/README.md`](../requirements/README.md#внешние-системы-поле-external)).

## Как выдать номер

1. Открыть [`_registry.md`](_registry.md).
2. Взять **Next**.
3. Создать файл (кейс, сьюит или прогон).
4. Сдвинуть реестр.

Result номер не берёт.

## Как добавить кейс

1. Выдать `PRJ-T-<n>`.
2. Скопировать [`_templates/test-case.md`](_templates/test-case.md) в `cases/`.
3. Переименовать в `PRJ-T-<n>-tc-<slug>.md`.
4. Заполнить `verifies` на SR/NFR (`PRJ-<n>`).

Без `verifies` кейс в покрытие не идёт. Статусы: `draft` → `review` → `approved` → `automated` → `obsolete`. Покрытие считается с `approved` или `automated`.

## Как добавить сьюит

1. Выдать `PRJ-T-<n>`.
2. Скопировать [`_templates/test-suite.md`](_templates/test-suite.md) в `suites/`.
3. Переименовать в `PRJ-T-<n>-ts-<slug>.md`.
4. Перечислить кейсы связью `contains` (`PRJ-T-<n>`).

Сьюит не закрывает требования. `relates-to` эпик — только навигация.

## Как добавить прогон

1. Выдать `PRJ-T-<n>`.
2. Создать папку `runs/PRJ-T-<n>-tr-<slug>/`.
3. Скопировать туда [`_templates/test-run.md`](_templates/test-run.md).
4. Связь `executes` → сьюит. Состав кейсов **скопировать** в `results` на момент старта.
5. Поле `release` — ключ из [`../requirements/_catalogs/releases.md`](../requirements/_catalogs/releases.md), если прогон сертифицирует поставку.
6. Поле `environment` — ключ из [`../requirements/_catalogs/environments.md`](../requirements/_catalogs/environments.md).
7. С `in-progress` заполнить `revision` (commit репозитория). `build` — сборка продукта, не ревизия кейсов.
8. По ходу прогона менять `results[].status`. На `failed` / `blocked` завести баг в `docs/requirements/bugs/` и прописать `defect`.
9. Не править состав, если сьюит изменился позже — только новый run.

Статусы прогона: `planned` → `in-progress` → `completed` | `aborted`.

Исход прогона (`outcome`), если `completed`:

- есть `failed` → `failed`
- иначе есть `blocked` → `blocked`
- иначе нет `not-run` → `passed`

Массовые CI-результаты в git не складываем: в репозитории схема и редкие ручные прогоны.

## Матрица покрытия

Открывается как Cursor Canvas рядом с чатом: [`coverage-matrix.canvas.tsx`](coverage-matrix.canvas.tsx).

Это покрытие **спецификации** (`verifies`), не статус последнего прогона. Canvas не читает markdown сам — после новых артефактов обновите снимок (кнопка Refresh snapshot from docs).
