# -*- coding: utf-8 -*-
"""Заголовок (frontmatter) агентов и скиллов: `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`
и копии в `.cursor/`.

Если YAML в заголовке не разбирается, приложение молча не регистрирует агента или
скилл. Так `figma-reader` с 07.10 по 11.10.2026 не был доступен как тип: в
description без кавычек стояло «Только чтение: ничего…», и `: ` YAML читает как новый ключ.

  python .claude/hooks/frontmatter_lint.py            проверить все файлы репозитория
  python .claude/hooks/frontmatter_lint.py --hook     режим хука PostToolUse(Write|Edit): JSON из stdin
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = re.compile(r"(^|/)(\.claude|\.cursor|optional/[^/]+)/(agents/[^/]+\.md|skills/[^/]+/SKILL\.md)$")
KEY = re.compile(r"^([A-Za-z][\w-]*):(?:\s+(.*))?$")

try:
    import yaml
except ImportError:  # без PyYAML остаётся построчная проверка
    yaml = None


def is_target(path: Path) -> bool:
    return bool(TARGET.search(path.as_posix()))


def frontmatter(text: str) -> tuple[str, int] | None:
    """Текст заголовка и номер его первой строки в файле, либо None."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for n, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:n]), 2
    return None


def plain_value_issue(value: str) -> str | None:
    """Чем однострочное значение без кавычек ломает YAML."""
    if not value or value[0] in "'\"|>":
        return None
    if value[0] in "&*!%@`{[":
        return f"значение начинается с «{value[0]}»: взять в кавычки"
    if ": " in value or value.endswith(":"):
        return "в значении без кавычек «: », YAML примет это за новый ключ: заменить на тире или запятую либо взять значение в кавычки"
    if " #" in value:
        return "в значении без кавычек « #», дальше YAML считает комментарий: взять в кавычки"
    return None


def lint_text(text: str, path: Path) -> list[tuple[int, str]]:
    fm = frontmatter(text)
    if fm is None:
        return [(1, "нет заголовка между строками «---»: агент или скилл не зарегистрируется")]
    body, first = fm
    issues: list[tuple[int, str]] = []
    keys: dict[str, str] = {}
    for n, line in enumerate(body.splitlines(), start=first):
        m = KEY.match(line)
        if not m:
            continue
        key, value = m.group(1), (m.group(2) or "").strip()
        keys[key] = value
        problem = plain_value_issue(value)
        if problem:
            issues.append((n, f"{key}: {problem}"))
    if yaml is not None and not issues:
        try:
            data = yaml.safe_load(body)
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            line = first + mark.line if mark else first
            return [(line, f"YAML не разбирается: {getattr(e, 'problem', None) or e}")]
        if not isinstance(data, dict):
            return [(first, "заголовок не является набором «ключ: значение»")]
        keys = {k: str(v) for k, v in data.items()}
    for key in ("name", "description"):
        if not keys.get(key):
            issues.append((first, f"нет поля «{key}»"))
    expected = path.parent.name if path.name == "SKILL.md" else path.stem
    if keys.get("name") and keys["name"] != expected:
        issues.append((first, f"name «{keys['name']}» не совпадает с именем файла или каталога «{expected}»"))
    return issues


def lint_file(path: Path) -> list[tuple[int, str]]:
    return lint_text(path.read_text(encoding="utf-8"), path)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def hook() -> int:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    path = Path(file_path)
    if not file_path or not is_target(path) or not path.exists():
        return 0
    issues = lint_file(path)
    if issues:
        text = (f"frontmatter: {rel(path)} — с такой ошибкой агент или скилл не зарегистрируется\n"
                + "\n".join(f"  строка {n}: {msg}" for n, msg in issues))
        print(json.dumps({
            "systemMessage": text,
            "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text},
        }, ensure_ascii=False))
    return 0


def all_targets() -> list[Path]:
    found = []
    for base in [ROOT / ".claude", ROOT / ".cursor", *sorted((ROOT / "optional").glob("*/"))]:
        found += sorted(base.glob("agents/*.md"))
        found += sorted(base.glob("skills/*/SKILL.md"))
    return found


def main(argv: list[str]) -> int:
    if argv[:1] == ["--hook"]:
        return hook()
    sys.stdout.reconfigure(encoding="utf-8")
    total = 0
    for path in all_targets():
        for n, message in lint_file(path):
            print(f"{rel(path)}:{n}: {message}")
            total += 1
    print(f"замечаний: {total}" if total else "замечаний нет")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
