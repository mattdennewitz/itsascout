"""ZyteFetcher: fallback fetcher using the Zyte API proxy service."""

from __future__ import annotations

import os
from base64 import b64decode

import requests

from .base import FetchResult
from .exceptions import FetchError


class ZyteFetcher:
    """Fetcher that uses the Zyte API for proxy-based page retrieval."""

    name = "zyte"

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def fetch(self, url: str) -> FetchResult:
        """Fetch *url* via Zyte API. Raises FetchError if API key is missing or request fails."""
        api_key = os.getenv("ZYTE_API_KEY")
        if not api_key:
            raise FetchError("ZYTE_API_KEY not set", strategy="zyte")

        try:
            api_response = requests.post(
                "https://api.zyte.com/v1/extract",
                auth=(api_key, ""),
                json={"url": url, "httpResponseBody": True},
                timeout=self.timeout,
            )
            api_response.raise_for_status()
        except requests.RequestException as exc:
            raise FetchError(
                f"Zyte API request failed: {exc}", strategy="zyte"
            ) from exc

        body = b64decode(api_response.json()["httpResponseBody"]).decode("utf-8")
        return FetchResult(
            html=body,
            status_code=200,
            strategy_used=self.name,
            url=url,
        )
