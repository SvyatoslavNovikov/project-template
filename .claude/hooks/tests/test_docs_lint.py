# -*- coding: utf-8 -*-
"""docs_lint: механика требований и тестов на временном репозитории.

Запуск из корня репозитория:  python -m unittest discover -s .claude/hooks/tests -v
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "docs_lint.py"

REGISTRY = "Сквозной счётчик `{p}-<n>`\n\n| Поле | Значение |\n|---|---|\n| Last issued | {last} |\n| Next | {next} |\n"
CATALOG = "| key | name | status |\n|---|---|---|\n{rows}\n\n`status`: x\n"

EPIC = "epics/ACME-1-epic-core/ACME-1-epic-core.md"
US = "epics/ACME-1-epic-core/stories/ACME-2-us-login/ACME-2-us-login.md"
SR = "epics/ACME-1-epic-core/stories/ACME-2-us-login/requirements/ACME-3-sr-auth.md"
NFR = "epics/ACME-1-epic-core/requirements/ACME-4-nfr-speed.md"
BUG = "bugs/ACME-5-bug-crash.md"
TC = "cases/ACME-T-1-tc-auth.md"
TS = "suites/ACME-T-2-ts-smoke.md"
TR = "runs/ACME-T-3-tr-smoke/ACME-T-3-tr-smoke.md"


def doc(stem: str, _body: str = "", **fm) -> str:
    """Frontmatter из fm, затем H1 и тело (_body)."""
    lines = ["---"]
    for key, value in fm.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines + ["---", "", f"# {stem}", "", _body])


CASE_BODY = "## Цель\n\nВход.\n\n## Шаги\n\n1. Открыть форму.\n\n## Ожидаемый результат\n\n- Форма открыта.\n"
TEMPLATE_BODY = "## Шаги\n\n1. …\n2. …\n\n## Ожидаемый результат\n\n- …\n"


def valid_repo() -> dict[str, str]:
    """Согласованный набор: каждая проверка в тестах ломает его в одном месте."""
    return {
        EPIC: dict(id="ACME-1", type="epic", status="approved", parent="", children=["ACME-2", "ACME-4"],
                   priority="must", releases=["1.0"], links=[]),
        US: dict(id="ACME-2", type="user-story", status="approved", parent="ACME-1", children=["ACME-3"],
                 priority="must", releases=["1.0"], links=[]),
        SR: dict(id="ACME-3", type="system-requirement", status="approved", parent="ACME-2", children=[],
                 priority="must", level="functional", links=[{"type": "implemented-in", "to": "code:src/auth"}]),
        NFR: dict(id="ACME-4", type="nfr", status="draft", parent="ACME-1", children=[], priority="should",
                  links=[{"type": "constrains", "to": "ACME-3"}]),
        BUG: dict(id="ACME-5", type="bug", status="open", parent="", children=[], environment="stage",
                  affects_releases=["1.0"], found_in="ACME-T-3", found_on="ACME-T-1",
                  links=[{"type": "defects", "to": "ACME-3"}]),
        TC: dict(id="ACME-T-1", type="test-case", status="approved", priority="must", level="ui",
                 links=[{"type": "verifies", "to": "ACME-3"}], _body=CASE_BODY),
        TS: dict(id="ACME-T-2", type="test-suite", status="approved", priority="should",
                 links=[{"type": "contains", "to": "ACME-T-1"}, {"type": "relates-to", "to": "ACME-1"}]),
        TR: dict(id="ACME-T-3", type="test-run", status="completed", outcome="failed", mode="automated",
                 release="1.0", revision="abc123", environment="stage",
                 links=[{"type": "executes", "to": "ACME-T-2"}],
                 results=[{"case": "ACME-T-1", "status": "failed", "defect": "ACME-5"}]),
    }


class DocsLintCase(unittest.TestCase):
    def build(self, files: dict, registries=((5, 6), (3, 4)), extra: dict[str, str] | None = None) -> Path:
        tmp = Path(self.tmpdir.name) / f"repo{len(list(Path(self.tmpdir.name).iterdir()))}"
        hooks = tmp / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        shutil.copy(HOOK, hooks / "docs_lint.py")
        req, tests = tmp / "docs" / "requirements", tmp / "docs" / "tests"
        (req / "_catalogs").mkdir(parents=True)
        tests.mkdir(parents=True)
        (req / "_registry.md").write_text(REGISTRY.format(p="ACME", last=registries[0][0], next=registries[0][1]), encoding="utf-8")
        (tests / "_registry.md").write_text(REGISTRY.format(p="ACME-T", last=registries[1][0], next=registries[1][1]), encoding="utf-8")
        (req / "_catalogs" / "releases.md").write_text(CATALOG.format(rows="| 1.0 | Первый | released |"), encoding="utf-8")
        (req / "_catalogs" / "environments.md").write_text(CATALOG.format(rows="| stage | Стейдж | active |"), encoding="utf-8")
        for path, fm in files.items():
            base = tests if path.startswith(("cases", "suites", "runs")) else req
            target = base / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(fm if isinstance(fm, str) else doc(Path(path).stem, **fm), encoding="utf-8")
        for path, text in (extra or {}).items():
            (tmp / path).parent.mkdir(parents=True, exist_ok=True)
            (tmp / path).write_text(text, encoding="utf-8")
        return tmp

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def lint(self, root: Path, *args: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(root / ".claude" / "hooks" / "docs_lint.py"), *args],
                              capture_output=True, text=True, encoding="utf-8", cwd=root)
        return proc.returncode, proc.stdout

    def assertFinds(self, files: dict, fragment: str, **kwargs):
        code, out = self.lint(self.build(files, **kwargs))
        self.assertIn(fragment, out)
        return code, out


class ValidRepoTest(DocsLintCase):
    def test_valid_repo_passes(self):
        code, out = self.lint(self.build(valid_repo()))
        self.assertEqual((code, out.strip()), (0, "замечаний нет"))

    def test_empty_repo_passes(self):
        code, out = self.lint(self.build({}, registries=((0, 1), (0, 1))))
        self.assertEqual(code, 0, out)


class BrokenRepoTest(DocsLintCase):
    def mutate(self, path: str, **changes) -> dict:
        files = valid_repo()
        files[path] = {**files[path], **changes}
        return files

    def test_identity(self):
        self.assertFinds(self.mutate(SR, id="ACME-30"), "не совпадает с именем файла")
        self.assertFinds(self.mutate(SR, type="nfr"), "по имени файла — system-requirement")
        self.assertFinds(self.mutate(TC, status="implemented"), "status «implemented» не из списка")
        self.assertFinds(self.mutate(US, priority="high"), "priority «high»")

    def test_bad_names(self):
        files = valid_repo()
        files["bugs/acme-6-bug-x.md"] = files.pop(BUG)
        self.assertFinds(files, "имя файла не по правилу")
        files = valid_repo()
        files["cases/ACME-T-01-tc-auth.md"] = files.pop(TC)
        self.assertFinds(files, "ведущим нулём")

    def test_duplicate_id(self):
        files = valid_repo()
        files["bugs/ACME-3-bug-dup.md"] = dict(id="ACME-3", type="bug", status="open", parent="", children=[], links=[])
        self.assertFinds(files, "ID ACME-3 уже занят")

    def test_tree(self):
        self.assertFinds(self.mutate(US, children=[]), "родитель ACME-2 не перечисляет ACME-3")
        self.assertFinds(self.mutate(EPIC, children=["ACME-2", "ACME-4", "ACME-9"]), "в children ACME-9: такого артефакта нет")
        self.assertFinds(self.mutate(SR, parent="ACME-1"), "parent ACME-1 — epic")
        self.assertFinds(self.mutate(BUG, parent="ACME-1"), "у bug parent должен быть пустым")
        files = valid_repo()
        files["epics/ACME-1-epic-core/ACME-3-sr-auth.md"] = files.pop(SR)
        self.assertFinds(files, "лежит не на своём месте")

    def test_catalogs(self):
        self.assertFinds(self.mutate(US, releases=["2.0"]), "releases: «2.0» нет")
        self.assertFinds(self.mutate(TR, environment="prod"), "environment «prod» нет")

    def test_links(self):
        self.assertFinds(self.mutate(TC, links=[{"type": "verifies", "to": "ACME-2"}]), "verifies → ACME-2 (user-story)")
        self.assertFinds(self.mutate(SR, links=[{"type": "verifies", "to": "ACME-3"}]), "verifies ставится на стороне test-case")
        self.assertFinds(self.mutate(SR, links=[{"type": "depends-on", "to": "ACME-2"}]), "depends-on связывает артефакты одного типа")
        self.assertFinds(self.mutate(SR, links=[{"type": "blocks", "to": "ACME-2"}]), "тип связи «blocks»")
        self.assertFinds(self.mutate(SR, links=[{"type": "relates-to", "to": "ACME-99"}]), "такого артефакта нет")
        self.assertFinds(self.mutate(SR, links=[{"type": "relates-to", "to": "ACME-T-1"}]), "пишется на стороне теста")
        self.assertFinds(self.mutate(NFR, links=[{"type": "relates-to", "to": "ACME-3"}]), "пишется у меньшего ID")

    def test_invariants(self):
        self.assertFinds(self.mutate(US, children=[]), "approved стори без единого SR")
        self.assertFinds(self.mutate(NFR, status="obsolete"), "obsolete без входящего supersedes")
        files = valid_repo()
        files[US]["children"] = ["ACME-3", "ACME-6", "ACME-7"]
        base = "epics/ACME-1-epic-core/stories/ACME-2-us-login/requirements/"
        for n, other in ((6, 7), (7, 6)):
            files[f"{base}ACME-{n}-sr-x{n}.md"] = dict(
                id=f"ACME-{n}", type="system-requirement", status="draft", parent="ACME-2", children=[],
                links=[{"type": "depends-on", "to": f"ACME-{other}"}])
        self.assertFinds(files, "цикл depends-on", registries=((7, 8), (3, 4)))
        files = self.mutate(NFR, status="approved")
        files[SR] = {**files[SR], "links": [{"type": "conflicts-with", "to": "ACME-4"}]}
        self.assertFinds(files, "оба approved")

    def test_runs_and_bugs(self):
        self.assertFinds(self.mutate(TR, outcome="passed"), "по results — failed")
        self.assertFinds(self.mutate(TR, revision=""), "revision пуст")
        self.assertFinds(self.mutate(TR, results=[{"case": "ACME-T-2", "status": "passed"}]), "не существующий test-case")
        self.assertFinds(self.mutate(TR, results=[{"case": "ACME-T-1", "status": "ok"}]), "status «ok» не из списка")
        self.assertFinds(self.mutate(BUG, found_on="ACME-T-2"), "found_on: ACME-T-2 должен быть существующим test-case")
        code, out = self.lint(self.build(valid_repo(), extra={
            "docs/tests/runs/ACME-T-3-tr-smoke/results/ACME-T-9.md": "---\ncase: ACME-T-9\n---\n"}))
        self.assertIn("такого кейса нет в results", out)

    def test_levels_and_modes(self):
        self.assertFinds(self.mutate(TC, level="manual"), "level «manual»: unit | api | ui | e2e")
        self.assertFinds(self.mutate(SR, level=""), "level «»: functional")
        self.assertFinds(self.mutate(TR, mode="auto"), "mode «auto»: manual | automated")

    def test_case_coverage(self):
        code, _ = self.assertFinds(self.mutate(TC, links=[]), "error: нет verifies")
        self.assertEqual(code, 1)  # approved-кейс без verifies обещает покрытие, которого нет
        code, _ = self.assertFinds(self.mutate(TC, status="draft", links=[]), "warn: нет verifies")
        self.assertEqual(code, 0)
        files = self.mutate(NFR, status="obsolete")
        files["epics/ACME-1-epic-core/requirements/ACME-6-nfr-speed2.md"] = dict(
            id="ACME-6", type="nfr", status="draft", parent="ACME-1", children=[],
            links=[{"type": "supersedes", "to": "ACME-4"}, {"type": "constrains", "to": "ACME-3"}])
        files[EPIC]["children"] = ["ACME-2", "ACME-4", "ACME-6"]
        files[TC] = {**files[TC], "links": [{"type": "verifies", "to": "ACME-3"}, {"type": "verifies", "to": "ACME-4"}]}
        self.assertFinds(files, "verifies → ACME-4, а требование obsolete", registries=((6, 7), (3, 4)))

    def test_case_sections(self):
        code, out = self.assertFinds(self.mutate(TC, _body=TEMPLATE_BODY), "секция «Шаги» пустая, а кейс approved")
        self.assertIn("секция «Ожидаемый результат» пустая", out)
        self.assertEqual(code, 1)
        self.assertFinds(self.mutate(TC, _body="## Цель\n\nВход.\n"), "секция «Шаги» отсутствует")
        code, _ = self.assertFinds(self.mutate(TC, status="review", _body=TEMPLATE_BODY), "warn: секция «Шаги» пустая")
        self.assertEqual(code, 0)
        code, out = self.lint(self.build(self.mutate(TC, status="draft", _body=TEMPLATE_BODY)))
        self.assertEqual((code, out.strip()), (0, "замечаний нет"))

    def test_suite_with_obsolete_case(self):
        files = valid_repo()
        files["cases/ACME-T-4-tc-old.md"] = dict(id="ACME-T-4", type="test-case", status="obsolete", level="ui", links=[])
        files["cases/ACME-T-5-tc-new.md"] = dict(id="ACME-T-5", type="test-case", status="draft", level="ui",
                                                 links=[{"type": "supersedes", "to": "ACME-T-4"},
                                                        {"type": "verifies", "to": "ACME-3"}])
        files[TS] = {**files[TS], "links": files[TS]["links"] + [{"type": "contains", "to": "ACME-T-4"}]}
        self.assertFinds(files, "сьюит содержит obsolete-кейс ACME-T-4", registries=((5, 6), (5, 6)))

    def test_registry(self):
        self.assertFinds(valid_repo(), "Next = 5, а уже выдан номер 5", registries=((4, 5), (3, 4)))
        code, out = self.assertFinds(valid_repo(), "Last issued = 4", registries=((4, 6), (3, 4)))
        self.assertEqual(code, 0)  # только предупреждения

    def test_path_filter(self):
        root = self.build(self.mutate(SR, id="ACME-30"))
        self.assertIn("ACME-3-sr-auth.md", self.lint(root, "docs/requirements")[1])
        self.assertEqual(self.lint(root, "docs/tests")[1].strip(), "замечаний нет")


class HookTest(DocsLintCase):
    def run_hook(self, root: Path, file_path: Path) -> str:
        payload = json.dumps({"tool_input": {"file_path": str(file_path)}})
        return subprocess.run([sys.executable, str(root / ".claude" / "hooks" / "docs_lint.py"), "--hook"],
                              input=payload, capture_output=True, text=True, encoding="utf-8").stdout.strip()

    def test_reports_only_changed_file(self):
        files = valid_repo()
        files[SR] = {**files[SR], "id": "ACME-30"}
        files[TC] = {**files[TC], "status": "nope"}
        root = self.build(files)
        out = json.loads(self.run_hook(root, root / "docs" / "requirements" / SR))
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("ACME-3-sr-auth.md", context)
        self.assertNotIn("ACME-T-1-tc-auth.md", context)
        self.assertEqual(self.run_hook(root, root / "docs" / "requirements" / EPIC), "")
        self.assertEqual(self.run_hook(root, root / "README.md"), "")


if __name__ == "__main__":
    unittest.main()
