# Модуль: common

Общая часть модулей интеграции (`jira`, `confluence`, `testit`). Сам по себе ничего не делает: подключается первым, до любого из них.

## Что в модуле

| Файл | Куда | Что это |
|---|---|---|
| `scripts/lib/http_client.py` | `scripts/lib/` | JSON-запросы на stdlib и `ApiClient`: запись без `apply=True` не отправляется, а печатается (dry-run по умолчанию) |
| `scripts/lib/artifacts.py` | `scripts/lib/` | Найти артефакт по ID, прочитать frontmatter и секции, записать `external.<система>` без переформатирования YAML |
| `scripts/tests/test_common.py` | `scripts/tests/` | Тесты без сети |

## Как подключить

```bash
mkdir -p scripts/lib scripts/tests && cp optional/common/scripts/lib/*.py scripts/lib/ && cp optional/common/scripts/tests/*.py scripts/tests/
```

Нужен PyYAML (`pip install pyyaml`). Проверка: `python -m unittest discover -s scripts/tests -v`.

## Правила для клиентов интеграций

- Клиент наследует `ApiClient`, пишет только через `_post`, `_put`, `_delete`: тогда dry-run и хук `external_write_guard` (по `client_files`) работают без доработок.
- Токен — только `env_token("<ИМЯ>")`, в конфигах и командах его нет.
- CLI принимает `--apply`; без него печатает план и пишет «dry-run: ничего не отправлено».
- Ключ созданного объекта — в `external.<система>` артефакта через `artifacts.set_external`, только по ответу сервиса.
