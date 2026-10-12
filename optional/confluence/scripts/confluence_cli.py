# -*- coding: utf-8 -*-
"""Confluence для проекта на шаблоне: чтение страниц как текста и публикация markdown.

  python scripts/confluence_cli.py read <pageId или ссылка> [--out файл]
  python scripts/confluence_cli.py search "space = ACME AND text ~ \"оплата\"" [--limit 10]
  python scripts/confluence_cli.py publish <файл.md> [--title …] [--space …] [--parent …] [--page-id …] [--apply]

publish без --apply печатает, что будет создано или обновлено, и ничего не отправляет.
Артефакт docs/ (с frontmatter id) публикуется как «<ID> <title>»; его страница хранится
в external.confluence, и повторный publish обновляет её. Обычный markdown (конспект встречи
и т.п.) создаёт новую страницу или обновляет --page-id. Настройки — scripts/confluence.config.json,
токен — env CONF_TOKEN. Запускать из корня репозитория.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
for lib in (HERE / "lib", HERE.parents[1] / "common" / "scripts" / "lib"):
    if lib.is_dir():
        sys.path.insert(0, str(lib))

import artifacts  # noqa: E402
from confluence_client import ConfluenceClient  # noqa: E402
from confluence_markup import to_storage, to_text  # noqa: E402
from http_client import DRY_RUN  # noqa: E402

CONFIG = HERE / "confluence.config.json"


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise SystemExit(f"нет {path.name}: скопируйте его из модуля optional/confluence и заполните")


def page_id(ref: str) -> str:
    """pageId из ссылки (?pageId=123, /pages/123/…) или сам ID."""
    for pattern in (r"[?&]pageId=(\d+)", r"/pages/(\d+)", r"^(\d+)$"):
        if m := re.search(pattern, ref.strip()):
            return m.group(1)
    raise SystemExit(f"не понял ID страницы в «{ref}»: нужна ссылка с pageId или /pages/<id>, либо число")


def read(client: ConfluenceClient, ref: str, out: Path | None) -> None:
    page = client.get_page(page_id(ref))
    header = (f"# {page.get('title', '')}\n\nСтраница {page.get('id')}, пространство "
              f"{(page.get('space') or {}).get('key', '')}, версия {(page.get('version') or {}).get('number', '')}\n\n")
    text = header + to_text(((page.get("body") or {}).get("storage") or {}).get("value", ""))
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"{out}: {len(text)} символов, {text.count(chr(10))} строк")
    else:
        print(text)


def search(client: ConfluenceClient, cql: str, limit: int) -> None:
    results = client.search(cql, limit)
    for r in results:
        print(f"{r.get('id')} | {(r.get('space') or {}).get('key', '')} | {r.get('title', '')}")
    print(f"найдено: {len(results)}")


def source(path: Path, root: Path) -> tuple[str, str, artifacts.Artifact | None]:
    """Заголовок, markdown тела и артефакт (если у файла есть frontmatter с id)."""
    try:
        art = artifacts.load(path)
    except ValueError:
        art = None
    if art and art.id:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        return f"{art.id} {art.title}", art.body + f"\n---\n\nИсточник: {art.id}, `{rel}`\n", art
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^# (.+)\n", text)
    return (m.group(1).strip() if m else path.stem), (text[m.end():] if m else text), None


def publish(client: ConfluenceClient, path: Path, config: dict[str, Any], root: Path, *, title: str | None,
            space: str | None, parent: str | None, page: str | None) -> None:
    default_title, body, art = source(path, root)
    title = title or default_title
    storage = to_storage(body)
    existing = page or (art.external("confluence") if art else None)
    if existing:
        print(f"{path.name} → обновить страницу {existing} «{title}»")
        client.update_page(page_id(existing), storage, title=title, message=f"из {path.name}")
        return
    space = space or config.get("space")
    parent = parent or config.get("parent_id") or None
    if not space:
        raise SystemExit(f"не задано пространство: --space или space в {CONFIG.name}")
    print(f"{path.name} → создать «{title}» в {space}" + (f" под {parent}" if parent else ""))
    created = client.create_page(title, space, parent, storage)
    if created is DRY_RUN:
        return
    print(f"создана страница {created['id']}")
    if art:
        artifacts.set_external(art.path, "confluence", str(created["id"]))
        print(f"external.confluence записан в {art.path.name}")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("read", help="страница как текст")
    p.add_argument("ref")
    p.add_argument("--out", type=Path)
    p = sub.add_parser("search", help="поиск по CQL")
    p.add_argument("cql")
    p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("publish", help="создать или обновить страницу из markdown")
    p.add_argument("file", type=Path)
    p.add_argument("--title")
    p.add_argument("--space")
    p.add_argument("--parent")
    p.add_argument("--page-id")
    p.add_argument("--apply", action="store_true", help="отправить; без флага — dry-run")
    p.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    config = load_config()
    client = ConfluenceClient(config, apply=getattr(args, "apply", False))
    if args.command == "read":
        read(client, args.ref, args.out)
    elif args.command == "search":
        search(client, args.cql, args.limit)
    else:
        publish(client, args.file, config, args.root, title=args.title, space=args.space,
                parent=args.parent, page=args.page_id)
        if not args.apply:
            print("dry-run: ничего не отправлено. Отправить — та же команда с --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
