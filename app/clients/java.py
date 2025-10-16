from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from app.services.exceptions import DownstreamServiceError

logger = logging.getLogger(__name__)


class JavaServiceClient:
    """Async HTTP client responsible for communicating with the Java backend."""

    def __init__(
        self,
        base_url: str | None,
        *,
        timeout: float = 10.0,
        use_mock_data: bool = True,
        token: str | None = None,
    ) -> None:
        self._base_url = str(base_url).rstrip("/") if base_url else None
        self._timeout = timeout
        self.use_mock_data = use_mock_data or not self._base_url
        self._headers = {"Authorization": f"Bearer {token}"} if token else None
        self._headers.update({
              "Content-Type": "application/json",
            "Accept": "application/json"
        })
        self._client: Optional[httpx.AsyncClient] = None
        if not self.use_mock_data and self._base_url:
            self._client = self._build_client()

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            headers=self._headers,
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self.use_mock_data or not self._base_url:
            raise RuntimeError("HTTP client requested while running in mock mode")
        if self._client is None:
            self._client = self._build_client()
        return self._client

    async def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.use_mock_data:
            raise RuntimeError("Real HTTP call requested while mock mode is enabled")
        client = await self._ensure_client()
        try:
            print(f"--- Sending to Java API ---\nURL: {path}\nPayload: {payload}\n--------------------------")
            response = await client.post(path, json=payload)
            print(response.status_code)
            print(response.text)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("Java service returned error %s", exc.response.status_code)
            raise DownstreamServiceError(
                "Java service returned an error response",
                status_code=exc.response.status_code,
                cause=exc,
            ) from exc
        except httpx.RequestError as exc:
            logger.exception("Unable to reach Java service: %s", exc)
            raise DownstreamServiceError(
                "Unable to reach Java service", status_code=None, cause=exc
            ) from exc

    async def get(
        self, path: str, params: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        if self.use_mock_data:
            raise RuntimeError("Real HTTP call requested while mock mode is enabled")
        client = await self._ensure_client()
        try:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("Java service returned error %s", exc.response.status_code)
            raise DownstreamServiceError(
                "Java service returned an error response",
                status_code=exc.response.status_code,
                cause=exc,
            ) from exc
        except httpx.RequestError as exc:
            logger.exception("Unable to reach Java service: %s", exc)
            raise DownstreamServiceError(
                "Unable to reach Java service", status_code=None, cause=exc
            ) from exc

    async def simulate_latency(self) -> None:
        """Allow services to await for latency even when mocking responses."""

        await asyncio.sleep(0)

