# -*- coding: utf-8 -*-
"""Клиент Test IT (REST API v2) поверх http_client.ApiClient.

Адрес — env TMS_BASE_URL или base_url в scripts/testit.config.json. Токен — env
TMS_PRIVATE_TOKEN, заголовок `Authorization: PrivateToken <токен>` (не Bearer).
Запись без apply=True не отправляется; поиск идёт через POST, но это чтение (_query).
"""
from __future__ import annotations

import os
from typing import Any

from http_client import DRY_RUN, ApiClient, ApiError, env_token


class TestItClient(ApiClient):
    def __init__(self, config: dict[str, Any], *, apply: bool = False, log=print):
        super().__init__(os.environ.get("TMS_BASE_URL") or config.get("base_url", ""),
                         f"PrivateToken {env_token('TMS_PRIVATE_TOKEN')}", apply=apply, log=log)

    # --- чтение

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self._get(f"/api/v2/projects/{project_id}")

    def get_work_item(self, work_item_id: str) -> dict[str, Any]:
        return self._get(f"/api/v2/workItems/{work_item_id}")

    def search_work_items(self, project_id: str, global_ids: list[int]) -> list[dict[str, Any]]:
        result = self._query("/api/v2/workItems/search", {
            "filter": {"isDeleted": False, "projectIds": [project_id], "globalIds": global_ids},
            "extractionModel": {}, "includes": {"steps": False, "attributes": False}})
        return result if isinstance(result, list) else result.get("items", [])

    # --- запись (dry-run без apply)

    def create_work_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/api/v2/workItems", payload)

    def update_work_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        """payload — полный work item с полем id (UUID)."""
        return self._put("/api/v2/workItems", payload)

    def create_autotest(self, external_id: str, name: str, project_id: str,
                        work_item_ids: list[str] | None = None) -> dict[str, Any] | None:
        """None — автотест с таким externalId уже есть (HTTP 409): результаты слать на него же."""
        body: dict[str, Any] = {"externalId": external_id, "name": name, "projectId": project_id}
        if work_item_ids:
            body["workItemIdsForLinkWithAutoTest"] = work_item_ids
        try:
            return self._post("/api/v2/autoTests", body)
        except ApiError as exc:
            if exc.status == 409:
                return None
            raise

    def create_test_run(self, configuration_id: str, work_item_ids: list[str]) -> dict[str, Any]:
        return self._post("/api/v2/testRuns/byConfigurations", {
            "testPointSelectors": [{"configurationId": configuration_id, "workItemIds": work_item_ids}]})

    def start_test_run(self, run_id: str) -> Any:
        return self._post(f"/api/v2/testRuns/{run_id}/start")

    def submit_test_results(self, run_id: str, results: list[dict[str, Any]]) -> Any:
        return self._post(f"/api/v2/testRuns/{run_id}/testResults", results)


__all__ = ["TestItClient", "DRY_RUN"]
