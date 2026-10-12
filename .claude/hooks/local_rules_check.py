# -*- coding: utf-8 -*-
"""SessionStart(startup): если на машине нет CLAUDE.local.md, подсказывает Claude
создать его по шаблону .claude/claude-local.template.md вместе с пользователем.

Вывод в stdout у SessionStart попадает в контекст сессии. Есть файл — хук молчит.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent.parent

if not (ROOT / "CLAUDE.local.md").is_file():
    print(
        "На этой машине нет CLAUDE.local.md (личные правила, в git не попадает). "
        "В начале ответа одной строкой предложи пользователю создать его по шаблону "
        ".claude/claude-local.template.md: спроси недостающее (роль, как к нему обращаться, "
        "что можно делать без вопроса) и ничего не придумывай. Если откажется — не напоминай."
    )
