# -*- coding: utf-8 -*-
"""Test IT для проекта на шаблоне: выгрузка кейсов docs/tests и результатов прогонов.

  python scripts/testit_cli.py push-cases [файлы или каталоги] [--apply]
  python scripts/testit_cli.py push-results <папка, файл или ID прогона> [--apply]

push-cases: кейс → work item (TestCases). Нет external.testit — создать и записать globalId,
есть — обновить тот же work item. Без шагов кейс пропускается, obsolete — тоже.
push-results: строки results прогона → автотесты с externalId = ID кейса (стабилен, как
и требует Test IT), тест-ран по конфигурации и результаты; ID тест-рана → external.testit
прогона. Кейсы прогона должны быть уже выгружены (external.testit).

Без --apply печатает план и ничего не отправляет. Настройки — scripts/testit.config.json,
токен — env TMS_PRIVATE_TOKEN. Запускать из корня репозитория.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
for lib in (HERE / "lib", HERE.parents[1] / "common" / "scripts" / "lib"):
    if lib.is_dir():
        sys.path.insert(0, str(lib))

import artifacts  # noqa: E402
from http_client import DRY_RUN  # noqa: E402
from testit_client import TestItClient  # noqa: E402

CONFIG = HERE / "testit.config.json"
STATE = {"draft": "NotReady", "review": "NeedsWork", "approved": "Ready", "automated": "Ready"}
PRIORITY = {"must": "High", "should": "Medium", "could": "Low"}
OUTCOME = {"passed": "Passed", "failed": "Failed", "blocked": "Blocked", "skipped": "Skipped"}


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise SystemExit(f"нет {path.name}: скопируйте его из модуля optional/testit и заполните")


def need(config: dict[str, Any], *keys: str) -> None:
    missing = [k for k in keys if not config.get(k)]
    if missing:
        raise SystemExit(f"не заданы {', '.join(missing)} в {CONFIG.name}")


def para(text: str) -> str:
    return f"<p>{html.escape(text, quote=False)}</p>" if text else ""


def step(action: str, expected: str = "") -> dict[str, str]:
    return {"action": action, "expected": expected, "testData": "", "comments": ""}


def case_payload(art: artifacts.Artifact) -> dict[str, Any] | None:
    """Work item по кейсу; None — нечего выгружать (нет шагов)."""
    steps = artifacts.items(art.sections.get("Шаги", ""))
    if not steps:
        return None
    expected = artifacts.items(art.sections.get("Ожидаемый результат", ""))
    expected_html = "".join(para(e) for e in expected)
    return {
        "name": f"{art.id} {art.title}",
        "description": para(" ".join(art.sections.get("Цель", "").split())),
        "entityTypeName": "TestCases",
        "duration": 600000,
        "state": STATE.get(str(art.fm.get("status")), "NotReady"),
        "priority": PRIORITY.get(str(art.fm.get("priority")), "Medium"),
        "attributes": {},
        "tags": [{"name": t} for t in [art.id, *map(str, art.fm.get("tags") or [])]],
        "links": [],
        "preconditionSteps": [step(para(p)) for p in artifacts.items(art.sections.get("Предусловия", ""))],
        # ожидаемый результат кейса — итог сценария, поэтому на последнем шаге
        "steps": [step(para(s), expected_html if i == len(steps) - 1 else "") for i, s in enumerate(steps)],
        "postconditionSteps": [],
    }


def case_files(root: Path, paths: list[str]) -> list[Path]:
    targets = [root / p for p in paths] or [root / "docs/tests/cases"]
    files: list[Path] = []
    for t in targets:
        files += sorted(t.glob("*-tc-*.md")) if t.is_dir() else [t]
    return files


def uuids_by_global_id(client: TestItClient, project_id: str, global_ids: list[str]) -> dict[str, str]:
    if not global_ids:
        return {}
    found = client.search_work_items(project_id, [int(g) for g in global_ids])
    return {str(item.get("globalId")): item.get("id") for item in found}


def push_cases(client: TestItClient, config: dict[str, Any], root: Path, paths: list[str]) -> None:
    need(config, "project_id", "section_id")
    cases = [artifacts.load(p) for p in case_files(root, paths)]
    cases = [c for c in cases if c.type == "test-case"]
    known = uuids_by_global_id(client, config["project_id"], [c.external("testit") for c in cases if c.external("testit")])
    for art in cases:
        if art.fm.get("status") == "obsolete":
            print(f"{art.id}: obsolete — пропущен")
            continue
        payload = case_payload(art)
        if payload is None:
            print(f"{art.id}: нет шагов — пропущен")
            continue
        global_id = art.external("testit")
        if global_id:
            uuid = known.get(global_id)
            if not uuid:
                print(f"{art.id}: external.testit = {global_id}, но в проекте Test IT такого work item нет — пропущен")
                continue
            print(f"{art.id} → обновить {global_id}")
            client.update_work_item({**payload, "id": uuid, "sectionId": config["section_id"]})
            continue
        print(f"{art.id} → создать кейс")
        created = client.create_work_item({**payload, "projectId": config["project_id"], "sectionId": config["section_id"]})
        if created is not DRY_RUN:
            artifacts.set_external(art.path, "testit", str(created["globalId"]))
            print(f"  создан {created['globalId']}; external.testit записан")


def run_file(root: Path, ref: str) -> Path:
    path = root / ref
    if path.is_dir():
        path = path / f"{path.name}.md"
    if path.is_file():
        return path
    return artifacts.find(root, ref)


def push_results(client: TestItClient, config: dict[str, Any], root: Path, ref: str) -> None:
    need(config, "project_id", "configuration_id")
    run = artifacts.load(run_file(root, ref))
    if run.type != "test-run":
        raise SystemExit(f"{run.id}: это {run.type}, а не test-run")
    rows = [r for r in run.fm.get("results") or [] if isinstance(r, dict) and r.get("status") in OUTCOME]
    cases = {str(r["case"]): artifacts.load(artifacts.find(root, str(r["case"]))) for r in rows}
    missing = [cid for cid, c in cases.items() if not c.external("testit")]
    if missing:
        raise SystemExit(f"кейсы не выгружены в Test IT (нет external.testit): {', '.join(missing)} — сначала push-cases")
    uuids = uuids_by_global_id(client, config["project_id"], [c.external("testit") for c in cases.values()])
    lost = [cid for cid, c in cases.items() if c.external("testit") not in uuids]
    if lost:
        raise SystemExit(f"в проекте Test IT не найдены work items кейсов: {', '.join(lost)}")
    print(f"{run.id}: {len(rows)} результатов → тест-ран в конфигурации {config['configuration_id']}")
    for cid, case in cases.items():
        client.create_autotest(cid, f"{cid} {case.title}", config["project_id"], [uuids[case.external('testit')]])
    created = client.create_test_run(config["configuration_id"], [uuids[c.external("testit")] for c in cases.values()])
    run_id = "<id тест-рана>" if created is DRY_RUN else created["id"]
    client.start_test_run(run_id)
    client.submit_test_results(run_id, [{
        "autoTestExternalId": str(r["case"]),
        "configurationId": config["configuration_id"],
        "outcome": OUTCOME[r["status"]],
        "statusCode": OUTCOME[r["status"]].upper(),
        "message": str(r.get("comment") or ""),
    } for r in rows])
    if created is not DRY_RUN:
        artifacts.set_external(run.path, "testit", str(run_id))
        print(f"тест-ран {run_id}; external.testit записан в {run.path.name}")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("push-cases", help="кейсы → work items")
    p.add_argument("paths", nargs="*")
    p.add_argument("--apply", action="store_true", help="отправить; без флага — dry-run")
    p.add_argument("--root", type=Path, default=Path.cwd())
    p = sub.add_parser("push-results", help="результаты прогона → тест-ран")
    p.add_argument("run")
    p.add_argument("--apply", action="store_true", help="отправить; без флага — dry-run")
    p.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    config = load_config()
    client = TestItClient(config, apply=args.apply)
    if args.command == "push-cases":
        push_cases(client, config, args.root, args.paths)
    else:
        push_results(client, config, args.root, args.run)
    if not args.apply:
        print("dry-run: ничего не отправлено. Отправить — та же команда с --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
