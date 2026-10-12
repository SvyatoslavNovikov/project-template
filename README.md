# Шаблон документации требований и тестов

Каркас для git: эпик → стори → системные требования, отдельно библиотека тестов, прогоны, баги и справочники (релизы, окружения).

Это **не продукт** и не привязка к конкретному TMS. Копируйте в новый репозиторий и подставьте свой префикс.

## Как начать

1. Скопировать этот репозиторий в проект.
2. Заменить префикс ID (см. ниже).
3. Читать с [`context.md`](context.md) — там карта инструкций и правила работы над требованиями.
4. Заполнить справочники [`releases`](docs/requirements/_catalogs/releases.md) и [`environments`](docs/requirements/_catalogs/environments.md).
5. Первый тикет — копия шаблона из `docs/requirements/_templates/`.

## Префикс ID

В шаблоне два пространства:

| Пространство | Пример | Где счётчик |
|---|---|---|
| Требования | `PRJ-1` | `docs/requirements/_registry.md` |
| Тесты | `PRJ-T-1` | `docs/tests/_registry.md` |

`PRJ` — заглушка. Замените на код проекта (латиница, без пробелов), например `ACME` и `ACME-T`. Менять нужно **везде**: инструкции, шаблоны, примеры в TRACEABILITY. Не переименовывайте только `PRJ-T` в `ACME` — иначе пространства смешаются.

Поиск по репозиторию: `PRJ`.

## Что внутри

- [`docs/requirements/`](docs/requirements/README.md) — эпики, стори, SR, NFR, баги
- [`docs/tests/`](docs/tests/README.md) — кейсы, сьюиты, прогоны
- [`docs/requirements/TRACEABILITY.md`](docs/requirements/TRACEABILITY.md) — типы связей и покрытие
- [`docs/requirements/GLOSSARY.md`](docs/requirements/GLOSSARY.md) — термины и роли
- [`CLAUDE.md`](CLAUDE.md) и [`.claude/`](.claude/toolkit.md) — правила Claude Code: оркестрация агентов, защитные хуки, handoff. Внешние системы проекта (трекер, вики, TMS) описать в `.claude/hooks/config.json`.
- [`optional/`](optional/README.md) — дополнительные модули (Figma и интеграции): подключаются копированием, только если нужны проекту.

Живые тикеты в шаблон не входят: папки `epics/`, `bugs/`, `cases/`, `suites/`, `runs/` пустые.
