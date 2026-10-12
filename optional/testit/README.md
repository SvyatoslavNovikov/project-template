# Модуль: Test IT

Выгрузка кейсов `docs/tests/cases` в Test IT (work items, globalId в `external.testit`) и результатов прогонов `docs/tests/runs` (автотесты с `externalId` = ID кейса, тест-ран по конфигурации). Источник правды — репозиторий.

Требует модуль [`common`](../common/README.md).

## Что нужно

- Test IT с REST API v2.
- Токен в переменной окружения `TMS_PRIVATE_TOKEN` (заголовок `PrivateToken`). Задавать на уровне пользователя ОС, не в файлах репозитория.
- PyYAML (`pip install pyyaml`).

## Как подключить

Из корня проекта, после модуля `common`:

```bash
cp optional/testit/scripts/testit_cli.py optional/testit/scripts/testit.config.json scripts/
```

```bash
cp optional/testit/scripts/lib/*.py scripts/lib/
```

```bash
mkdir -p scripts/tests .claude/skills/testit && cp optional/testit/scripts/tests/*.py scripts/tests/ && cp optional/testit/skills/testit/SKILL.md .claude/skills/testit/
```

Затем:

1. Заполнить `scripts/testit.config.json`: `base_url` (или env `TMS_BASE_URL`, он важнее), `project_id` — UUID проекта, `section_id` — UUID секции для новых кейсов, `configuration_id` — UUID конфигурации тест-ранов. Взять в Test IT или у администратора, не угадывать.
2. Дописать в `.claude/hooks/config.json` списки из [`config.json`](config.json) модуля, заменив хост на свой (регулярное выражение).
3. Проверить: `python -m unittest discover -s scripts/tests -v`, `python .claude/hooks/frontmatter_lint.py`, `python scripts/testit_cli.py push-cases` (dry-run).
4. Скилл `testit` — в таблицу скиллов `.claude/toolkit.md`; подключение — в `.claude/CHANGELOG.md` проекта.

## Что в модуле

| Файл | Куда | Что это |
|---|---|---|
| `scripts/testit_cli.py` | `scripts/` | CLI: `push-cases`, `push-results` (dry-run без `--apply`) |
| `scripts/testit.config.json` | `scripts/` | Проект, секция, конфигурация, без токенов |
| `scripts/lib/testit_client.py` | `scripts/lib/` | Клиент REST API v2 поверх `http_client.ApiClient` |
| `scripts/tests/test_testit.py` | `scripts/tests/` | Тесты без сети: work item, dry-run, globalId, результаты |
| `skills/testit/SKILL.md` | `.claude/skills/testit/` | Когда и как выгружать |
| `config.json` | дописать в `.claude/hooks/config.json` | Токен, хост, клиент и CLI для защитных хуков |

## Что не проверено и чего модуль не делает

- Формат результатов (`outcome` вместе с `statusCode`) взят из работающей интеграции проекта ELKA; на другой версии Test IT сверить с документацией API.
- Если автотест с таким `externalId` уже есть (HTTP 409), CLI его не пересоздаёт и связь с work item заново не ставит.
- Тест-планы, чек-листы, вложения, синхронизация из Test IT обратно в репозиторий — нет.
