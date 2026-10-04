import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import settings


class SourceRequestError(RuntimeError):
    """HTTP failure without a potentially sensitive request URL."""

    def __init__(self, message, *, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class BaseCollector(ABC):
    source = "base"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(
            timeout=settings.request_timeout,
            headers={
                "User-Agent": "TechJobsAggregator/0.1 (public job listings; contact: admin@example.invalid)",
                "Accept": "application/json",
            },
        )
        self._owns_client = client is None
        self._last_request = 0.0
        self.request_interval = 0.5
        self.raw_responses = []

    async def close(self):
        if self._owns_client:
            await self.client.aclose()

    async def request_json(self, url: str, *, params=None, headers=None):
        return await self._request_json("GET", url, params=params, headers=headers)

    async def request_json_post(self, url: str, *, json_body, headers=None):
        return await self._request_json("POST", url, json_body=json_body, headers=headers)

    async def _request_json(self, method, url, *, params=None, json_body=None, headers=None):
        def transient(exc):
            return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)) or (
                isinstance(exc, SourceRequestError)
                and (
                    exc.retryable
                    or (
                        str(exc).split()[-1].isdigit()
                        and int(str(exc).split()[-1]) in {429, 500, 502, 503, 504}
                    )
                )
            )

        @retry(
            stop=stop_after_attempt(settings.max_retries),
            wait=wait_exponential(multiplier=0.5, max=8),
            retry=retry_if_exception(transient),
            reraise=True,
        )
        async def _get():
            await asyncio.sleep(
                max(
                    0,
                    self.request_interval - (asyncio.get_event_loop().time() - self._last_request),
                )
            )
            try:
                response = await self.client.request(
                    method, url, params=params, json=json_body, headers=headers
                )
            except httpx.TimeoutException:
                raise SourceRequestError("request timed out", retryable=True) from None
            except httpx.ConnectError:
                raise SourceRequestError("connection failed", retryable=True) from None
            self._last_request = asyncio.get_event_loop().time()
            if response.is_error:
                raise SourceRequestError(f"HTTP {response.status_code}")
            try:
                payload = response.json()
            except ValueError:
                self.raw_responses.append({"_raw_text": response.text})
                raise
            self.raw_responses.append(payload)
            return payload

        return await _get()

    @abstractmethod
    async def fetch(self, config: dict[str, Any]) -> list[dict[str, Any]]: ...
    @abstractmethod
    def normalize(self, raw_data: dict[str, Any], config: dict[str, Any]): ...
