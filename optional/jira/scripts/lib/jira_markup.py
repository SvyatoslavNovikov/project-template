# -*- coding: utf-8 -*-
"""Markdown артефактов → разметка Jira wiki (поле description в REST API v2).

Покрывает то, что встречается в шаблонах: заголовки, списки (с вложенностью),
жирный и курсив, `код`, блоки ``` ```, ссылки, таблицы, цитаты. Остальное идёт как есть.
"""
from __future__ import annotations

import re

INLINE_CODE = re.compile(r"`([^`]+)`")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")


def inline(text: str) -> str:
    codes: list[str] = []

    def keep(m: re.Match) -> str:
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = INLINE_CODE.sub(keep, text)
    text = text.replace("\\<", "<").replace("\\>", ">")
    text = LINK.sub(lambda m: f"[{m.group(1)}|{m.group(2)}]", text)
    text = BOLD.sub(lambda m: f"\x01{m.group(1)}\x01", text)  # жирный прячем, чтобы курсив его не задел
    text = ITALIC.sub(lambda m: f"_{m.group(1)}_", text)
    text = text.replace("\x01", "*")
    return re.sub(r"\x00(\d+)\x00", lambda m: "{{" + codes[int(m.group(1))] + "}}", text)


def to_wiki(markdown: str) -> str:
    out: list[str] = []
    in_code = False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip()
            out.append("{code}" if in_code or not lang else f"{{code:{lang}}}")
            in_code = not in_code
            continue
        if in_code:
            out.append(line)
            continue
        if m := re.match(r"^(#{1,6})\s+(.*)$", line):
            out.append(f"h{len(m.group(1))}. {inline(m.group(2))}")
        elif re.match(r"^\s*\|?\s*:?-{3,}", line) and "|" in line:
            continue  # разделитель шапки таблицы
        elif line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            header = not out or not out[-1].startswith("|")
            sep = "||" if header else "|"
            out.append(sep + sep.join(inline(c) for c in cells) + sep)
        elif m := re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line):
            depth = len(m.group(1).replace("\t", "  ")) // 2 + 1
            mark = "#" if m.group(2)[0].isdigit() else "*"
            out.append(f"{mark * depth} {inline(m.group(3))}")
        elif line.startswith("> "):
            out.append(f"bq. {inline(line[2:])}")
        else:
            out.append(inline(line))
    return "\n".join(out).strip() + "\n"
