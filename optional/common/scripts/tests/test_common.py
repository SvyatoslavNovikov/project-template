# -*- coding: utf-8 -*-
"""Общая часть интеграций: dry-run клиента и запись external в артефакт. Без сети.

Запуск из корня репозитория: python -m unittest discover -s scripts/tests -v
(в шаблоне — -s optional/common/scripts/tests).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))

import artifacts  # noqa: E402
import http_client  # noqa: E402

DOC = """---
id: ACME-2
type: user-story
title: "Вход по email"
status: draft
parent: ACME-1
links: []
---

# ACME-2-us-login

## Формулировка

Как пользователь, я хочу войти по email.

## Шаги

1. Открыть форму.
2. …

## Ожидаемый результат

- …
"""


class ClientTest(unittest.TestCase):
    def client(self, apply: bool):
        self.log: list[str] = []
        return http_client.ApiClient("https://svc.invalid/", "Bearer x", apply=apply, log=self.log.append)

    def test_dry_run_sends_nothing(self):
        with mock.patch.object(http_client, "request_json") as request:
            c = self.client(apply=False)
            self.assertEqual(c._post("/a", {"x": 1}), http_client.DRY_RUN)
            c._put("/b", {"y": 2})
            c._delete("/c")
            request.assert_not_called()
        self.assertEqual([m for m, _, _ in c.planned], ["POST", "PUT", "DELETE"])
        self.assertIn("DRY-RUN POST /a", self.log[0])
        self.assertNotIn("Bearer", "\n".join(self.log))

    def test_apply_sends_and_get_always_reads(self):
        with mock.patch.object(http_client, "request_json", return_value={"ok": 1}) as request:
            c = self.client(apply=False)
            self.assertEqual(c._get("/r"), {"ok": 1})
            c._query("/search", {"filter": {}})  # чтение через POST идёт и в dry-run
            self.client(apply=True)._post("/a", {"x": 1})
        self.assertEqual([call.args[:2] for call in request.call_args_list],
                         [("GET", "https://svc.invalid/r"), ("POST", "https://svc.invalid/search"),
                          ("POST", "https://svc.invalid/a")])

    def test_missing_base_url_and_token(self):
        with self.assertRaisesRegex(RuntimeError, "адрес сервиса"):
            http_client.ApiClient("", "Bearer x")
        with mock.patch.dict("os.environ", {"SOME_TOKEN": ""}):
            with self.assertRaisesRegex(RuntimeError, "SOME_TOKEN"):
                http_client.env_token("SOME_TOKEN")


class ArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / "docs/requirements/epics/ACME-1-epic-x/stories/ACME-2-us-login/ACME-2-us-login.md"
        self.path.parent.mkdir(parents=True)
        self.path.write_text(DOC, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_and_load(self):
        self.assertEqual(artifacts.find(self.root, "ACME-2"), self.path)
        with self.assertRaises(FileNotFoundError):
            artifacts.find(self.root, "ACME-20")
        a = artifacts.load(self.path)
        self.assertEqual((a.id, a.type, a.title), ("ACME-2", "user-story", "Вход по email"))
        self.assertFalse(a.body.startswith("# "))
        self.assertEqual(artifacts.items(a.sections["Шаги"]), ["Открыть форму."])
        self.assertEqual(artifacts.items(a.sections["Ожидаемый результат"]), [])

    def test_set_external_adds_and_updates(self):
        artifacts.set_external(self.path, "jira", "J-7")
        artifacts.set_external(self.path, "testit", "1042")
        artifacts.set_external(self.path, "jira", "J-8")
        a = artifacts.load(self.path)
        self.assertEqual(a.fm["external"], {"jira": "J-8", "testit": "1042"})
        text = self.path.read_text(encoding="utf-8")
        self.assertIn('title: "Вход по email"', text)  # остальной frontmatter не переписан
        self.assertEqual(text.count("external:"), 1)
        self.assertNotIn("\r", text)

    def test_set_external_flow_and_empty_forms(self):
        for start in ("external: {}", "external: {jira: J-1}"):
            with self.subTest(start=start):
                self.path.write_text(DOC.replace("links: []", f"links: []\n{start}"), encoding="utf-8")
                artifacts.set_external(self.path, "confluence", "4567")
                external = artifacts.load(self.path).fm["external"]
                self.assertEqual(external["confluence"], "4567")
                if "J-1" in start:
                    self.assertEqual(external["jira"], "J-1")


if __name__ == "__main__":
    unittest.main()
