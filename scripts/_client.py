"""Cliente HTTP compartido por los scripts: solo hablan con la API REST (principio X)."""

from __future__ import annotations

import os

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
TOKEN = os.environ.get("TOKEN_OPERADOR_PMU", "pmu-demo")


def api_client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        base_url=API_BASE_URL,
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=timeout,
    )
