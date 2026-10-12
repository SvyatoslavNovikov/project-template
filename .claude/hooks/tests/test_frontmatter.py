# -*- coding: utf-8 -*-
"""Заголовки агентов и скиллов разбираются, иначе приложение их молча не регистрирует.

Запуск из корня репозитория:  python -m unittest discover -s .claude/hooks/tests -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / ".claude" / "hooks" / "frontmatter_lint.py"
sys.path.insert(0, str(HOOK.parent))

import frontmatter_lint as fl  # noqa: E402

AGENT = Path(".claude/agents/figma-reader.md")


def doc(description: str, name: str = "figma-reader") -> str:
    return f"---\nname: {name}\ndescription: {description}\nmodel: sonnet\n---\n\nТекст агента.\n"


class RepoFilesTest(unittest.TestCase):
    def test_all_agents_and_skills_parse(self):
        targets = fl.all_targets()
        self.assertTrue(targets)
        for path in targets:
            with self.subTest(path=fl.rel(path)):
                self.assertEqual(fl.lint_file(path), [])


class LintTextTest(unittest.TestCase):
    def test_colon_in_plain_description(self):
        # исходная ошибка figma-reader, 07.10.2026
        issues = fl.lint_text(doc("Читает макеты. Только чтение: ничего не меняет в Figma."), AGENT)
        self.assertEqual([n for n, _ in issues], [3])

    def test_valid_forms_pass(self):
        for description in (
            "Читает макеты. Только чтение, ничего не меняет в Figma.",
            '"Читает макеты. Только чтение: ничего не меняет в Figma."',
            "Ссылки вида https://www.figma.com/design/x?node-id=1-2 и jira-export/<ключ>/figma.md",
            "Тире — допустимо, двоеточие без пробела тоже (a:b)",
        ):
            with self.subTest(description=description):
                self.assertEqual(fl.lint_text(doc(description), AGENT), [])

    def test_other_breaking_values(self):
        for description in ("Пишет # заметки", "[черновик] истории", "*важно* читать"):
            with self.subTest(description=description):
                self.assertTrue(fl.lint_text(doc(description), AGENT))

    def test_missing_frontmatter_and_fields(self):
        self.assertTrue(fl.lint_text("# Без заголовка\n", AGENT))
        self.assertTrue(fl.lint_text("---\nname: figma-reader\n---\n", AGENT))

    def test_name_must_match_file(self):
        self.assertTrue(fl.lint_text(doc("Читает макеты.", name="figma"), AGENT))
        skill = Path(".claude/skills/handoff/SKILL.md")
        self.assertEqual(fl.lint_text(doc("Передача работы.", name="handoff"), skill), [])


class HookTest(unittest.TestCase):
    def run_hook(self, file_path: Path) -> str:
        payload = json.dumps({"tool_input": {"file_path": str(file_path)}})
        return subprocess.run(
            [sys.executable, str(HOOK), "--hook"],
            input=payload, capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()

    def test_reports_broken_agent_and_ignores_other_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = Path(tmp) / ".claude" / "agents" / "figma-reader.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(doc("Только чтение: ничего не меняет."), encoding="utf-8")
            out = json.loads(self.run_hook(agent))
            self.assertIn("строка 3", out["hookSpecificOutput"]["additionalContext"])

            other = Path(tmp) / "tracks" / "x.md"
            other.parent.mkdir(parents=True)
            other.write_text(doc("Только чтение: ничего не меняет."), encoding="utf-8")
            self.assertEqual(self.run_hook(other), "")


if __name__ == "__main__":
    unittest.main()
