# -*- coding: utf-8 -*-
"""PreToolUse(Bash|PowerShell): блокирует хардкод токенов в команде и попытки добавить
в git каталоги сырых выгрузок (export_dirs из config.json). Пути берутся только из
аргументов git add/commit (разбор — command_parse.py): упоминание каталога в тексте
коммита или here-doc не мешает.

Хук читает JSON вызова инструмента из stdin. Exit 0 без вывода = пропустить.
Печать JSON с hookSpecificOutput.permissionDecision=deny = заблокировать.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hook_config  # noqa: E402
from command_parse import git_paths, segments  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

LITERAL = r"\s*=\s*['\"]?[A-Za-z0-9_\-\.]{10,}"
GENERIC_SECRET = re.compile(r"\b[A-Z][A-Z0-9_]*(TOKEN|SECRET|PASSWORD|API_KEY)" + LITERAL)
AUTH_HEADER_LITERAL = re.compile(r"(Bearer|PrivateToken)\s+[A-Za-z0-9_\-\.]{15,}")


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        return 0
    try:
        config = hook_config.load()
    except hook_config.ConfigError:
        config = {key: [] for key in hook_config.KEYS}  # общие проверки работают; о сломанном файле скажет external_write_guard

    names = [re.escape(n) for n in config["secret_env"]]
    named = re.compile(r"\b(" + "|".join(names) + r")" + LITERAL) if names else None
    if GENERIC_SECRET.search(command) or (named and named.search(command)):
        deny(
            "Похоже на хардкод токена прямо в команде. Используйте переменную окружения "
            "(в PowerShell: $env:ИМЯ), не значение литералом."
        )

    if AUTH_HEADER_LITERAL.search(command):
        deny(
            "В команде похоже на настоящее значение заголовка Authorization "
            "(Bearer/PrivateToken ...). Не печатать и не коммитить токены."
        )

    dirs = [d.strip("/") for d in config["export_dirs"] if d.strip("/")]
    if dirs:
        dirs_re = re.compile(r"(^|/)(" + "|".join(re.escape(d) for d in dirs) + r")(/|$)")
        # Только пути-аргументы git add/commit, а не упоминания в тексте коммита или here-doc.
        found = [
            path
            for seg in segments(command)
            for path in git_paths(seg)[1]
            if dirs_re.search(path.replace("\\", "/"))
        ]
        if found:
            deny(
                "Команда добавляет в git каталог сырых выгрузок ("
                + ", ".join(dirs)
                + "): они в .gitignore намеренно и могут содержать чувствительные данные. "
                "Если это осознанно — уберите путь из команды и спросите пользователя."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
