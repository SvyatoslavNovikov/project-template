# Модуль: Figma

Агент `figma-reader` читает макеты Figma (фреймы по node-id и комментарии) и пишет текстовую расшифровку в файл, чтобы основной поток не тратил контекст на скриншоты.

## Когда подключать

В проекте есть макеты в Figma, и требования ссылаются на них (`figma.com/design/…?node-id=…`).

## Что нужно на машине

- Claude in Chrome (расширение) с открытой сессией Figma в Chrome пользователя. Во встроенном браузере приложения агент упрётся в экран входа.
- Токен Figma не нужен: агент читает макет через браузер, API не использует.

## Как подключить

Из корня проекта:

```bash
cp optional/figma/agents/figma-reader.md .claude/agents/
```

```bash
cp optional/figma/docs/figma-reading.md docs/
```

Затем:

1. В `.claude/toolkit.md`, в таблицу агентов, добавить строку: `| figma-reader | sonnet | Макеты Figma по node-id → tmp/agents/figma/<тема>/figma.md, в чат дайджест. Только чтение |`.
2. Проверить заголовок: `python .claude/hooks/frontmatter_lint.py`.
3. Отметить подключение в `.claude/CHANGELOG.md` проекта.

## Как отключить

Удалить `.claude/agents/figma-reader.md` и `docs/figma-reading.md`, убрать строку из `toolkit.md`.

## Что в модуле

| Файл | Куда копировать | Что это |
|---|---|---|
| `agents/figma-reader.md` | `.claude/agents/` | Агент: порядок чтения, формат файла, ограничения |
| `docs/figma-reading.md` | `docs/` | Рецепт: навигация по node-id, тексты без скриншотов, известные сбои |
