# -*- coding: utf-8 -*-
"""Механика требований и тестов: `docs/requirements/` и `docs/tests/`.

Проверяет то, что считается по файлам без понимания текста, по правилам
docs/requirements/README.md, docs/requirements/TRACEABILITY.md и docs/tests/README.md:
  - имя файла, `id`, `type`, статус, приоритет, заголовок H1, префикс проекта, уникальность ID;
  - место в дереве и `parent` по папкам, допустимый тип родителя, взаимность `children`;
  - `links`: цель существует, допустимые пары типов, каноническая сторона, self-link;
  - ключи справочников (`releases`, `affects_releases`, `release`, `environment`);
  - `level` у SR и кейса, `mode` у прогона, `severity` у бага;
  - кейсы: `verifies` (сирота не даёт покрытия), verifies на obsolete-требование, заполненные
    «Шаги» и «Ожидаемый результат» с review; сьюит без obsolete-кейсов;
  - прогоны: состав `results`, `revision`, `outcome`, файлы `results/<кейс>.md`; поля бага `found_*`;
  - инварианты: у approved стори есть SR, у obsolete есть входящий supersedes,
    нет циклов в `depends-on`, пара conflicts-with не оба approved;
  - реестры: `Next` больше любого выданного номера.
Смысл (формулировки, противоречия, покрытие) проверяет агент `req-reviewer`.

  python .claude/hooks/docs_lint.py [пути]   проверить всё или только замечания по путям
  python .claude/hooks/docs_lint.py --hook   режим хука PostToolUse(Write|Edit): JSON из stdin

Нужен PyYAML (`pip install pyyaml`). Без него CLI завершается с кодом 2, хук молчит.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
REQ_TYPES = {"epic": "epic", "us": "user-story", "sr": "system-requirement", "nfr": "nfr", "bug": "bug"}
TEST_TYPES = {"tc": "test-case", "ts": "test-suite", "tr": "test-run"}
REQ_STATUS = {"draft", "review", "approved", "implemented", "obsolete"}
STATUSES = {
    "epic": REQ_STATUS, "user-story": REQ_STATUS, "system-requirement": REQ_STATUS, "nfr": REQ_STATUS,
    "bug": {"open", "in-progress", "fixed", "verified", "closed", "rejected"},
    "test-case": {"draft", "review", "approved", "automated", "obsolete"},
    "test-suite": {"draft", "review", "approved", "obsolete"},
    "test-run": {"planned", "in-progress", "completed", "aborted"},
}
RESULT_STATUS = {"passed", "failed", "blocked", "skipped", "not-run"}
PRIORITY = {"must", "should", "could"}
CASE_LEVELS = ("unit", "api", "ui", "e2e")
SR_LEVELS = ("functional", "data", "api", "ui", "integration")
RUN_MODES = ("manual", "automated")
SEVERITY = ("blocker", "major", "minor", "trivial")
COVERING = ("approved", "automated")  # статусы кейса, которые дают покрытие
CASE_SECTIONS = ("Шаги", "Ожидаемый результат")
PLACEHOLDER = re.compile(r"^(?:[-*]|\d+\.)?\s*(?:…|\.\.\.)?\s*$")
PARENT_TYPES = {"user-story": {"epic"}, "system-requirement": {"user-story"}, "nfr": {"user-story", "epic"}}
SPEC = {"system-requirement", "nfr"}
# тип связи -> (допустимые типы источника, допустимые типы цели); None — любой
LINK_RULES = {
    "verifies": ({"test-case"}, SPEC),
    "contains": ({"test-suite"}, {"test-case"}),
    "executes": ({"test-run"}, {"test-suite"}),
    "defects": ({"bug"}, SPEC),
    "constrains": ({"nfr"}, {"user-story", "system-requirement"}),
    "implemented-in": ({"user-story", "system-requirement", "nfr"}, None),
    "depends-on": (None, None),
    "supersedes": (None, None),
    "relates-to": (None, None),
    "conflicts-with": (None, None),
}
NAME_RE = re.compile(r"^([A-Z][A-Z0-9]*)-(T-)?(\d+)-([a-z]+)-([a-z0-9]+(?:-[a-z0-9]+)*)$")
ID_RE = re.compile(r"^([A-Z][A-Z0-9]*)-(T-)?(\d+)$")


@dataclass
class Issue:
    path: Path
    line: int
    level: str  # error | warn
    message: str

    def render(self) -> str:
        return f"{rel(self.path)}:{self.line}: {self.level}: {self.message}"


@dataclass
class Artifact:
    path: Path
    stem: str
    prefix: str
    space: str  # req | test
    num: int
    code: str
    text: str
    fm: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.prefix}-{'T-' if self.space == 'test' else ''}{self.num}"

    @property
    def type(self) -> str:
        return (REQ_TYPES if self.space == "req" else TEST_TYPES).get(self.code, "")

    def line(self, needle: str) -> int:
        for n, line in enumerate(self.text.splitlines(), 1):
            if needle in line:
                return n
        return 1


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_list(value) -> list:
    if value in (None, ""):
        return []
    return value if isinstance(value, list) else [value]


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    """Frontmatter как dict или None и текст ошибки."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "нет frontmatter (первая строка не ---)"
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, "frontmatter не закрыт строкой ---"
    try:
        data = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError as exc:
        return None, f"frontmatter не разбирается как YAML: {str(exc).splitlines()[0]}"
    if not isinstance(data, dict):
        return None, "frontmatter не словарь"
    return data, ""


