# -*- coding: utf-8 -*-
"""Модуль Confluence: разметка в обе стороны, ID страницы, dry-run publish и запись ID. Без сети.

Запуск из корня репозитория: python -m unittest discover -s scripts/tests -v
(в шаблоне — -s optional/confluence/scripts/tests).
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
import confluence_cli  # noqa: E402
import http_client  # noqa: E402
from confluence_markup import to_storage, to_text  # noqa: E402

CONFIG = {"base_url": "https://wiki.invalid", "space": "ACME", "parent_id": "100"}
STORY = ("---\nid: ACME-2\ntype: user-story\ntitle: Вход\nstatus: draft\nparent: ACME-1\n{ext}---\n\n"
         "# ACME-2-us-login\n\n## Критерии приёмки\n\n- **Given** форма <a>\n")


class MarkupTest(unittest.TestCase):
    def test_storage(self):
        s = to_storage("## Итог\n\nСтрока и **жирный** <тег>.\n\n- a\n  - a1\n- b\n1. n\n\n| x | y |\n|---|---|\n"
                       "| 1 | [l](http://e?a=1&b=2) |\n\n```py\nprint(\"]]>\")\n```\n> цитата")
        for expected in ("<h2>Итог</h2>", "<p>Строка и <strong>жирный</strong> &lt;тег&gt;.</p>",
                         "<ul><li>a<ul><li>a1</li></ul></li><li>b</li></ul><ol><li>n</li></ol>",
                         "<tr><th>x</th><th>y</th></tr>", '<a href="http://e?a=1&amp;b=2">l</a>',
                         '<ac:parameter ac:name="language">py</ac:parameter>', "<blockquote><p>цитата</p></blockquote>"):
            self.assertIn(expected, s)

    def test_round_trip_text(self):
        text = to_text(to_storage("## Итог\n\n- a\n  - a1\n\n| x | y |\n|---|---|\n| 1 | 2 |\n\n```\nprint(\"]]>\")\n```"))
        for expected in ("## Итог", "- a\n  - a1", "| x | y", 'print("]]>")'):
            self.assertIn(expected, text)

    def test_page_id(self):
        for ref in ("123", "https://wiki/pages/viewpage.action?pageId=123", "https://x.atlassian.net/wiki/spaces/A/pages/123/T"):
            self.assertEqual(confluence_cli.page_id(ref), "123")
        with self.assertRaises(SystemExit):
            confluence_cli.page_id("https://wiki/display/A/Page")


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.story = self.root / "docs/requirements/epics/ACME-1-epic-x/stories/ACME-2-us-login/ACME-2-us-login.md"
        self.story.parent.mkdir(parents=True)
        self.story.write_text(STORY.format(ext=""), encoding="utf-8")
        self.notes = self.root / "docs/meetings/2026-10-12-x.md"
        self.notes.parent.mkdir(parents=True)
        self.notes.write_text("# Встреча\n\n## Итог\n\nРешили.\n", encoding="utf-8")
        self.env = mock.patch.dict("os.environ", {"CONF_TOKEN": "dummy-not-a-real-token", "CONF_BASE_URL": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_publish(self, path: Path, apply: bool, responses, **kw):
        options = {"title": None, "space": None, "parent": None, "page": None, **kw}
        with mock.patch.object(http_client, "request_json", side_effect=responses) as request:
            client = confluence_cli.ConfluenceClient(CONFIG, apply=apply, log=lambda _: None)
            with redirect_stdout(io.StringIO()):
                confluence_cli.publish(client, path, CONFIG, self.root, **options)
        return request, client

    def test_dry_run_artifact(self):
        before = self.story.read_text(encoding="utf-8")
        request, client = self.run_publish(self.story, False, [])
        request.assert_not_called()
        method, path, body = client.planned[0]
        self.assertEqual((method, path, body["title"]), ("POST", "/rest/api/content", "ACME-2 Вход"))
        self.assertEqual(body["ancestors"], [{"id": "100"}])
        self.assertIn("&lt;a&gt;", body["body"]["storage"]["value"])
        self.assertEqual(self.story.read_text(encoding="utf-8"), before)

    def test_apply_creates_and_writes_id_then_updates(self):
        self.run_publish(self.story, True, [{"id": "555"}])
        self.assertEqual(artifacts.load(self.story).external("confluence"), "555")
        request, _ = self.run_publish(self.story, True, [{"title": "t", "version": {"number": 4}}, {}])
        method, url = request.call_args.args[:2]
        self.assertEqual((method, url), ("PUT", "https://wiki.invalid/rest/api/content/555"))
        self.assertEqual(request.call_args.kwargs["body"]["version"]["number"], 5)

    def test_plain_markdown(self):
        request, client = self.run_publish(self.notes, False, [])
        self.assertEqual(client.planned[0][2]["title"], "Встреча")
        _, client = self.run_publish(self.notes, False, [{"title": "Встреча", "version": {"number": 1}}], page="777")
        self.assertEqual(client.planned[0][:2], ("PUT", "/rest/api/content/777"))


if __name__ == "__main__":
    unittest.main()
