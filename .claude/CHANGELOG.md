# Изменения инструментария Claude Code

Что менялось в `CLAUDE.md` и `.claude/` шаблона. Проект, созданный из шаблона, переносит изменения вручную и отмечает у себя, до какой записи дошёл.

## 2026-10-12
- `CLAUDE.md`: карта, жёсткие правила, оркестрация и экономия токенов, Compact instructions (перенесено из lk-context и обобщено).
- `CLAUDE.local.md` по шаблону `.claude/claude-local.template.md`, напоминание — хук `local_rules_check.py`.
- Хуки `secret_guard`, `external_write_guard` с настройкой через `.claude/hooks/config.json`; `frontmatter_lint`, `command_parse`; тесты в `.claude/hooks/tests/`.
- Скилл `handoff`.
- Агент `playwright-runner`: прогон по кейсам `docs/tests`, ID кейса `PRJ-T-<n>` — идентификатор автотеста; сырой отчёт в `tmp/agents/playwright/`, прогон в `docs/tests/runs/` — по просьбе. В `.gitignore` — каталоги отчётов Playwright.
- Агенты `req-writer` (оформление требований по шаблонам и реестру) и `req-reviewer` (проверка трассировки, инвариантов и противоречий, только чтение).
- `req_lint.py`: механика `docs/requirements` и `docs/tests` (CLI и хук PostToolUse), тесты `.claude/hooks/tests/test_req_lint.py`. `req-writer` и `req-reviewer` запускают его вместо ручной проверки механики.
- `req_lint.py` переименован в `docs_lint.py`: он проверяет и требования, и тесты. Новые проверки: `level` у SR и кейса, `mode` у прогона, кейс без `verifies` (ошибка с `approved`/`automated`), `verifies` на obsolete-требование, пустые «Шаги» и «Ожидаемый результат» с `review`, obsolete-кейс в сьюите.
- `.gitattributes`: LF в рабочей копии на любой ОС (`* text=auto eol=lf`), CRLF только для `.bat`/`.cmd`.
- Агент `test-case-author`: кейсы из approved SR и NFR, `verifies`, проверка `docs_lint`.
- Скиллы `bug-report`, `regression-report`, `meeting-notes` под структуру `docs/requirements` и `docs/tests`; конспекты встреч — `docs/meetings/`. `docs_lint` проверяет `severity` бага.
- `optional/`: дополнительные модули, подключаются копированием. Первый — `optional/figma/` (агент `figma-reader`, рецепт `figma-reading.md`). `frontmatter_lint` проверяет агентов и скиллы модулей.
- Поле `external` (ключи во внешних системах) в правилах `docs/` и в `docs_lint`: словарь «система → ID», один внешний ID — один артефакт.
- Модули `optional/common`, `jira`, `confluence`, `testit`: клиенты REST, CLI с dry-run по умолчанию и `--apply`, скиллы, фрагменты `config.json`, тесты без сети.
- `hook_config`: ошибка в `.claude/hooks/config.json` больше не выключает защиту молча — `external_write_guard` спрашивает подтверждение на любую команду и называет причину.
- `TRACEABILITY.md`: инвариант про уникальность `external` перенесён в конец списка под №22 — при добавлении он получил №16 и задублировал номер инварианта про `environment`.

## 2026-11-07
- Статус `canceled` для требований, отменённых до реализации (из frame-crm): поле `cancel_reason`, папка `docs/requirements/_canceled/` вне дерева, правила в README и TRACEABILITY (инвариант 5). `docs_lint`: canceled только в `_canceled/` и с `cancel_reason`, пустой `children`, живые артефакты на canceled не ссылаются; тесты. `.ignore` исключает `_canceled/` из поиска, `CLAUDE.md` и агенты `req-writer`, `req-reviewer`, `test-case-author` её не читают.

## 2026-11-09
- Агенты `app-developer` (sonnet: код в репозитории приложения, общается только с основным потоком, системные решения возвращает готовыми) и `code-reviewer` (opus: независимое ревью кода без отчёта разработчика). `req-reviewer` проверяет, что системные решения выводятся из стори, эпика и NFR пользователя.
- `CLAUDE.md`: граница решений (эпик, стори, NFR пользователя — пользователь; SR, ADR — основной поток после ревью), раздел «Разработка и решения»: разработка агентом вместо отдельной сессии, вопросы пользователю на языке продукта, список системных решений раз в этап. Имя каталога репозитория кода в шаблоне — `TBD`.
- Статусы требований: `in-progress`, `acceptance` (эпик и стори), `superseded` (заменено до релиза); кто переводит статус, приёмка, классы замечаний, пересмотр требований — `docs/requirements/README.md`. `docs_lint` проверяет новые статусы и инварианты 23–28 `TRACEABILITY.md`; тесты. Скилл `regression-report` собирает пакет приёмки.
- Путь к соседнему репозиторию кода не зашит: по умолчанию соседний каталог, иначе — в `CLAUDE.local.md` (поле в `.claude/claude-local.template.md`); основной поток передаёт абсолютный путь агентам в брифе. Поле NFR `decided_by: user | system` — кто утверждает NFR.