def catalog_keys(name: str) -> set[str]:
    path = ROOT / "docs" / "requirements" / "_catalogs" / name
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    keys, in_table = set(), False
    for line in text.splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and cells and cells[0] == "key":
            in_table = True
            continue
        if in_table and line.lstrip().startswith("|"):
            if cells[0] and not set(cells[0]) <= set("-: "):
                keys.add(cells[0])
        elif in_table:
            in_table = False
    return keys


def registry(path: Path) -> tuple[str | None, int | None, int | None]:
    """Префикс, Last issued, Next из реестра."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None, None, None
    prefix = re.search(r"`([A-Z][A-Z0-9]*)-(?:T-)?<n>`", text)
    last = re.search(r"\|\s*Last issued\s*\|\s*(\d+)\s*\|", text)
    nxt = re.search(r"\|\s*Next\s*\|\s*(\d+)\s*\|", text)
    return (prefix.group(1) if prefix else None,
            int(last.group(1)) if last else None,
            int(nxt.group(1)) if nxt else None)


def artifact_files() -> list[Path]:
    req, tests = ROOT / "docs" / "requirements", ROOT / "docs" / "tests"
    files = sorted((req / "epics").rglob("*.md")) + sorted((req / "bugs").glob("*.md"))
    files += sorted((tests / "cases").glob("*.md")) + sorted((tests / "suites").glob("*.md"))
    files += sorted(p for p in (tests / "runs").glob("*/*.md"))
    return files


class Linter:
    def __init__(self):
        self.issues: list[Issue] = []
        self.by_id: dict[str, Artifact] = {}
        self.arts: list[Artifact] = []
        self.releases = catalog_keys("releases.md")
        self.environments = catalog_keys("environments.md")
        self.req_registry = ROOT / "docs" / "requirements" / "_registry.md"
        self.test_registry = ROOT / "docs" / "tests" / "_registry.md"
        self.prefix = registry(self.req_registry)[0]

    def add(self, path: Path, line: int, level: str, message: str) -> None:
        self.issues.append(Issue(path, line, level, message))

    # ---------- загрузка

    def load(self) -> None:
        for path in artifact_files():
            m = NAME_RE.match(path.stem)
            space = "test" if path.is_relative_to(ROOT / "docs" / "tests") else "req"
            if not m or bool(m.group(2)) != (space == "test"):
                expected = "<PRJ>-T-<n>-<tc|ts|tr>-<slug>.md" if space == "test" else "<PRJ>-<n>-<тип>-<slug>.md"
                self.add(path, 1, "error", f"имя файла не по правилу {expected} (slug латиницей через дефисы)")
                continue
            text = path.read_text(encoding="utf-8")
            art = Artifact(path, path.stem, m.group(1), space, int(m.group(3)), m.group(4), text)
            if not art.type:
                self.add(path, 1, "error", f"неизвестный код типа «{art.code}» в имени файла")
                continue
            if m.group(3).startswith("0"):
                self.add(path, 1, "error", "номер с ведущим нулём")
            fm, error = split_frontmatter(text)
            if fm is None:
                self.add(path, 1, "error", error)
                continue
            art.fm = fm
            if art.id in self.by_id:
                self.add(path, 1, "error", f"ID {art.id} уже занят: {rel(self.by_id[art.id].path)}")
                continue
            self.by_id[art.id] = art
            self.arts.append(art)

    # ---------- проверки одного файла

    def check_identity(self, a: Artifact) -> None:
        if self.prefix and a.prefix != self.prefix:
            self.add(a.path, 1, "error", f"префикс {a.prefix}, в реестре {self.prefix}")
        if str(a.fm.get("id", "")) != a.id:
            self.add(a.path, a.line("id:"), "error", f"id «{a.fm.get('id', '')}» не совпадает с именем файла ({a.id})")
        if a.fm.get("type") != a.type:
            self.add(a.path, a.line("type:"), "error", f"type «{a.fm.get('type', '')}», по имени файла — {a.type}")
        status = a.fm.get("status")
        if status not in STATUSES[a.type]:
            self.add(a.path, a.line("status:"), "error",
                     f"status «{status}» не из списка: {', '.join(sorted(STATUSES[a.type]))}")
        if "priority" in a.fm and a.fm["priority"] not in PRIORITY:
            self.add(a.path, a.line("priority:"), "error", f"priority «{a.fm['priority']}»: must | should | could")
        heading = next((l[2:].strip() for l in a.text.splitlines() if l.startswith("# ")), None)
        if heading != a.stem:
            self.add(a.path, a.line("# "), "warn", f"заголовок H1 «{heading}» не совпадает с именем файла")

    def folder_parent(self, a: Artifact) -> tuple[bool, str | None]:
        """Лежит ли файл на своём месте и stem родителя по папкам."""
        parts = a.path.relative_to(ROOT / "docs" / ("requirements" if a.space == "req" else "tests")).parts
        name = a.stem + ".md"
        layouts = {
            "epic": [(("epics", a.stem, name), None)],
            "user-story": [(("epics", "*", "stories", a.stem, name), 1)],
            "system-requirement": [(("epics", "*", "stories", "*", "requirements", name), 3)],
            "nfr": [(("epics", "*", "stories", "*", "requirements", name), 3),
                    (("epics", "*", "requirements", name), 1)],
            "bug": [(("bugs", name), None)],
            "test-case": [(("cases", name), None)],
            "test-suite": [(("suites", name), None)],
            "test-run": [(("runs", a.stem, name), None)],
        }[a.type]
        for layout, parent_index in layouts:
            if len(parts) == len(layout) and all(x == "*" or x == p for x, p in zip(layout, parts)):
                return True, parts[parent_index] if parent_index is not None else None
        return False, None

    def check_tree(self, a: Artifact) -> None:
        placed, parent_stem = self.folder_parent(a)
        if not placed:
            self.add(a.path, 1, "error", f"{a.type} лежит не на своём месте (см. структуру в README каталога)")
        parent = a.fm.get("parent") or ""
        if a.type not in PARENT_TYPES:
            if parent:
                self.add(a.path, a.line("parent:"), "error", f"у {a.type} parent должен быть пустым")
        else:
            if not parent:
                self.add(a.path, a.line("parent:"), "error", "parent не заполнен")
            elif parent not in self.by_id:
                self.add(a.path, a.line("parent:"), "error", f"parent {parent} не найден")
            else:
                p = self.by_id[parent]
                if p.type not in PARENT_TYPES[a.type]:
                    self.add(a.path, a.line("parent:"), "error",
                             f"parent {parent} — {p.type}, допустимо: {', '.join(sorted(PARENT_TYPES[a.type]))}")
                if placed and parent_stem and p.stem != parent_stem:
                    self.add(a.path, a.line("parent:"), "error",
                             f"parent {parent}, а файл лежит в папке {parent_stem}")
                if a.id not in [str(c) for c in as_list(p.fm.get("children"))]:
                    self.add(a.path, a.line("parent:"), "error", f"родитель {parent} не перечисляет {a.id} в children")
        for child in as_list(a.fm.get("children")):
            c = self.by_id.get(str(child))
            if c is None:
                self.add(a.path, a.line(str(child)), "error", f"в children {child}: такого артефакта нет")
            elif c.fm.get("parent") != a.id:
                self.add(a.path, a.line(str(child)), "error",
                         f"в children {child}, но его parent — «{c.fm.get('parent') or ''}»")

    def check_catalogs(self, a: Artifact) -> None:
        for key in ("releases", "affects_releases", "release"):
            for value in as_list(a.fm.get(key)):
                if str(value) not in self.releases:
                    self.add(a.path, a.line(f"{key}:"), "error", f"{key}: «{value}» нет в _catalogs/releases.md")
        env = a.fm.get("environment")
        if env and str(env) not in self.environments:
            self.add(a.path, a.line("environment:"), "error", f"environment «{env}» нет в _catalogs/environments.md")

    def check_links(self, a: Artifact) -> None:
        for link in as_list(a.fm.get("links")):
            if not isinstance(link, dict) or "type" not in link or "to" not in link:
                self.add(a.path, a.line("links:"), "error", f"связь без type или to: {link}")
                continue
            kind, to = link["type"], str(link["to"])
            line = a.line(f"to: {to}")
            if kind not in LINK_RULES:
                self.add(a.path, a.line(f"type: {kind}"), "error", f"тип связи «{kind}» не из TRACEABILITY.md")
                continue
            sources, targets = LINK_RULES[kind]
            if sources and a.type not in sources:
                self.add(a.path, line, "error", f"{kind} ставится на стороне {', '.join(sorted(sources))}, не {a.type}")
            if kind == "implemented-in" and to.startswith("code:"):
                continue
            t = self.by_id.get(to)
            if t is None:
                self.add(a.path, line, "error", f"{kind} → {to}: такого артефакта нет")
                continue
            if t is a:
                self.add(a.path, line, "error", f"{kind} на самого себя")
                continue
            if targets and t.type not in targets:
                self.add(a.path, line, "error", f"{kind} → {to} ({t.type}), допустимо: {', '.join(sorted(targets))}")
            if kind in ("depends-on", "supersedes") and t.type != a.type:
                self.add(a.path, line, "error", f"{kind} связывает артефакты одного типа, а здесь {a.type} → {t.type}")
            if kind == "supersedes" and t.fm.get("status") != "obsolete":
                self.add(a.path, line, "warn", f"{to} заменён, но его статус не obsolete")
            if kind in ("relates-to", "conflicts-with"):
                if a.space == "req" and t.space == "test":
                    self.add(a.path, line, "error", f"{kind} между требованием и тестом пишется на стороне теста")
                elif a.space == t.space and a.num > t.num:
                    self.add(a.path, line, "warn", f"{kind} пишется у меньшего ID ({to}), обратную сторону не дублируют")
            if kind == "conflicts-with" and a.fm.get("status") == "approved" and t.fm.get("status") == "approved":
                self.add(a.path, line, "error", f"conflicts-with: {a.id} и {to} оба approved")

    def check_bug(self, a: Artifact) -> None:
        if a.fm.get("severity") not in SEVERITY:
            self.add(a.path, a.line("severity:"), "error", f"severity «{a.fm.get('severity') or ''}»: {' | '.join(SEVERITY)}")
        for key, kind in (("found_in", "test-run"), ("found_on", "test-case")):
            value = a.fm.get(key)
            if value and (str(value) not in self.by_id or self.by_id[str(value)].type != kind):
                self.add(a.path, a.line(f"{key}:"), "error", f"{key}: {value} должен быть существующим {kind}")

    def section_filled(self, a: Artifact, title: str) -> bool | None:
        """Есть ли в секции «## title» что-то кроме заглушек шаблона; None — секции нет."""
        found, body = False, []
        for line in a.text.splitlines():
            if line.startswith("## "):
                if found:
                    break
                found = line[3:].strip() == title
                continue
            if found:
                body.append(line.strip())
        if not found:
            return None
        return any(not PLACEHOLDER.match(line) for line in body)

    def check_case(self, a: Artifact) -> None:
        status = a.fm.get("status")
        if a.fm.get("level") not in CASE_LEVELS:
            self.add(a.path, a.line("level:"), "error", f"level «{a.fm.get('level') or ''}»: {' | '.join(CASE_LEVELS)}")
        verifies = [str(l.get("to")) for l in as_list(a.fm.get("links"))
                    if isinstance(l, dict) and l.get("type") == "verifies"]
        if not verifies and status != "obsolete":
            self.add(a.path, a.line("links:"), "error" if status in COVERING else "warn",
                     "нет verifies: кейс-сирота, в покрытие не идёт")
        for to in verifies:
            t = self.by_id.get(to)
            if t and t.fm.get("status") == "obsolete" and status != "obsolete":
                self.add(a.path, a.line(f"to: {to}"), "warn", f"verifies → {to}, а требование obsolete")
        if status in ("review",) + COVERING:
            for title in CASE_SECTIONS:
                filled = self.section_filled(a, title)
                if not filled:
                    self.add(a.path, a.line(f"## {title}"), "error" if status in COVERING else "warn",
                             f"секция «{title}» {'отсутствует' if filled is None else 'пустая'}, а кейс {status}")

    def check_suite(self, a: Artifact) -> None:
        if a.fm.get("status") == "obsolete":
            return
        for link in as_list(a.fm.get("links")):
            if isinstance(link, dict) and link.get("type") == "contains":
                t = self.by_id.get(str(link.get("to")))
                if t and t.fm.get("status") == "obsolete":
                    self.add(a.path, a.line(f"to: {link.get('to')}"), "warn",
                             f"сьюит содержит obsolete-кейс {link.get('to')}")

    def check_run(self, a: Artifact) -> None:
        status = a.fm.get("status")
        if a.fm.get("mode") not in RUN_MODES:
            self.add(a.path, a.line("mode:"), "error", f"mode «{a.fm.get('mode') or ''}»: {' | '.join(RUN_MODES)}")
        seen, statuses = set(), []
        for row in as_list(a.fm.get("results")):
            if not isinstance(row, dict):
                self.add(a.path, a.line("results:"), "error", f"строка results не словарь: {row}")
                continue
            case, st, defect = str(row.get("case", "")), row.get("status"), row.get("defect")
            line = a.line(f"case: {case}")
            if case in seen:
                self.add(a.path, line, "error", f"кейс {case} в results дважды")
            seen.add(case)
            if case not in self.by_id or self.by_id[case].type != "test-case":
                self.add(a.path, line, "error", f"results: {case} не существующий test-case")
            if st not in RESULT_STATUS:
                self.add(a.path, line, "error", f"results[{case}].status «{st}» не из списка")
            statuses.append(st)
            if defect and (str(defect) not in self.by_id or self.by_id[str(defect)].type != "bug"):
                self.add(a.path, line, "error", f"results[{case}].defect {defect} не существующий bug")
        if status in ("in-progress", "completed") and not a.fm.get("revision"):
            self.add(a.path, a.line("revision:"), "error", f"прогон {status}, а revision пуст")
        if status == "completed":
            expected = ("failed" if "failed" in statuses else "blocked" if "blocked" in statuses
                        else "passed" if "not-run" not in statuses else "")
            if expected and a.fm.get("outcome") != expected:
                self.add(a.path, a.line("outcome:"), "error", f"outcome «{a.fm.get('outcome') or ''}», по results — {expected}")
            if not a.fm.get("environment"):
                self.add(a.path, a.line("environment:"), "warn", "пустой environment допустим только у чернового прогона")
        elif a.fm.get("outcome"):
            self.add(a.path, a.line("outcome:"), "warn", "outcome заполнен, а прогон не completed")
        results_dir = a.path.parent / "results"
        for path in sorted(results_dir.glob("*.md")) if results_dir.is_dir() else []:
            if path.stem not in seen:
                self.add(path, 1, "error", f"результат {path.stem}: такого кейса нет в results прогона {a.id}")
            fm, error = split_frontmatter(path.read_text(encoding="utf-8"))
            if fm is None:
                self.add(path, 1, "error", error)
            elif str(fm.get("case", "")) != path.stem:
                self.add(path, 1, "error", f"case «{fm.get('case', '')}» не совпадает с именем файла")

    # ---------- проверки по всему набору

    def check_invariants(self) -> None:
        superseded = {str(l.get("to")) for a in self.arts for l in as_list(a.fm.get("links"))
                      if isinstance(l, dict) and l.get("type") == "supersedes"}
        for a in self.arts:
            if a.type == "user-story" and a.fm.get("status") == "approved":
                if not any(self.by_id.get(str(c)) and self.by_id[str(c)].type == "system-requirement"
                           for c in as_list(a.fm.get("children"))):
                    self.add(a.path, a.line("status:"), "error", "approved стори без единого SR в children")
            if a.fm.get("status") == "obsolete" and a.id not in superseded:
                self.add(a.path, a.line("status:"), "error", "obsolete без входящего supersedes")
        graph = {a.id: [str(l.get("to")) for l in as_list(a.fm.get("links"))
                        if isinstance(l, dict) and l.get("type") == "depends-on"] for a in self.arts}
        state: dict[str, int] = {}

        def visit(node: str, stack: list[str]) -> None:
            state[node] = 1
            for nxt in graph.get(node, []):
                if state.get(nxt) == 1:
                    cycle = stack[stack.index(nxt):] + [nxt] if nxt in stack else [node, nxt]
                    self.add(self.by_id[node].path, self.by_id[node].line(f"to: {nxt}"), "error",
                             "цикл depends-on: " + " → ".join(cycle))
                elif nxt in graph and not state.get(nxt):
                    visit(nxt, stack + [nxt])
            state[node] = 2

        for node in graph:
            if not state.get(node):
                visit(node, [node])

    def check_registries(self) -> None:
        for path, space in ((self.req_registry, "req"), (self.test_registry, "test")):
            _, last, nxt = registry(path)
            if nxt is None:
                self.add(path, 1, "error", "в реестре не найдено поле Next")
                continue
            nums = [a.num for a in self.arts if a.space == space]
            top = max(nums, default=0)
            if nxt <= top:
                self.add(path, 1, "error", f"Next = {nxt}, а уже выдан номер {top}: сдвиньте реестр")
            if last is not None and last != top:
                self.add(path, 1, "warn", f"Last issued = {last}, наибольший номер в файлах — {top}")
            if last is not None and nxt != last + 1:
                self.add(path, 1, "warn", f"Next ({nxt}) не равен Last issued + 1 ({last + 1})")

    def run(self) -> list[Issue]:
        self.load()
        for a in self.arts:
            self.check_identity(a)
            self.check_tree(a)
            self.check_catalogs(a)
            self.check_links(a)
            if a.type == "bug":
                self.check_bug(a)
            if a.type == "test-run":
                self.check_run(a)
            if a.type == "test-case":
                self.check_case(a)
            if a.type == "test-suite":
                self.check_suite(a)
            if a.type == "system-requirement" and a.fm.get("level") not in SR_LEVELS:
                self.add(a.path, a.line("level:"), "error", f"level «{a.fm.get('level') or ''}»: {' | '.join(SR_LEVELS)}")
        self.check_invariants()
        self.check_registries()
        return sorted(self.issues, key=lambda i: (rel(i.path), i.line))


