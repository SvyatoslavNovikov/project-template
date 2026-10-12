# -*- coding: utf-8 -*-
"""Артефакты docs/requirements и docs/tests для CLI интеграций.

  find(root, "ACME-12")            путь к файлу артефакта по ID
  load(path) -> Artifact           frontmatter (dict), тело без frontmatter и H1, секции
  set_external(path, "jira", key)  записать external.<система> правкой текста, не перегенерируя YAML

Нужен PyYAML (`pip install pyyaml`), как и для `.claude/hooks/docs_lint.py`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DOCS = ("docs/requirements", "docs/tests")
ID_IN_NAME = re.compile(r"^([A-Z][A-Z0-9]*-(?:T-)?\d+)-[a-z]+-")


@dataclass
class Artifact:
    path: Path
    fm: dict[str, Any]
    body: str
    sections: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return str(self.fm.get("id", ""))

    @property
    def type(self) -> str:
        return str(self.fm.get("type", ""))

    @property
    def title(self) -> str:
        return str(self.fm.get("title") or "").strip() or self.path.stem

    def external(self, system: str) -> str | None:
        value = (self.fm.get("external") or {}).get(system)
        return str(value) if value not in (None, "") else None


def split(text: str) -> tuple[list[str], int]:
    """Строки файла и индекс закрывающей строки --- frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("нет frontmatter")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines, i
    raise ValueError("frontmatter не закрыт")


def load(path: Path) -> Artifact:
    text = path.read_text(encoding="utf-8")
    lines, end = split(text)
    fm = yaml.safe_load("\n".join(lines[1:end])) or {}
    rest = lines[end + 1:]
    # заголовок H1 = имя файла, во внешнюю систему не нужен
    while rest and not rest[0].strip():
        rest.pop(0)
    if rest and rest[0].startswith("# "):
        rest.pop(0)
    body = "\n".join(rest).strip() + "\n"
    return Artifact(path, fm, body, sections(body))


def sections(body: str) -> dict[str, str]:
    """Секции «## Заголовок» → текст секции."""
    result: dict[str, str] = {}
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            result[current] = ""
        elif current is not None:
            result[current] += line + "\n"
    return {k: v.strip() for k, v in result.items()}


def items(section: str) -> list[str]:
    """Пункты нумерованного или маркированного списка без заглушек шаблона."""
    out = []
    for line in section.splitlines():
        m = re.match(r"^\s*(?:\d+\.|[-*])\s+(.*)$", line)
        if m and m.group(1).strip() not in ("", "…", "..."):
            out.append(m.group(1).strip())
    return out


def find(root: Path, artifact_id: str) -> Path:
    for base in DOCS:
        for path in (root / base).rglob(f"{artifact_id}-*.md"):
            m = ID_IN_NAME.match(path.name)
            if m and m.group(1) == artifact_id and "_templates" not in path.parts:
                return path
    raise FileNotFoundError(f"артефакт {artifact_id} не найден в {', '.join(DOCS)}")


def scalar(value: object) -> str:
    """Значение для YAML: числа и строки со спецсимволами в кавычках, чтобы читались строкой."""
    text = str(value)
    if re.fullmatch(r"[\w./-]+", text) and not re.fullmatch(r"[\d.]+", text):
        return text
    return '"' + text.replace('"', '\\"') + '"'


def set_external(path: Path, system: str, key: str) -> None:
    """Записать external.<system>: <key>, не трогая остальной frontmatter."""
    if not re.fullmatch(r"[a-z][a-z0-9-]*", system):
        raise ValueError(f"имя системы «{system}»")
    text = path.read_text(encoding="utf-8")
    lines, end = split(text)
    entry = f"  {system}: {scalar(key)}"
    for i in range(1, end):
        flow = re.match(r"^external:\s*(\{.*\S.*\})\s*$", lines[i])
        if flow:  # external: {jira: X} → блочная запись, чтобы дописывать построчно
            pairs = yaml.safe_load(flow.group(1)) or {}
            lines[i:i + 1] = ["external:"] + [f"  {k}: {scalar(v)}" for k, v in pairs.items()]
            end += len(pairs)
            break
    start = next((i for i in range(1, end) if re.match(r"^external:\s*(\{\s*\})?\s*$", lines[i])), None)
    if start is None:
        lines[end:end] = ["external:", entry]
    else:
        lines[start] = "external:"
        stop = start + 1
        while stop < end and lines[stop].startswith((" ", "\t")):
            stop += 1
        block = lines[start + 1:stop]
        for n, line in enumerate(block):
            if re.match(rf"^\s+{re.escape(system)}:", line):
                block[n] = entry
                break
        else:
            block.append(entry)
        lines[start + 1:stop] = block
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
