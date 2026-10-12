# -*- coding: utf-8 -*-
"""Клиент Jira (REST API v2: Server, Data Center, Cloud) поверх http_client.ApiClient.

Адрес — env JIRA_BASE_URL или base_url в scripts/jira.config.json. Токен — env JIRA_TOKEN:
Server/DC — Personal Access Token (Bearer), Cloud — API token с env JIRA_USER (auth: basic
в конфиге). Запись без apply=True не отправляется (dry-run, см. http_client).
"""
from __future__ import annotations

import base64
import os
from typing import Any

from http_client import ApiClient, build_query, env_token


class JiraClient(ApiClient):
    def __init__(self, config: dict[str, Any], *, apply: bool = False, log=print):
        token = env_token("JIRA_TOKEN")
        if config.get("auth", "bearer") == "basic":
            user = os.environ.get("JIRA_USER", "").strip()
            if not user:
                raise RuntimeError("auth: basic — нужен JIRA_USER (email учётной записи)")
            header = "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode()
        else:
            header = f"Bearer {token}"
        super().__init__(os.environ.get("JIRA_BASE_URL") or config.get("base_url", ""), header,
                         apply=apply, log=log)

    # --- чтение

    def myself(self) -> dict[str, Any]:
        return self._get("/rest/api/2/myself")

    def get_issue(self, key: str, fields: str | None = None) -> dict[str, Any]:
        query = f"?{build_query({'fields': fields})}" if fields else ""
        return self._get(f"/rest/api/2/issue/{key}{query}")

    def search(self, jql: str, fields: str = "summary,issuetype,status", limit: int = 50) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        while len(issues) < limit:
            page = self._get("/rest/api/2/search?" + build_query({
                "jql": jql, "fields": fields, "startAt": len(issues), "maxResults": min(100, limit - len(issues))}))
            batch = page.get("issues", [])
            issues += batch
            if not batch or len(issues) >= page.get("total", 0):
                break
        return issues

    def get_comments(self, key: str, limit: int = 3) -> list[dict[str, Any]]:
        data = self._get(f"/rest/api/2/issue/{key}/comment?" + build_query({"orderBy": "-created", "maxResults": limit}))
        return data.get("comments", [])[:limit]

    # --- запись (dry-run без apply)

    def create_issue(self, fields: dict[str, Any]) -> dict[str, Any]:
        return self._post("/rest/api/2/issue", {"fields": fields})

    def update_issue(self, key: str, fields: dict[str, Any]) -> dict[str, Any]:
        return self._put(f"/rest/api/2/issue/{key}", {"fields": fields})

    def link_issues(self, link_type: str, inward_key: str, outward_key: str) -> dict[str, Any]:
        return self._post("/rest/api/2/issueLink", {
            "type": {"name": link_type}, "inwardIssue": {"key": inward_key}, "outwardIssue": {"key": outward_key}})

    def add_remote_link(self, key: str, url: str, title: str) -> dict[str, Any]:
        return self._post(f"/rest/api/2/issue/{key}/remotelink", {"object": {"url": url, "title": title}})
