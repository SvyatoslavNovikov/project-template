# -*- coding: utf-8 -*-
"""Разбор команды Bash/PowerShell для хуков: что именно запускается.

Хукам нужно отличать запуск скрипта от его упоминания (git add, grep, текст коммита).
segments() делит команду на простые команды по &&, ||, ;, | и переводам строк, не
заглядывая внутрь кавычек, here-doc (<<EOF) и here-string PowerShell (@'...'@).
У каждой простой команды:
  argv  — токены без внешних кавычек (первый — исполняемый файл, после &, ., call);
  text  — исходный текст;
  stdin — тело here-doc этой команды или текст предыдущего звена конвейера.
Разбор приблизительный: цель — не пропустить явный запуск и не реагировать на текст.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
PREFIX_TOKENS = {"&", ".", "call", "exec", "time", "command"}


@dataclass
class Segment:
    argv: list[str]
    text: str
    stdin: str | None = None
    exe: str = field(init=False)

    def __post_init__(self) -> None:
        first = self.argv[0] if self.argv else ""
        name = re.split(r"[\\/]", first)[-1].lower()
        self.exe = name[:-4] if name.endswith(".exe") else name


def _cut_heredocs(command: str) -> tuple[str, list[str]]:
    """Убирает тела here-doc из текста; на месте маркера остаётся __HEREDOC_n__."""
    lines = command.split("\n")
    out: list[str] = []
    bodies: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        found = list(HEREDOC_RE.finditer(line))
        if not found:
            out.append(line)
            i += 1
            continue
        for match in reversed(found):
            line = line[: match.start()] + f" __HEREDOC_{len(bodies) + found.index(match)}__ " + line[match.end():]
        out.append(line)
        i += 1
        for match in found:
            body: list[str] = []
            while i < len(lines) and lines[i].strip() != match.group(2):
                body.append(lines[i])
                i += 1
            i += 1  # строка-разделитель
            bodies.append("\n".join(body))
    return "\n".join(out), bodies


def _mask_quotes(text: str) -> tuple[str, list[str]]:
    """Заменяет строки в кавычках и here-string PowerShell на __Q_n__."""
    saved: list[str] = []
    result: list[str] = []
    i = 0
    while i < len(text):
        two = text[i:i + 2]
        if two in ("@'", '@"') and (i + 2 >= len(text) or text[i + 2] in "\r\n"):
            end = text.find("\n" + two[1] + "@", i + 2)
            end = len(text) if end == -1 else end + 3
            saved.append(text[i:end])
            result.append(f"__Q_{len(saved) - 1}__")
            i = end
            continue
        ch = text[i]
        if ch in "'\"":
            j = i + 1
            while j < len(text) and text[j] != ch:
                j += 2 if ch == '"' and text[j] in "\\`" else 1
            saved.append(text[i:j + 1])
            result.append(f"__Q_{len(saved) - 1}__")
            i = j + 1
            continue
        result.append(ch)
        i += 1
    return "".join(result), saved


def _restore(text: str, saved: list[str]) -> str:
    return re.sub(r"__Q_(\d+)__", lambda m: saved[int(m.group(1))], text)


def _unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return token[1:-1]
    if token.startswith(("@'", '@"')):
        return token[2:-2].strip("\r\n")
    return token


def _tokens(text: str) -> list[str]:
    try:
        lexer = shlex.shlex(text, posix=False, punctuation_chars=False)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return [_unquote(t) for t in lexer]
    except ValueError:
        return [_unquote(t) for t in text.split()]


def segments(command: str) -> list[Segment]:
    text, bodies = _cut_heredocs(command)
    masked, saved = _mask_quotes(text)
    result: list[Segment] = []
    previous_pipe: str | None = None
    for part in re.split(r"(\|\||&&|;|\n|\|)", masked):
        if part in ("||", "&&", ";", "\n", "|"):
            if part != "|":
                previous_pipe = None
            continue
        raw = _restore(part, saved).strip()
        if not raw:
            continue
        stdin = previous_pipe
        heredoc = re.search(r"__HEREDOC_(\d+)__", raw)
        if heredoc:
            stdin = bodies[int(heredoc.group(1))]
            raw = (raw[: heredoc.start()] + raw[heredoc.end():]).strip()
        argv = _tokens(raw)
        while argv and argv[0].lower() in PREFIX_TOKENS:
            argv = argv[1:]
        while argv and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", argv[0]):  # VAR=x cmd
            argv = argv[1:]
        if argv:
            result.append(Segment(argv, raw, stdin))
        previous_pipe = raw
    return result


def python_target(seg: Segment) -> tuple[str, str | None, list[str]]:
    """Для запуска python: (вид, скрипт или код, аргументы скрипта).

    вид: 'script' — файл .py; 'code' — python -c; 'stdin' — python - (код из here-doc/конвейера);
    'module' — python -m; '' — не python или ничего не запускает."""
    if not re.fullmatch(r"python[0-9.]*|py", seg.exe):
        return "", None, []
    args = seg.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-c":
            return "code", args[i + 1] if i + 1 < len(args) else "", []
        if arg == "-m":
            return "module", args[i + 1] if i + 1 < len(args) else "", args[i + 2:]
        if arg == "-":
            return "stdin", seg.stdin or "", args[i + 1:]
        if arg.startswith("-"):
            i += 1
            continue
        return "script", arg, args[i + 1:]
    return ("stdin", seg.stdin, []) if seg.stdin else ("", None, [])


def powershell_script(seg: Segment) -> str | None:
    """Путь к .ps1, если сегмент его запускает (pwsh -File x.ps1, & x.ps1, .\\x.ps1)."""
    if seg.exe.endswith(".ps1"):
        return seg.argv[0]
    if seg.exe in ("pwsh", "powershell"):
        for i, arg in enumerate(seg.argv[1:], start=1):
            if arg.lower() in ("-file", "-f") and i + 1 < len(seg.argv):
                return seg.argv[i + 1]
    return None


def git_paths(seg: Segment) -> tuple[str, list[str]]:
    """Для git add/commit: (подкоманда, пути-аргументы без значений -m/-F/--message/--file)."""
    if seg.exe != "git":
        return "", []
    args = seg.argv[1:]
    while args and args[0] in ("-C", "-c"):  # git -C <путь> add …
        args = args[2:]
    if not args or args[0] not in ("add", "commit"):
        return "", []
    sub, rest, paths = args[0], args[1:], []
    skip = False
    for arg in rest:
        if skip:
            skip = False
            continue
        if arg in ("--message", "--file", "--author", "--date") or re.fullmatch(r"-[a-zA-Z]*[mFCc]", arg):
            skip = True  # значение опции (-m, -am, -F …) — не путь
            continue
        if arg.startswith(("--message=", "--file=", "--author=", "--date=")) or arg.startswith("-"):
            continue
        paths.append(arg)
    return sub, paths
