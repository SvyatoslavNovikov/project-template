# Модуль: Confluence

Чтение страниц Confluence как текста (источник для требований) и публикация артефактов `docs/` и конспектов встреч с ID страницы в `external.confluence`.

Требует модуль [`common`](../common/README.md).

## Что нужно

- Confluence Server, Data Center или Cloud с REST API `/rest/api/content`.
- Токен в переменной окружения `CONF_TOKEN`: для Server/DC — Personal Access Token, для Cloud — API token и `CONF_USER` (email) с `"auth": "basic"` в конфиге. Задавать на уровне пользователя ОС, не в файлах репозитория.
- PyYAML (`pip install pyyaml`).

## Как подключить

Из корня проекта, после модуля `common`:

```bash
cp optional/confluence/scripts/confluence_cli.py optional/confluence/scripts/confluence.config.json scripts/
```

```bash
cp optional/confluence/scripts/lib/*.py scripts/lib/
```

```bash
mkdir -p scripts/tests .claude/skills/confluence && cp optional/confluence/scripts/tests/*.py scripts/tests/ && cp optional/confluence/skills/confluence/SKILL.md .claude/skills/confluence/
```

Затем:

1. Заполнить `scripts/confluence.config.json`: `base_url` (или env `CONF_BASE_URL`, он важнее; для Cloud — с `/wiki`), `space` и `parent_id` по умолчанию для publish.
2. Дописать в `.claude/hooks/config.json` списки из [`config.json`](config.json) модуля, заменив хост на свой (регулярное выражение).
3. Проверить: `python -m unittest discover -s scripts/tests -v`, `python .claude/hooks/frontmatter_lint.py`, `python scripts/confluence_cli.py read <pageId>`.
4. Скилл `confluence` — в таблицу скиллов `.claude/toolkit.md`; подключение — в `.claude/CHANGELOG.md` проекта.

## Что в модуле

| Файл | Куда | Что это |
|---|---|---|
| `scripts/confluence_cli.py` | `scripts/` | CLI: `read`, `search`, `publish` (dry-run без `--apply`) |
| `scripts/confluence.config.json` | `scripts/` | Пространство и родитель по умолчанию, без токенов |
| `scripts/lib/confluence_client.py` | `scripts/lib/` | Клиент REST API поверх `http_client.ApiClient` |
| `scripts/lib/confluence_markup.py` | `scripts/lib/` | Markdown → storage-формат и storage → текст |
| `scripts/tests/test_confluence.py` | `scripts/tests/` | Тесты без сети: разметка, ID страницы, dry-run, запись ID |
| `skills/confluence/SKILL.md` | `.claude/skills/confluence/` | Когда и как читать и публиковать |
| `config.json` | дописать в `.claude/hooks/config.json` | Токен, хост, клиент и CLI для защитных хуков |

## Чего модуль не делает

Вложения, макросы кроме блока кода, упоминания людей, страницы демо по шаблону конкретной команды — нет. Нужны — дописать в проекте поверх `confluence_client.py` и `confluence_markup.py`.
