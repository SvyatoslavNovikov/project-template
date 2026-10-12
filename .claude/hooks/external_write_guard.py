# -*- coding: utf-8 -*-
"""PreToolUse(Bash|PowerShell): запись во внешние системы только после подтверждения
пользователя (правило CLAUDE.md «ничего не создавать и не менять без прямой команды»).

Какие системы внешние, задаёт config.json (hook_config.py). Хук не блокирует, а
возвращает permissionDecision=ask: пользователь видит причину и подтверждает или
отклоняет вызов. Смотрит только на то, что команда ЗАПУСКАЕТ (разбор — command_parse.py),
а не на упоминания файлов в git, grep или тексте коммита:
  - скрипт из apply_scripts с флагом --apply;
  - python <скрипт из репозитория>, если в скрипте есть запись через client_files
    (методы, вызывающие _post/_put/_delete) или прямые POST/PUT/PATCH/DELETE на write_hosts;
    скрипт с поддержкой --dry-run, запущенный с этим флагом, пропускается;
  - python -c / python - (код из here-doc или конвейера) с таким же кодом;
  - запуск .ps1 из репозитория с -Method Post/Put/Patch/Delete на write_hosts;
  - curl / Invoke-RestMethod / Invoke-WebRequest с записью на write_hosts.
Чтение (GET) и dry-run проходят без вопросов. Пустой config.json — хук молчит.
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import hook_config  # noqa: E402
from command_parse import powershell_script, python_target, segments  # noqa: E402

ROOT = hook_config.ROOT
HTTP_WRITE_RE = re.compile(
    r"""(["'](POST|PUT|PATCH|DELETE)["']|-Method\s+["']?(Post|Put|Patch|Delete)\b|-X\s*(POST|PUT|PATCH|DELETE)\b"""
    r"""|--request\s+(POST|PUT|PATCH|DELETE)\b|\b(requests|httpx)\.(post|put|patch|delete)\(|\._(post|put|delete)\()""",
    re.IGNORECASE,
)
CURL_WRITE_RE = re.compile(r"(^|\s)(-d|--data\S*|-F|--form|-T|--upload-file)(\s|=|$)")
HTTP_CLIENTS = {"curl", "invoke-restmethod", "invoke-webrequest", "irm", "iwr"}


def ask(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason + " Подтвердите, что пользователь дал на это команду.",
        }
    }, ensure_ascii=False))
    sys.exit(0)


class Rules:
    def __init__(self, config: dict[str, list[str]]):
        self.hosts = "|".join(f"(?:{h})" for h in config["write_hosts"])
        self.apply_scripts = {p.replace("\\", "/").removeprefix("./") for p in config["apply_scripts"]}
        self.client_stems = [Path(p).stem for p in config["client_files"]]
        self.methods = self.client_write_methods(config["client_files"])

    @staticmethod
    def client_write_methods(files: list[str]) -> set[str]:
        """Методы клиентов, которые пишут: тело содержит _post/_put/_delete или POST/PUT/DELETE."""
        names: set[str] = set()
        for client in files:
            try:
                text = (ROOT / client).read_text(encoding="utf-8")
            except OSError:
                continue
            for match in re.finditer(r"^    def (\w+)\(.*?(?=^    def |\Z)", text, re.S | re.M):
                name = match.group(1)
                if name.startswith(("_", "get_", "search_")):  # поиск бывает POST-ом, но это чтение
                    continue
                if re.search(r"self\._(post|put|delete)\(|[\"'](POST|PUT|PATCH|DELETE)[\"']", match.group(0)):
                    names.add(name)
        return names

    def mentions_system(self, text: str) -> bool:
        if self.hosts and re.search(self.hosts, text):
            return True
        return any(stem in text for stem in self.client_stems)

    def writes_found(self, text: str) -> str | None:
        """Первая найденная примета записи в коде скрипта."""
        if self.methods:
            m = re.search(r"\.(" + "|".join(sorted(self.methods)) + r")\(", text)
            if m:
                return f"вызов {m.group(1)}()"
        m = HTTP_WRITE_RE.search(text)
        if m and self.mentions_system(text):
            return f"запрос на запись ({m.group(0).strip()})"
        return None


def resolve(path: str, cwd: str) -> Path | None:
    for base in (Path(cwd or ROOT), ROOT):
        candidate = Path(path) if Path(path).is_absolute() else base / path
        try:
            candidate = candidate.resolve()
            candidate.relative_to(ROOT)
        except (OSError, ValueError):
            continue
        if candidate.is_file():
            return candidate
    return None


def check_script(script: Path, args: list[str], rules: Rules) -> None:
    rel = script.relative_to(ROOT).as_posix()
    if rel in rules.apply_scripts:
        if "--apply" in args:
            ask(f"Запись во внешнюю систему: {rel} с --apply.")
        return
    try:
        text = script.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return
    if "--dry-run" in args and "--dry-run" in text:
        return
    found = rules.writes_found(text)
    if found:
        ask(f"Скрипт {rel} пишет во внешнюю систему ({found}).")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        return 0
    try:
        rules = Rules(hook_config.load())
    except hook_config.ConfigError as exc:
        ask(str(exc) + ".")  # без настроек не знаем, что пишет наружу: спрашиваем на всё
    if not (rules.hosts or rules.apply_scripts or rules.client_stems):
        return 0
    cwd = payload.get("cwd") or str(ROOT)

    for seg in segments(command):
        kind, target, args = python_target(seg)
        if kind == "script" and target:
            script = resolve(target, cwd)
            if script is not None and script.parent.name != "hooks":
                check_script(script, args, rules)
        elif kind in ("code", "stdin") and target:
            found = rules.writes_found(target)
            if found:
                ask(f"Python-код в команде пишет во внешнюю систему ({found}).")

        ps1 = powershell_script(seg)
        if ps1 and rules.hosts:
            script = resolve(ps1, cwd)
            if script is not None:
                text = script.read_text(encoding="utf-8-sig", errors="replace")
                if re.search(rules.hosts, text) and HTTP_WRITE_RE.search(text):
                    ask(f"Скрипт {script.relative_to(ROOT).as_posix()} пишет во внешнюю систему.")

        if seg.exe in HTTP_CLIENTS and rules.hosts and re.search(rules.hosts, seg.text):
            if HTTP_WRITE_RE.search(seg.text) or (seg.exe == "curl" and CURL_WRITE_RE.search(seg.text)):
                ask("Прямой HTTP-запрос на запись во внешнюю систему.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
