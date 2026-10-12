# -*- coding: utf-8 -*-
"""Настройки защитных хуков проекта: `.claude/hooks/config.json`.

Хуки шаблона не знают систем конкретного проекта. Что считать секретом, сырой
выгрузкой и записью во внешнюю систему, задаёт config.json:

  secret_env     имена переменных с токенами: литерал `ИМЯ=значение` в команде запрещён
                 (имена на _TOKEN, _SECRET, _PASSWORD, _API_KEY ловятся и без списка);
  export_dirs    каталоги сырых выгрузок: `git add` и `git commit` с ними запрещены;
  write_hosts    регулярные выражения хостов внешних систем: запись на них (curl,
                 Invoke-RestMethod, скрипты с POST/PUT/PATCH/DELETE) — только с подтверждением;
  client_files   Python-клиенты API (пути от корня): их методы с _post/_put/_delete считаются записью;
  apply_scripts  скрипты (пути от корня), которые пишут только с флагом --apply.

Нет файла или пустые списки — хук проверяет только общее (литералы токенов в заголовках).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS = ("secret_env", "export_dirs", "write_hosts", "client_files", "apply_scripts")


def load() -> dict[str, list[str]]:
    try:
        data = json.loads((ROOT / ".claude" / "hooks" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {key: [str(v) for v in data.get(key) or []] for key in KEYS}
