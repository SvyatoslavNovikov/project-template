# -*- coding: utf-8 -*-
"""Модуль Test IT: кейс → work item, dry-run, запись globalId, результаты прогона. Без сети.

Запуск из корня репозитория: python -m unittest discover -s scripts/tests -v
(в шаблоне — -s optional/testit/scripts/tests).
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
import testit_cli  # noqa: E402

CONFIG = {"base_url": "https://tms.invalid", "project_id": "p-uuid", "section_id": "s-uuid", "configuration_id": "c-uuid"}
CASE = """---
id: ACME-T-{n}
type: test-case
title: Вход {n}
status: {status}
priority: must
tags: [smoke]
level: ui
links:
  - type: verifies
    to: ACME-3
{ext}---

# ACME-T-{n}-tc-login{n}

## Цель

Подтвердить вход.

## Предусловия

- Пользователь <зарегистрирован>

## Шаги

1. Открыть форму.
2. Ввести данные.

## Ожидаемый результат

- Открыта главная.
"""
RUN = """---
id: ACME-T-9
type: test-run
title: Смоук
status: completed
outcome: failed
mode: automated
revision: abc
results:
  - case: ACME-T-1
    status: passed
  - case: ACME-T-2
    status: failed
    comment: "500 на входе"
  - case: ACME-T-3
    status: not-run
---

# ACME-T-9-tr-smoke
"""


class TestItCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        cases = self.root / "docs/tests/cases"
        cases.mkdir(parents=True)
        self.case1 = cases / "ACME-T-1-tc-login1.md"
        self.case2 = cases / "ACME-T-2-tc-login2.md"
        self.case1.write_text(CASE.format(n=1, status="approved", ext=""), encoding="utf-8")
        self.case2.write_text(CASE.format(n=2, status="draft", ext="external:\n  testit: \"502\"\n"), encoding="utf-8")
        (cases / "ACME-T-3-tc-old.md").write_text(CASE.format(n=3, status="obsolete", ext=""), encoding="utf-8")
        run = self.root / "docs/tests/runs/ACME-T-9-tr-smoke"
        run.mkdir(parents=True)
        self.run = run / "ACME-T-9-tr-smoke.md"
        self.run.write_text(RUN, encoding="utf-8")
        self.env = mock.patch.dict("os.environ", {"TMS_PRIVATE_TOKEN": "dummy-not-a-real-token", "TMS_BASE_URL": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    @staticmethod
    def server(method, url, **kwargs):
        if url.endswith("/workItems/search"):
            ids = kwargs["body"]["filter"]["globalIds"]
            return [{"globalId": g, "id": f"uuid-{g}"} for g in ids if g in (501, 502)]
        if method == "POST" and url.endswith("/workItems"):
            return {"id": "uuid-501", "globalId": 501}
        if url.endswith("/testRuns/byConfigurations"):
            return {"id": "run-1"}
        return {}

    def call(self, fn, apply: bool, *args):
        with mock.patch.object(http_client, "request_json", side_effect=self.server) as request:
            client = testit_cli.TestItClient(CONFIG, apply=apply, log=lambda _: None)
            with redirect_stdout(io.StringIO()) as out:
                fn(client, CONFIG, self.root, *args)
        return request, client, out.getvalue()


class CasesTest(TestItCase):
    def test_payload(self):
        payload = testit_cli.case_payload(artifacts.load(self.case1))
        self.assertEqual(payload["name"], "ACME-T-1 Вход 1")
        self.assertEqual((payload["state"], payload["priority"]), ("Ready", "High"))
        self.assertEqual([t["name"] for t in payload["tags"]], ["ACME-T-1", "smoke"])
        self.assertEqual(payload["preconditionSteps"][0]["action"], "<p>Пользователь &lt;зарегистрирован&gt;</p>")
        self.assertEqual([s["expected"] for s in payload["steps"]], ["", "<p>Открыта главная.</p>"])
        empty = artifacts.load(self.case1)
        empty.sections["Шаги"] = "1. …"
        self.assertIsNone(testit_cli.case_payload(empty))

    def test_dry_run_plans_create_and_update_only(self):
        before = self.case1.read_text(encoding="utf-8")
        request, client, out = self.call(testit_cli.push_cases, False, [])
        self.assertEqual([c.args[0] for c in request.call_args_list], ["POST"])  # только поиск (_query)
        self.assertEqual([(m, p) for m, p, _ in client.planned], [("POST", "/api/v2/workItems"), ("PUT", "/api/v2/workItems")])
        self.assertEqual(client.planned[1][2]["id"], "uuid-502")
        self.assertIn("obsolete — пропущен", out)
        self.assertEqual(self.case1.read_text(encoding="utf-8"), before)

    def test_apply_writes_global_id(self):
        self.call(testit_cli.push_cases, True, ["docs/tests/cases/ACME-T-1-tc-login1.md"])
        self.assertEqual(artifacts.load(self.case1).external("testit"), "501")


class ResultsTest(TestItCase):
    def test_requires_pushed_cases(self):
        with self.assertRaisesRegex(SystemExit, "ACME-T-1"):
            self.call(testit_cli.push_results, False, "docs/tests/runs/ACME-T-9-tr-smoke")

    def test_dry_run_and_apply(self):
        artifacts.set_external(self.case1, "testit", "501")
        _, client, _ = self.call(testit_cli.push_results, False, "ACME-T-9")
        paths = [p for _, p, _ in client.planned]
        self.assertEqual(paths, ["/api/v2/autoTests", "/api/v2/autoTests", "/api/v2/testRuns/byConfigurations",
                                 "/api/v2/testRuns/<id тест-рана>/start", "/api/v2/testRuns/<id тест-рана>/testResults"])
        results = client.planned[-1][2]
        self.assertEqual([(r["autoTestExternalId"], r["outcome"], r["statusCode"]) for r in results],
                         [("ACME-T-1", "Passed", "PASSED"), ("ACME-T-2", "Failed", "FAILED")])  # not-run не отправляется
        self.assertEqual(results[1]["message"], "500 на входе")
        self.assertNotIn("external", artifacts.load(self.run).fm)

        self.call(testit_cli.push_results, True, "docs/tests/runs/ACME-T-9-tr-smoke")
        self.assertEqual(artifacts.load(self.run).external("testit"), "run-1")


if __name__ == "__main__":
    unittest.main()
