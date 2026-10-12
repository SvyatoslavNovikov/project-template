# -*- coding: utf-8 -*-
"""Защитные хуки: без сети и без настоящих токенов.

Хуки копируются во временный репозиторий со своим config.json и подставным клиентом
API, поэтому проверка не зависит от настроек конкретного проекта.

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

HOOKS = Path(__file__).resolve().parents[1]

CONFIG = {
    "secret_env": ["SVC_KEY"],
    "export_dirs": ["svc-export/"],
    "write_hosts": [r"api\.example\.com"],
    "client_files": ["scripts/lib/svc_client.py"],
    "apply_scripts": ["scripts/svc.py"],
}
CLIENT = '''class SvcClient:
    def get_item(self, key):
        return self._get(f"/item/{key}")

    def create_item(self, data):
        return self._post("/item", data)

    def _post(self, path, body):
        return request_json("POST", path, body)
'''
SCRIPTS = {
    "scripts/svc.py": "import svc_client\n",
    "scripts/svc-create.py": "from svc_client import SvcClient\nSvcClient().create_item({})\n",
    "scripts/svc-read.py": "from svc_client import SvcClient\nSvcClient().get_item('X-1')\n",
    "scripts/svc-fix.py": "import argparse  # --dry-run\nfrom svc_client import SvcClient\nSvcClient().create_item({})\n",
    "scripts/report.py": "print('local only')\n",
}
# подставные значения собираются по частям, чтобы сам файл не выглядел как хардкод токена
FAKE_NAMED = "SVC_" + "KEY=" + "abcdefghijklmnop12345"
FAKE_GENERIC = "OTHER_" + "TOKEN=" + "abcdefghijklmnop12345"


def make_repo(tmp: Path, config: dict | None) -> Path:
    hooks = tmp / ".claude" / "hooks"
    shutil.copytree(HOOKS, hooks, ignore=shutil.ignore_patterns("tests", "__pycache__", "config.json"))
    if config is not None:
        text = config if isinstance(config, str) else json.dumps(config)
        (hooks / "config.json").write_text(text, encoding="utf-8")
    for rel, text in {"scripts/lib/svc_client.py": CLIENT, **SCRIPTS}.items():
        path = tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp


class HookCase(unittest.TestCase):
    config: dict | None = CONFIG
    hook = ""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = make_repo(Path(cls.tmp.name), cls.config)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def decision(self, command: str) -> str:
        payload = json.dumps({"tool_input": {"command": command}, "cwd": str(self.root)})
        out = subprocess.run(
            [sys.executable, str(self.root / ".claude" / "hooks" / self.hook)],
            input=payload, capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"

    def assertDecisions(self, expected: str, commands):
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(self.decision(command), expected)


class WriteGuardTest(HookCase):
    hook = "external_write_guard.py"

    def test_reads_pass(self):
        self.assertDecisions("allow", (
            "python scripts/svc.py digest X-1",
            'python scripts/svc.py create --summary "не путать с --apply"',
            "python scripts/svc-read.py",
            "python scripts/svc-fix.py --dry-run",
            "python scripts/report.py",
            # упоминания пишущих скриптов без запуска
            "git add scripts/svc-create.py scripts/lib/svc_client.py",
            "grep -n def scripts/lib/svc_client.py; cat scripts/svc-create.py | head",
            "git commit -q -F - <<'EOF'\npython scripts/svc.py create --apply\nEOF",
            "python - <<'EOF'\ntext = text.replace('svc.py create', 'затем --apply')\nEOF",
            "curl -s https://api.example.com/item/X-1",
            "Invoke-RestMethod -Uri https://api.example.com/item/1 -Headers $h",
            "curl -X POST https://other.example.org/item",
        ))

    def test_writes_ask(self):
        self.assertDecisions("ask", (
            "python scripts/svc.py create --summary x --apply",
            "Set-Location C:\\repo; python scripts/svc.py update X-1 --apply",
            "python scripts/svc-create.py",
            "python scripts/svc-fix.py",
            "python - <<EOF\nfrom svc_client import SvcClient\nSvcClient().create_item({})\nEOF",
            "python -c \"import svc_client; svc_client.SvcClient().create_item({})\"",
            "curl -X POST https://api.example.com/item",
            "curl -s -d @body.json https://api.example.com/item",
            "Invoke-RestMethod -Method Put -Uri https://api.example.com/item/1",
        ))


class SecretGuardTest(HookCase):
    hook = "secret_guard.py"

    def test_mentions_pass(self):
        self.assertDecisions("allow", (
            "git commit -q -F - <<'EOF'\nraw data goes to svc-export/X-1.json\nEOF",
            'git commit -m "results go to svc-export/X-1"',
            "python - <<'EOF'\nprint('git add svc-export/ is blocked by the hook')\nEOF",
            "grep -rn svc-export/ .gitignore",
            "$env:SVC_KEY | Out-Null",
        ))

    def test_denied(self):
        self.assertDecisions("deny", (
            "git add svc-export/X-1.json",
            "git add -f svc-export",
            "git -C C:/repo add svc-export/run.json",
            "echo " + FAKE_NAMED,
            "echo " + FAKE_GENERIC,
            "curl -H 'Authorization: Bearer abcdefghijklmnopqrstu' https://x",
        ))


class EmptyConfigTest(HookCase):
    """Шаблон по умолчанию: систем нет, проверяются только литералы токенов."""

    config = None

    def test_write_guard_silent(self):
        self.hook = "external_write_guard.py"
        self.assertDecisions("allow", (
            "python scripts/svc-create.py",
            "curl -X POST https://api.example.com/item",
        ))

    def test_secret_guard_generic_only(self):
        self.hook = "secret_guard.py"
        self.assertDecisions("allow", ("git add svc-export/X-1.json", "echo " + FAKE_NAMED))
        self.assertDecisions("deny", ("echo " + FAKE_GENERIC,))


class BrokenConfigTest(HookCase):
    """Опечатка в config.json не должна молча выключать защиту."""

    config = '{"write_hosts": ["api\\.example\\.com"]}'  # \. — недопустимая escape-последовательность JSON

    def test_write_guard_asks_on_everything(self):
        self.hook = "external_write_guard.py"
        self.assertDecisions("ask", ("python scripts/report.py", "git status"))

    def test_secret_guard_keeps_generic_checks(self):
        self.hook = "secret_guard.py"
        self.assertDecisions("deny", ("echo " + FAKE_GENERIC,))
        self.assertDecisions("allow", ("git status",))


if __name__ == "__main__":
    unittest.main()
