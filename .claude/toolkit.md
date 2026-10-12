# Инструментарий Claude Code

Что шаблон даёт Claude Code и как настроить под проект. Правила работы — в [`CLAUDE.md`](../CLAUDE.md).

## Скиллы (`.claude/skills/`)

| Скилл | Когда |
|---|---|
| `handoff` | Граница фаз, контекст больше ~200K, пауза дольше часа: состояние в `docs/handoff/`, работа продолжается в новой сессии |

## Агенты (`.claude/agents/`)

| Агент | Модель | Когда |
|---|---|---|
| `req-writer` | sonnet | Оформить принятые решения в эпик, стори, SR, NFR по шаблонам: ID по реестру, `parent`/`children`/`links`. Пакет стори — параллельно, ID выдаёт основной поток |
| `req-reviewer` | opus | Проверка требований и кейсов перед показом и перед `review`/`approved`: трассировка, инварианты, противоречия, глоссарий. Только чтение |
| `playwright-runner` | sonnet | Прогон Playwright-тестов по кейсам `docs/tests` (приёмка, регресс, проверка бага), заведение раннера и автотестов по кейсам. Сырой отчёт — в `tmp/agents/playwright/`, прогон в `docs/tests/runs/` — только по просьбе |

Новый агент — файл `.claude/agents/<имя>.md` с заголовком `name`, `description`, `model` (и при необходимости `tools`, `effort`, `maxTurns`); `name` совпадает с именем файла. Префикс ID в тексте агента не прописывать: брать его из `docs/requirements/_registry.md` и `docs/tests/_registry.md`.

## Хуки (`.claude/hooks/` + `.claude/settings.json`)

| Хук | Событие | Что делает |
|---|---|---|
| `local_rules_check.py` | SessionStart | Нет `CLAUDE.local.md` — предлагает создать по `.claude/claude-local.template.md` |
| `secret_guard.py` | PreToolUse (Bash, PowerShell) | Запрещает литералы токенов в команде и `git add` каталогов сырых выгрузок |
| `external_write_guard.py` | PreToolUse (Bash, PowerShell) | Спрашивает подтверждение на запись во внешние системы; чтение и `--dry-run` пропускает |
| `frontmatter_lint.py` | PostToolUse (Write, Edit) | Проверяет заголовок агентов и скиллов: с ошибкой в YAML приложение молча их не регистрирует |
| `req_lint.py` | PostToolUse (Write, Edit) | Механика `docs/requirements` и `docs/tests`: имена и ID, дерево и `children`, связи, справочники, прогоны, инварианты, реестры. Показывает замечания по изменённому файлу и реестру его пространства |

`command_parse.py` — общий разбор команд для хуков: отличает запуск скрипта от упоминания в `git add`, `grep` или тексте коммита. `hook_config.py` читает настройки.

### Настройка под проект: `.claude/hooks/config.json`

По умолчанию списки пустые: хуки проверяют только литералы токенов (имена на `_TOKEN`, `_SECRET`, `_PASSWORD`, `_API_KEY` и заголовки `Bearer …`). Когда у проекта появляется внешняя система, её описывают здесь:

```json
{
  "secret_env": ["JIRA_TOKEN"],
  "export_dirs": ["jira-export/"],
  "write_hosts": ["jira\\.example\\.com"],
  "client_files": ["scripts/lib/jira_client.py"],
  "apply_scripts": ["scripts/jira.py"]
}
```

- `secret_env` — имена переменных с токенами, которые не ловятся общим правилом.
- `export_dirs` — каталоги сырых выгрузок; их же добавить в `.gitignore`.
- `write_hosts` — регулярные выражения хостов: запись на них только с подтверждением.
- `client_files` — Python-клиенты API: методы с `_post`/`_put`/`_delete` считаются записью.
- `apply_scripts` — скрипты, которые без `--apply` работают в dry-run.

### Проверки

```bash
python -m unittest discover -s .claude/hooks/tests -v
```

```bash
python .claude/hooks/frontmatter_lint.py
```

```bash
python .claude/hooks/req_lint.py docs
```

`req_lint.py` без аргументов проверяет всё, с путями — показывает замечания только по ним; код выхода 1 при ошибках, предупреждения (`warn`) его не меняют. Нужен PyYAML (`pip install pyyaml`): без него хук молчит, CLI завершается с кодом 2. Смысл требований линтер не проверяет: это `req-reviewer`.

Тесты хуков работают на временном репозитории со своим конфигом и не зависят от `config.json` проекта. После правки хуков прогнать их.

## Обновления шаблона

Проекты копируют шаблон, а не ссылаются на него. Изменения в `.claude/` и `CLAUDE.md` записывать в [`CHANGELOG.md`](CHANGELOG.md), чтобы в проекте было видно, что уже перенесено.
