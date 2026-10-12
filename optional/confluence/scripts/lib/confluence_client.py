# -*- coding: utf-8 -*-
"""Клиент Confluence (REST API /rest/api/content: Server, Data Center, Cloud) поверх ApiClient.

Адрес — env CONF_BASE_URL или base_url в scripts/confluence.config.json (для Cloud —
с /wiki на конце). Токен — env CONF_TOKEN: Server/DC — Personal Access Token (Bearer),
Cloud — API token с env CONF_USER (auth: basic). Запись без apply=True не отправляется.
"""
from __future__ import annotations

import base64
import os
from typing import Any

from http_client import DRY_RUN, ApiClient, build_query, env_token


class ConfluenceClient(ApiClient):
    def __init__(self, config: dict[str, Any], *, apply: bool = False, log=print):
        token = env_token("CONF_TOKEN")
        if config.get("auth", "bearer") == "basic":
            user = os.environ.get("CONF_USER", "").strip()
            if not user:
                raise RuntimeError("auth: basic — нужен CONF_USER (email учётной записи)")
            header = "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode()
        else:
            header = f"Bearer {token}"
        super().__init__(os.environ.get("CONF_BASE_URL") or config.get("base_url", ""), header,
                         apply=apply, log=log)

    def get_page(self, page_id: str, expand: str = "body.storage,space,version,ancestors") -> dict[str, Any]:
        return self._get(f"/rest/api/content/{page_id}?{build_query({'expand': expand})}")

    def search(self, cql: str, limit: int = 25) -> list[dict[str, Any]]:
        data = self._get("/rest/api/content/search?" + build_query({"cql": cql, "limit": limit, "expand": "space,version"}))
        return data.get("results", [])

    def create_page(self, title: str, space_key: str, parent_id: str | None, storage: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {"storage": {"value": storage, "representation": "storage"}},
        }
        if parent_id:
            payload["ancestors"] = [{"id": str(parent_id)}]
        return self._post("/rest/api/content", payload)

    def update_page(self, page_id: str, storage: str, title: str | None = None, message: str = "") -> dict[str, Any]:
        """Новая версия страницы: номер версии читается с сервера (чтение идёт и в dry-run)."""
        current = self.get_page(page_id, expand="version")
        payload = {
            "type": "page",
            "title": title or current["title"],
            "body": {"storage": {"value": storage, "representation": "storage"}},
            "version": {"number": current["version"]["number"] + 1, "message": message},
        }
        return self._put(f"/rest/api/content/{page_id}", payload)


__all__ = ["ConfluenceClient", "DRY_RUN"]
