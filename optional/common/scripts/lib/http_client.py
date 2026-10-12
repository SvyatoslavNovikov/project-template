# -*- coding: utf-8 -*-
"""HTTP-клиент интеграций (только stdlib): JSON-запросы и защита записи.

ApiClient — база клиентов Jira, Confluence и Test IT. Чтение (_get) идёт всегда.
Запись (_post, _put, _delete) без apply=True не отправляется: клиент печатает,
что отправил бы, и возвращает DRY_RUN. Так dry-run — поведение по умолчанию,
а не флаг, который можно забыть.

Токены берутся из окружения в клиентах-наследниках и не печатаются: в план
dry-run попадают метод, путь и тело, но не заголовки.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

DRY_RUN: dict[str, Any] = {"dryRun": True}


class ApiError(RuntimeError):
    def __init__(self, method: str, url: str, status: int, body: str):
        super().__init__(f"HTTP {status} {method} {url}: {body[:2000]}")
        self.method = method
        self.url = url
        self.status = status
        self.body = body


def request_json(
    method: str,
    url: str,
    *,
    auth_header: str,
    body: dict[str, Any] | list[Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    """Выполнить запрос и вернуть распарсенный JSON (или {} при пустом теле)."""
    data = None
    headers = {"Authorization": auth_header, "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json; charset=utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raise ApiError(method, url, exc.code, exc.read().decode("utf-8", errors="replace")) from exc


def build_query(params: dict[str, Any]) -> str:
    return urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})


def summarize(body: Any, limit: int = 600) -> str:
    text = json.dumps(body, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + f"… ({len(text)} символов)"


class ApiClient:
    """База клиентов: base_url, заголовок авторизации, dry-run для записи."""

    def __init__(self, base_url: str, auth_header: str, *, apply: bool = False,
                 log: Callable[[str], None] = print):
        if not base_url:
            raise RuntimeError("не задан адрес сервиса (переменная окружения или config)")
        self.base_url = base_url.rstrip("/")
        self._auth_header = auth_header
        self.apply = apply
        self.log = log
        self.planned: list[tuple[str, str, Any]] = []

    def _get(self, path: str) -> Any:
        return request_json("GET", f"{self.base_url}{path}", auth_header=self._auth_header)

    def _query(self, path: str, body: Any) -> Any:
        """Чтение через POST (поиск с фильтром в теле): отправляется и в dry-run.
        Только для эндпоинтов, которые ничего не меняют."""
        return request_json("POST", f"{self.base_url}{path}", auth_header=self._auth_header, body=body)

    def _write(self, method: str, path: str, body: Any = None) -> Any:
        if not self.apply:
            self.planned.append((method, path, body))
            self.log(f"DRY-RUN {method} {path}" + (f"\n  {summarize(body)}" if body is not None else ""))
            return DRY_RUN
        return request_json(method, f"{self.base_url}{path}", auth_header=self._auth_header, body=body)

    def _post(self, path: str, body: Any = None) -> Any:
        return self._write("POST", path, body)

    def _put(self, path: str, body: Any = None) -> Any:
        return self._write("PUT", path, body)

    def _delete(self, path: str) -> Any:
        return self._write("DELETE", path)


def env_token(name: str) -> str:
    """Токен из окружения; в сообщении об ошибке — только имя переменной."""
    import os

    token = os.environ.get(name, "").strip()
    if len(token) < 10:
        raise RuntimeError(f"{name} не задан или слишком короткий")
    return token
