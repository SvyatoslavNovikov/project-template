# -*- coding: utf-8 -*-
"""Markdown ↔ storage-формат Confluence (XHTML).

  to_storage(markdown)  заголовки, абзацы, списки с вложенностью, таблицы, блоки кода
                        (макрос code), цитаты, жирный, курсив, `код`, ссылки
  to_text(storage)      читаемый текст страницы для контекста: заголовки «#», пункты «-»,
                        строки таблиц через « | », тело макросов кода
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

INLINE_CODE = re.compile(r"`([^`]+)`")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")


def inline(text: str) -> str:
    codes: list[str] = []

    def keep(m: re.Match) -> str:
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = INLINE_CODE.sub(keep, text.replace("\\<", "<").replace("\\>", ">"))
    text = html.escape(text, quote=False)
    text = LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)  # текст уже экранирован
    text = BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{html.escape(codes[int(m.group(1))], quote=False)}</code>", text)


def code_macro(lang: str, code: str) -> str:
    param = f'<ac:parameter ac:name="language">{html.escape(lang)}</ac:parameter>' if lang else ""
    body = code.replace("]]>", "]]]]><![CDATA[>")
    return (f'<ac:structured-macro ac:name="code">{param}'
            f"<ac:plain-text-body><![CDATA[{body}]]></ac:plain-text-body></ac:structured-macro>")


def to_storage(markdown: str) -> str:
    out: list[str] = []
    para: list[str] = []
    lists: list[str] = []  # стек открытых списков; на каждом уровне открыт <li>
    table: list[list[str]] = []
    code: list[str] | None = None
    lang = ""

    def flush_para():
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    def close_lists(depth: int = 0):
        while len(lists) > depth:
            out.append(f"</li></{lists.pop()}>")

    def flush_table():
        if table:
            rows = [f"<tr>{''.join(f'<th>{inline(c)}</th>' for c in table[0])}</tr>"]
            rows += [f"<tr>{''.join(f'<td>{inline(c)}</td>' for c in row)}</tr>" for row in table[1:]]
            out.append(f"<table><tbody>{''.join(rows)}</tbody></table>")
            table.clear()

    def flush_all():
        flush_para()
        close_lists()
        flush_table()

    for line in markdown.splitlines():
        if code is not None:
            if line.strip().startswith("```"):
                out.append(code_macro(lang, "\n".join(code)))
                code = None
            else:
                code.append(line)
            continue
        if line.strip().startswith("```"):
            flush_all()
            code, lang = [], line.strip()[3:].strip()
            continue
        if m := re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line):
            flush_para()
            flush_table()
            depth = len(m.group(1).replace("\t", "  ")) // 2 + 1
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            close_lists(depth)
            if len(lists) == depth and lists[-1] == tag:
                out.append(f"</li><li>{inline(m.group(3))}")
                continue
            if len(lists) == depth:
                close_lists(depth - 1)
            while len(lists) < depth - 1:
                out.append(f"<{tag}><li>")
                lists.append(tag)
            out.append(f"<{tag}><li>{inline(m.group(3))}")
            lists.append(tag)
            continue
        if line.strip().startswith("|"):
            flush_para()
            close_lists()
            if not re.match(r"^\s*\|?\s*:?-{3,}", line):
                table.append([c.strip() for c in line.strip().strip("|").split("|")])
            continue
        flush_table()
        if not line.strip():
            flush_para()
            close_lists()
        elif m := re.match(r"^(#{1,6})\s+(.*)$", line):
            flush_all()
            out.append(f"<h{len(m.group(1))}>{inline(m.group(2))}</h{len(m.group(1))}>")
        elif line.startswith("> "):
            flush_all()
            out.append(f"<blockquote><p>{inline(line[2:])}</p></blockquote>")
        else:
            close_lists()
            para.append(line.strip())
    if code is not None:
        out.append(code_macro(lang, "\n".join(code)))
    flush_all()
    return "".join(out)


class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "table", "blockquote", "ul", "ol"}
    SKIP = {"ac:parameter", "style", "script"}
    CODE = "ac:plain-text-body"

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.depth = 0
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == self.CODE:
            self.parts.append("\n")
        elif re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("ul", "ol"):
            self.depth += 1
        elif tag == "li":
            self.parts.append("\n" + "  " * (self.depth - 1) + "- ")
        elif tag in ("td", "th"):
            self.parts.append(" | ")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in ("ul", "ol"):
            self.depth = max(0, self.depth - 1)
        elif tag in ("p", "table", self.CODE) or re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def unknown_decl(self, data):
        if data.startswith("CDATA["):
            self.parts.append(data[6:])  # разрезанный «]]>» приходит несколькими кусками подряд


def to_text(storage: str) -> str:
    parser = _Text()
    parser.feed(storage)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
