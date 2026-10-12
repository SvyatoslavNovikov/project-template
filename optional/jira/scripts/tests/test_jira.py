# -*- coding: utf-8 -*-
"""Модуль Jira: разметка, сбор полей, dry-run publish и запись ключа. Без сети.

Запуск из корня репозитория: python -m unittest discover -s scripts/tests -v
(в шаблоне — -s optional/jira/scripts/tests).
"""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
for lib in (SCRIPTS / "lib", SCRIPTS.parents[1] / "common" / "scripts" / "lib", SCRIPTS):
    if lib.is_dir():
        sys.path.insert(0, str(lib))

import artifacts  # noqa: E402
import http_client  # noqa: E402
import jira_cli  # noqa: E402
from jira_markup import to_wiki  # noqa: E402

CONFIG = {"base_url": "https://jira.invalid", "project": "ACME",
          "issue_types": {"epic": "Epic", "user-story": "Story"},
          "epic_name_field": "customfield_1", "epic_link_field": "customfield_2", "labels": ["docs"]}
EPIC = "---\nid: ACME-1\ntype: epic\ntitle: Ядро\nstatus: approved\nparent: \"\"\n{ext}---\n\n# ACME-1-epic-core\n\n## Идея\n\nТекст.\n"
STORY = ("---\nid: ACME-2\ntype: user-story\ntitle: Вход\nstatus: draft\nparent: ACME-1\n{ext}---\n\n"
         "# ACME-2-us-login\n\n## Критерии приёмки\n\n- **Given** форма\n")


class MarkupTest(unittest.TestCase):
    def test_constructs(self):
        wiki = to_wiki("## Шаги\n\n1. Открыть **форму** и *поле*\n  - `a*b`\n\n| a | b |\n|---|---|\n"
                       "| 1 | [x](http://e) |\n\n```py\nprint(1)\n```\n> цитата\nКак \\<роль\\>")
        for expected in ("h2. Шаги", "# Открыть *форму* и _поле_", "** {{a*b}}", "||a||b||",
                         "|1|[x|http://e]|", "{code:py}\nprint(1)\n{code}", "bq. цитата", "Как <роль>"):
            self.assertIn(expected, wiki)


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        base = self.root / "docs/requirements/epics/ACME-1-epic-core"
        (base / "stories/ACME-2-us-login").mkdir(parents=True)
        self.epic = base / "ACME-1-epic-core.md"
        self.story = base / "stories/ACME-2-us-login/ACME-2-us-login.md"
        self.epic.write_text(EPIC.format(ext="external:\n  jira: J-1\n"), encoding="utf-8")
        self.story.write_text(STORY.format(ext=""), encoding="utf-8")
        self.env = mock.patch.dict("os.environ", {"JIRA_TOKEN": "dummy-not-a-real-token", "JIRA_BASE_URL": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_publish(self, artifact_id: str, apply: bool, response=None):
        with mock.patch.object(http_client, "request_json", return_value=response) as request:
            client = jira_cli.JiraClient(CONFIG, apply=apply, log=lambda _: None)
            with redirect_stdout(io.StringIO()) as out:
                jira_cli.publish(client, artifact_id, CONFIG, self.root)
        return request, client, out.getvalue()

    def test_fields(self):
        fields = jira_cli.issue_fields(artifacts.load(self.story), CONFIG, self.root)["create"]
        self.assertEqual(fields["issuetype"], {"name": "Story"})
        self.assertEqual(fields["customfield_2"], "J-1")  # Epic Link из external.jira эпика
        self.assertEqual(fields["labels"], ["ACME-2", "docs"])
        self.assertIn("* *Given* форма", fields["description"])
        self.assertIn("Источник: ACME-2, docs/requirements/", fields["description"])
        self.assertEqual(jira_cli.issue_fields(artifacts.load(self.epic), CONFIG, self.root)["create"]["customfield_1"], "Ядро")

    def test_dry_run_sends_nothing_and_keeps_file(self):
        before = self.story.read_text(encoding="utf-8")
        request, client, _ = self.run_publish("ACME-2", apply=False)
        request.assert_not_called()
        self.assertEqual([m for m, _, _ in client.planned], ["POST"])
        self.assertEqual(self.story.read_text(encoding="utf-8"), before)

    def test_apply_creates_and_writes_key(self):
        request, _, out = self.run_publish("ACME-2", apply=True, response={"key": "J-2"})
        self.assertEqual(request.call_args.args[:2], ("POST", "https://jira.invalid/rest/api/2/issue"))
        self.assertEqual(artifacts.load(self.story).external("jira"), "J-2")
        self.assertIn("создано: J-2", out)

    def test_existing_key_updates(self):
        request, _, _ = self.run_publish("ACME-1", apply=True, response={})
        self.assertEqual(request.call_args.args[:2], ("PUT", "https://jira.invalid/rest/api/2/issue/J-1"))
        self.assertNotIn("project", request.call_args.kwargs["body"]["fields"])

    def test_unmapped_type_refused(self):
        sr = self.root / "docs/requirements/epics/ACME-1-epic-core/stories/ACME-2-us-login/requirements/ACME-3-sr-x.md"
        sr.parent.mkdir(parents=True)
        sr.write_text("---\nid: ACME-3\ntype: system-requirement\ntitle: X\nparent: ACME-2\n---\n\n# ACME-3-sr-x\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "не сопоставлен"):
            self.run_publish("ACME-3", apply=False)


if __name__ == "__main__":
    unittest.main()
