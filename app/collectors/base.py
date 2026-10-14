import asyncio
import random
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import settings


class SourceRequestError(RuntimeError):
    """HTTP failure without a potentially sensitive request URL."""

    def __init__(self, message, *, retryable=False, status_code=None, throttled=False):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.throttled = throttled


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
        self.exhausted = False
        self.throttled = False
        self.failed = False
        self.retry_queue: list[dict[str, Any]] = []

    async def close(self):
        if self._owns_client:
            await self.client.aclose()

    async def request_json(self, url: str, *, params=None, headers=None):
        return await self._request_json("GET", url, params=params, headers=headers)

    async def request_json_post(self, url: str, *, json_body, headers=None):
        return await self._request_json("POST", url, json_body=json_body, headers=headers)

    async def request_json_post_or_none(self, url: str, *, json_body, headers=None):
        try:
            return await self.request_json_post(url, json_body=json_body, headers=headers)
        except SourceRequestError as exc:
            if exc.status_code == 404:
                self.exhausted = True
                return None
            raise

    async def request_json_or_none(self, url: str, *, params=None, headers=None):
        """Return None on 404 so paginators can treat missing pages as exhaustion."""
        try:
            return await self.request_json(url, params=params, headers=headers)
        except SourceRequestError as exc:
            if exc.status_code == 404:
                self.exhausted = True
                return None
            raise

    async def _request_json(self, method, url, *, params=None, json_body=None, headers=None):
        last_error = None
        attempts = 3
        for attempt in range(attempts):
            await asyncio.sleep(
                max(0, self.request_interval - (asyncio.get_event_loop().time() - self._last_request))
            )
            try:
                response = await self.client.request(
                    method, url, params=params, json=json_body, headers=headers
                )
                self._last_request = asyncio.get_event_loop().time()
                if response.status_code == 404:
                    raise SourceRequestError("HTTP 404", status_code=404)
                if response.status_code == 429:
                    last_error = SourceRequestError("HTTP 429", retryable=True, status_code=429, throttled=True)
                elif response.status_code in {500, 502, 503, 504}:
                    last_error = SourceRequestError(
                        f"HTTP {response.status_code}", retryable=True, status_code=response.status_code
                    )
                elif response.is_error:
                    raise SourceRequestError(f"HTTP {response.status_code}", status_code=response.status_code)
                else:
                    payload = response.json()
                    self.raw_responses.append(payload)
                    return payload
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = SourceRequestError(
                    "request timed out" if isinstance(exc, httpx.TimeoutException) else "connection failed",
                    retryable=True,
                )
            except SourceRequestError as exc:
                if exc.status_code == 404:
                    raise
                if not exc.retryable:
                    raise
                last_error = exc
            except ValueError:
                # A transient/truncated 200 response should not terminate a cursor walk
                # after a single occurrence. Treat malformed JSON like a retryable failure.
                self.raw_responses.append({"_raw_error": "invalid JSON response"})
                last_error = SourceRequestError("invalid JSON response", retryable=True)

            if last_error is None:
                continue
            if attempt < attempts - 1:
                if last_error.throttled:
                    self.throttled = True
                # 429 receives exponential backoff with jitter; transient network/5xx failures
                # use the same bounded retry policy.
                delay = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)

        self.failed = True
        self.throttled = bool(last_error and last_error.throttled)
        self.retry_queue.append({
            "source": self.source,
            "error": str(last_error or "request failed"),
            "attempts": attempts,
        })
        raise last_error or SourceRequestError("request failed after three attempts")

    @abstractmethod
    async def fetch(self, config: dict[str, Any]) -> list[dict[str, Any]]: ...

    @abstractmethod
    def normalize(self, raw_data: dict[str, Any], config: dict[str, Any]): ...