def under(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved == r or r in resolved.parents for r in roots)


def hook() -> int:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path or yaml is None:
        return 0
    path = Path(file_path).resolve()
    docs = [(ROOT / "docs" / "requirements").resolve(), (ROOT / "docs" / "tests").resolve()]
    if path.suffix != ".md" or not under(path, docs) or "_templates" in path.parts or "_catalogs" in path.parts:
        return 0
    space_root = next(d for d in docs if under(path, [d]))
    issues = [i for i in Linter().run()
              if i.path.resolve() == path or (i.path.resolve() == space_root / "_registry.md")]
    if issues:
        text = (f"docs_lint: {rel(path)}\n" + "\n".join("  " + i.render() for i in issues[:20])
                + (f"\n  … ещё {len(issues) - 20}" if len(issues) > 20 else ""))
        print(json.dumps({
            "systemMessage": text,
            "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text},
        }, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--hook"]:
        return hook()
    sys.stdout.reconfigure(encoding="utf-8")
    if yaml is None:
        print("docs_lint: нужен PyYAML — pip install pyyaml", file=sys.stderr)
        return 2
    issues = Linter().run()
    if argv:
        roots = [Path(p).resolve() for p in argv]
        issues = [i for i in issues if under(i.path, roots)]
    for issue in issues:
        print(issue.render())
    errors = sum(i.level == "error" for i in issues)
    warns = len(issues) - errors
    print(f"ошибок: {errors}, предупреждений: {warns}" if issues else "замечаний нет")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
