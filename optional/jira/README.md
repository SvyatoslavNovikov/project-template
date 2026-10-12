# Модуль: Jira

Чтение задач Jira и выгрузка эпиков, стори и багов из `docs/requirements` в Jira с ключом в `external.jira`. Источник правды — репозиторий, Jira получает копию.

Требует модуль [`common`](../common/README.md).

## Что нужно

- Jira Server, Data Center или Cloud с REST API v2.
- Токен в переменной окружения `JIRA_TOKEN`: для Server/DC — Personal Access Token, для Cloud — API token и `JIRA_USER` (email) с `"auth": "basic"` в конфиге. Задавать на уровне пользователя ОС, не в файлах репозитория.
- PyYAML (`pip install pyyaml`).

## Как подключить

Из корня проекта, после модуля `common`:

```bash
cp optional/jira/scripts/jira_cli.py optional/jira/scripts/jira.config.json scripts/
```

```bash
cp optional/jira/scripts/lib/*.py scripts/lib/
```

```bash
mkdir -p scripts/tests .claude/skills/jira && cp optional/jira/scripts/tests/*.py scripts/tests/ && cp optional/jira/skills/jira/SKILL.md .claude/skills/jira/
```

Затем:

1. Заполнить `scripts/jira.config.json`:
   - `base_url` — адрес Jira (или env `JIRA_BASE_URL`, он важнее);
   - `project` — ключ проекта Jira;
   - `issue_types` — тип артефакта → тип задачи Jira; что не указано, не выгружается;
   - `epic_name_field`, `epic_link_field` — ID полей Epic Name и Epic Link (`customfield_…`), если в Jira они есть; узнать — `GET /rest/api/2/field` или у администратора, не угадывать;
   - `labels` — метки, которые ставятся на все выгруженные задачи.
2. Дописать в `.claude/hooks/config.json` списки из [`config.json`](config.json) модуля, заменив хост на свой (регулярное выражение).
3. Проверить: `python -m unittest discover -s scripts/tests -v`, `python .claude/hooks/frontmatter_lint.py`, `python scripts/jira_cli.py digest <любой ключ>`.
4. Скилл `jira` — в таблицу скиллов `.claude/toolkit.md`; подключение — в `.claude/CHANGELOG.md` проекта.

## Что в модуле

| Файл | Куда | Что это |
|---|---|---|
| `scripts/jira_cli.py` | `scripts/` | CLI: `digest`, `find`, `publish` (dry-run без `--apply`) |
| `scripts/jira.config.json` | `scripts/` | Настройки проекта Jira, без токенов |
| `scripts/lib/jira_client.py` | `scripts/lib/` | Клиент REST API v2 поверх `http_client.ApiClient` |
| `scripts/lib/jira_markup.py` | `scripts/lib/` | Markdown → разметка Jira wiki |
| `scripts/tests/test_jira.py` | `scripts/tests/` | Тесты без сети: разметка, поля, dry-run, запись ключа |
| `skills/jira/SKILL.md` | `.claude/skills/jira/` | Когда и как читать и выгружать |
| `config.json` | дописать в `.claude/hooks/config.json` | Токен, хост, клиент и CLI для защитных хуков |

## Чего модуль не делает

Статусы, исполнители, спринты, версии, Smart Checklist и прочие поля конкретной Jira — нет: это настройки процессов, а не требования. Нужны — дописать в проекте поверх `jira_client.py`.
