# Требования

Хранение продуктовых требований в git: эпик → user story → системные требования.

Связи между артефактами, покрытие тестами и правила ссылок: [`TRACEABILITY.md`](TRACEABILITY.md). Термины: [`GLOSSARY.md`](GLOSSARY.md).

## Структура

```text
docs/requirements/
├── README.md
├── TRACEABILITY.md
├── GLOSSARY.md
├── _registry.md
├── _catalogs/
│   ├── releases.md
│   └── environments.md
├── _templates/
├── bugs/
│   └── PRJ-N-bug-....md
└── epics/
    └── PRJ-1-epic-.../
        ├── PRJ-1-epic-....md
        └── stories/
            └── PRJ-2-us-.../
                ├── PRJ-2-us-....md
                └── requirements/
                    ├── PRJ-3-sr-....md
                    └── PRJ-4-nfr-....md
```

Один артефакт — один файл. Иерархия дублируется папками.

Идея не отдельный тип: это короткий набросок внутри эпика (секция «Идея»).

Тесты **не** кладём в дерево требований. Каталог: [`docs/tests/`](../tests/README.md) — кейсы, сьюиты и прогоны. Их ID — `PRJ-T-<n>`, отдельный реестр. Покрытие спецификации — `verifies` на кейсе. Матрица: [`docs/tests/coverage-matrix.canvas.tsx`](../tests/coverage-matrix.canvas.tsx).

Релизы — справочник [`_catalogs/releases.md`](_catalogs/releases.md), не тикеты. В тикете поле `releases` (ключи из справочника). В прогоне — поле `release`.

Окружения — справочник [`_catalogs/environments.md`](_catalogs/environments.md). В прогоне и на баге — поле `environment`.

Баги — тикеты [`bugs/`](bugs/) (`PRJ-<n>-bug-…`), не строки результата и не узлы дерева эпик → стори.

## Идентификаторы

Два независимых счётчика:

| Пространство | Канонический ID | Реестр | Что нумерует |
|---|---|---|---|
| Требования | `PRJ-<n>` | [`_registry.md`](_registry.md) | epic, user-story, sr, nfr, bug |
| Тесты | `PRJ-T-<n>` | [`docs/tests/_registry.md`](../tests/_registry.md) | test-case, test-suite, test-run |

Справочники (`_catalogs/`) в счётчик не входят.

`PRJ-10` и `PRJ-T-10` — разные документы, это нормально.

Внутри каждого пространства номер **сквозной** по типам: нельзя два файла `PRJ-10` в требованиях и нельзя два `PRJ-T-10` в тестах. Номер не переиспользуется, даже если артефакт `obsolete`.

Имя файла и папки (требования):

```text
PRJ-<номер>-<тип>-<slug>.md
```

Пример: `PRJ-10-us-create-test-case.md`

| Тип | Код в имени | Значение `type` в YAML |
|---|---|---|
| Epic | `epic` | `epic` |
| User Story | `us` | `user-story` |
| System Requirement | `sr` | `system-requirement` |
| Non-functional | `nfr` | `nfr` |
| Bug | `bug` | `bug` |

Тестовые типы и имена — в [`docs/tests/README.md`](../tests/README.md).

В тексте и ссылках используем канонический ID (`PRJ-10` или `PRJ-T-10`). Тип и slug в имени можно менять; номер — нельзя.

Номера без ведущих нулей: `PRJ-10`, не `PRJ-010`.

## Как выдать номер

1. Открыть реестр своего пространства (`docs/requirements/_registry.md` или `docs/tests/_registry.md`).
2. Взять значение **Next**.
3. Создать файл с этим номером.
4. Обновить реестр: `Last issued` = выданный номер, `Next` = `+1`.

## Статусы требований

`draft` → `review` → `approved` → `implemented` → `obsolete`

| Статус | Смысл |
|---|---|
| `draft` | черновик |
| `review` | готово к ревью |
| `approved` | можно проектировать и реализовывать |
| `implemented` | закрыто реализацией |
| `obsolete` | не действует; файл не удаляем, указываем чем заменено через `supersedes` |

Приоритет: `must` | `should` | `could`.

`releases`: список ключей из [`_catalogs/releases.md`](_catalogs/releases.md). Обычно заполняем на user story; на SR — если в версию идёт отдельное требование (хотфикс); на эпике — по желанию; на баге — Fix Version. Пустой список = ещё не запланировано в версию.

Статусы багов и тестов — в [`TRACEABILITY.md`](TRACEABILITY.md). Роли в стори — из [`GLOSSARY.md`](GLOSSARY.md).

## Как добавить артефакт

1. Выдать номер (см. выше).
2. Скопировать шаблон из `_templates/` в нужное место дерева.
3. Переименовать в `PRJ-<n>-<тип>-<slug>`.
4. Заполнить frontmatter и секции.
5. Прописать `parent` (кроме эпика и бага) и добавить себя в `children` родителя.
6. Ассоциации (`depends-on`, `constrains`, …) писать в `links` — см. [`TRACEABILITY.md`](TRACEABILITY.md).
7. Версию поставки и окружение выбирать из справочников, не создавать тикет релиза или окружения.
8. Роль в user story брать из [`GLOSSARY.md`](GLOSSARY.md).

Шаблоны:

- [`_templates/epic.md`](_templates/epic.md)
- [`_templates/user-story.md`](_templates/user-story.md)
- [`_templates/system-requirement.md`](_templates/system-requirement.md)
- [`_templates/nfr.md`](_templates/nfr.md)
- [`_templates/bug.md`](_templates/bug.md)

Шаблоны тестов — в [`docs/tests/_templates/`](../tests/_templates/).
