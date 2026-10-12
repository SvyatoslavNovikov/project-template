# Изменения инструментария Claude Code

Что менялось в `CLAUDE.md` и `.claude/` шаблона. Проект, созданный из шаблона, переносит изменения вручную и отмечает у себя, до какой записи дошёл.

## 2026-10-12
- `CLAUDE.md`: карта, жёсткие правила, оркестрация и экономия токенов, Compact instructions (перенесено из lk-context и обобщено).
- `CLAUDE.local.md` по шаблону `.claude/claude-local.template.md`, напоминание — хук `local_rules_check.py`.
- Хуки `secret_guard`, `external_write_guard` с настройкой через `.claude/hooks/config.json`; `frontmatter_lint`, `command_parse`; тесты в `.claude/hooks/tests/`.
- Скилл `handoff`.
- Агент `playwright-runner`: прогон по кейсам `docs/tests`, ID кейса `PRJ-T-<n>` — идентификатор автотеста; сырой отчёт в `tmp/agents/playwright/`, прогон в `docs/tests/runs/` — по просьбе. В `.gitignore` — каталоги отчётов Playwright.
