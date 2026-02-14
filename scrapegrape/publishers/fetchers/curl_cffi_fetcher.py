"""CurlCffiFetcher: browser TLS impersonation via curl-cffi."""

from __future__ import annotations

from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import RequestException

from .base import FetchResult
from .exceptions import FetchError

WAF_BLOCK_SIGNATURES = [
    "checking your browser",
    "cloudflare",
    "access denied",
    "just a moment",
    "cf-browser-verification",
    "ray id",
]


class CurlCffiFetcher:
    """Fetcher using curl-cffi with browser TLS fingerprint impersonation."""

    name = "curl_cffi"

    def __init__(self, timeout: float = 30.0, impersonate: str = "chrome"):
        self.timeout = timeout
        self.impersonate = impersonate

    def fetch(self, url: str) -> FetchResult:
        """Fetch *url* using curl-cffi. Raises FetchError on WAF block or connection failure."""
        try:
            response = curl_requests.get(
                url,
                impersonate=self.impersonate,
                timeout=self.timeout,
            )
        except RequestException as exc:
            raise FetchError(
                f"curl-cffi connection failed: {exc}", strategy="curl_cffi"
            ) from exc

        if response.status_code == 403 or self._is_waf_block(response.text):
            raise FetchError(
                f"WAF block detected (status={response.status_code})",
                strategy="curl_cffi",
            )

        try:
            response.raise_for_status()
        except Exception as exc:
            raise FetchError(
                f"HTTP error {response.status_code}: {exc}", strategy="curl_cffi"
            ) from exc

        return FetchResult(
            html=response.text,
            status_code=response.status_code,
            strategy_used=self.name,
            url=url,
        )

    def _is_waf_block(self, body: str) -> bool:
        """Check if the response body contains known WAF challenge signatures."""
        body_lower = body.lower()
        return any(sig in body_lower for sig in WAF_BLOCK_SIGNATURES)
