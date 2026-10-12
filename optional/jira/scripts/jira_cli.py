# -*- coding: utf-8 -*-
"""Jira для проекта на шаблоне: чтение задач и выгрузка артефактов docs/requirements.

  python scripts/jira_cli.py digest ACME-123 [--comments 3]
  python scripts/jira_cli.py find "project = ACME AND status = Open" [--limit 20]
  python scripts/jira_cli.py publish PRJ-12 [--apply]

publish без --apply печатает, что будет создано или обновлено, и ничего не отправляет.
С --apply создаёт задачу (или обновляет ту, что уже в external.jira) и записывает ключ
в external.jira артефакта. Настройки — scripts/jira.config.json, токен — env JIRA_TOKEN.
Запускать из корня репозитория.
"""
from __future__ import annotations

import argparse
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
from jira_client import JiraClient  # noqa: E402
from jira_markup import to_wiki  # noqa: E402

CONFIG = HERE / "jira.config.json"


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise SystemExit(f"нет {path.name}: скопируйте его из модуля optional/jira и заполните")


def text(value: Any, limit: int = 0) -> str:
    value = "" if value is None else str(value)
    return value if not limit or len(value) <= limit else value[:limit] + "…"


def digest(client: JiraClient, key: str, comments: int) -> None:
    issue = client.get_issue(key, "summary,issuetype,status,assignee,priority,labels,fixVersions,description,issuelinks,parent")
    f = issue.get("fields", {})
    print(f"{key} [{text((f.get('issuetype') or {}).get('name'))}] {text(f.get('summary'))}")
    print(f"  статус: {text((f.get('status') or {}).get('name'))}; исполнитель: "
          f"{text((f.get('assignee') or {}).get('displayName')) or '—'}; приоритет: {text((f.get('priority') or {}).get('name'))}")
    if f.get("labels"):
        print(f"  метки: {', '.join(f['labels'])}")
    if f.get("fixVersions"):
        print(f"  версии: {', '.join(v.get('name', '') for v in f['fixVersions'])}")
    for link in f.get("issuelinks") or []:
        other = link.get("outwardIssue") or link.get("inwardIssue") or {}
        kind = (link.get("type") or {}).get("outward" if "outwardIssue" in link else "inward", "")
        print(f"  связь: {kind} {other.get('key', '')} {text((other.get('fields') or {}).get('summary'), 80)}")
    if f.get("description"):
        print("  описание:\n    " + text(f["description"], 1500).replace("\n", "\n    "))
    for c in client.get_comments(key, comments) if comments else []:
        print(f"  комментарий {text((c.get('author') or {}).get('displayName'))}, {text(c.get('created'))[:10]}: "
              f"{text(c.get('body'), 400)}")


def find(client: JiraClient, jql: str, limit: int) -> None:
    issues = client.search(jql, limit=limit)
    for issue in issues:
        f = issue.get("fields", {})
        print(f"{issue['key']} | {text((f.get('issuetype') or {}).get('name'))} | "
              f"{text((f.get('status') or {}).get('name'))} | {text(f.get('summary'), 100)}")
    print(f"найдено: {len(issues)}")


def issue_fields(art: artifacts.Artifact, config: dict[str, Any], root: Path) -> dict[str, Any]:
    issue_type = (config.get("issue_types") or {}).get(art.type)
    if not issue_type:
        raise SystemExit(f"{art.id}: тип {art.type} не сопоставлен с типом задачи Jira (issue_types в {CONFIG.name})")
    source = art.path.resolve().relative_to(root.resolve()).as_posix()
    fields: dict[str, Any] = {
        "summary": art.title,
        "description": to_wiki(art.body) + f"\n----\nИсточник: {art.id}, {source}\n",
        "labels": [art.id] + list(config.get("labels") or []),
    }
    if art.type == "epic" and config.get("epic_name_field"):
        fields[config["epic_name_field"]] = art.title
    parent_id = art.fm.get("parent")
    if parent_id and config.get("epic_link_field"):
        parent = artifacts.load(artifacts.find(root, str(parent_id)))
        if parent.type == "epic" and parent.external("jira"):
            fields[config["epic_link_field"]] = parent.external("jira")
        elif parent.type == "epic":
            print(f"  эпик {parent_id} ещё не в Jira: Epic Link не ставится, сначала publish {parent_id}")
    return {"create": {"project": {"key": config.get("project", "")}, "issuetype": {"name": issue_type}, **fields},
            "update": fields}


def publish(client: JiraClient, artifact_id: str, config: dict[str, Any], root: Path) -> None:
    art = artifacts.load(artifacts.find(root, artifact_id))
    fields = issue_fields(art, config, root)
    key = art.external("jira")
    if key:
        print(f"{art.id} → обновить {key}")
        client.update_issue(key, fields["update"])
        return
    if not config.get("project"):
        raise SystemExit(f"не задан project в {CONFIG.name}")
    print(f"{art.id} → создать {fields['create']['issuetype']['name']} в {config['project']}")
    created = client.create_issue(fields["create"])
    if created is DRY_RUN:
        return
    artifacts.set_external(art.path, "jira", created["key"])
    print(f"создано: {created['key']}; external.jira записан в {art.path.name}")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("digest", help="кратко о задаче")
    p.add_argument("key")
    p.add_argument("--comments", type=int, default=3)
    p = sub.add_parser("find", help="поиск по JQL")
    p.add_argument("jql")
    p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("publish", help="создать или обновить задачу по артефакту")
    p.add_argument("id")
    p.add_argument("--apply", action="store_true", help="отправить; без флага — dry-run")
    p.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    config = load_config()
    client = JiraClient(config, apply=getattr(args, "apply", False))
    if args.command == "digest":
        digest(client, args.key, args.comments)
    elif args.command == "find":
        find(client, args.jql, args.limit)
    else:
        publish(client, args.id, config, args.root)
        if not args.apply:
            print("dry-run: ничего не отправлено. Отправить — та же команда с --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
