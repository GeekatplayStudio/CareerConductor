"""Scraper base: fetches official public job-board JSON APIs politely.

Deliberately does not attempt to evade bot detection (no fingerprint spoofing,
no mouse-path emulation). These are documented public endpoints intended for
programmatic consumption; we identify ourselves honestly and rate-limit.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator

import httpx

from careerconductor.config.settings import settings

USER_AGENT = "CareerConductor/0.1 (personal job-search tool; contact via geekatplay@gmail.com)"


@dataclass
class RawJobPosting:
    company_name: str
    job_id: str
    title: str
    location: str
    url: str
    raw_payload: str


class PoliteClient:
    """Shared HTTP client enforcing a minimum delay between requests to any host."""

    def __init__(self, min_delay_seconds: float | None = None):
        self.min_delay = min_delay_seconds if min_delay_seconds is not None else settings.min_request_delay_seconds
        self._last_request_at: float = 0.0
        self._client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15.0)

    def get(self, url: str, **kwargs) -> httpx.Response:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        response = self._client.get(url, **kwargs)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    def close(self) -> None:
        self._client.close()


class BaseBoardScraper:
    board_type: str = "base"

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient()

    def fetch(self, company_name: str, board_token: str) -> Iterator[RawJobPosting]:
        raise NotImplementedError
