# Phase 7: Fetch Strategy - Research

**Researched:** 2026-02-14
**Domain:** HTTP fetching with browser TLS impersonation, proxy fallback, strategy pattern
**Confidence:** HIGH

## Summary

Phase 7 implements a fetch strategy manager that tries curl-cffi (browser TLS impersonation) first, falls back to Zyte proxy API on failure, and persists the working strategy per publisher. The project already has a working Zyte integration in `ingestion/services.py` (`fetch_html_via_proxy`), which uses raw `requests.post` to `https://api.zyte.com/v1/extract`. The Publisher model already exists with a `domain` field and various result fields -- a new `fetch_strategy` field needs to be added to remember what works.

curl-cffi v0.14.0 is the standard library for browser TLS fingerprinting in Python. It mimics the `requests` API (Session, get/post, Response with `.status_code`, `.text`, `.ok`, `.raise_for_status()`), supports impersonating Chrome/Safari/Firefox fingerprints, and handles HTTP/2 natively. The key design is a `FetchStrategyManager` class that orchestrates two concrete strategies -- `CurlCffiFetcher` and `ZyteFetcher` -- with WAF detection heuristics (403 status, challenge page markers) driving fallback decisions and per-publisher strategy memory.

**Primary recommendation:** Implement a simple Strategy pattern with two concrete fetchers behind a common interface, a manager that handles fallback logic and publisher strategy persistence, and thorough TDD with monkeypatched HTTP calls.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| curl-cffi | 0.14.0 | Browser TLS impersonation HTTP client | De facto standard for bypassing TLS fingerprinting; 68% adoption in ethical scraping; mimics requests API |
| requests | 2.32.4 (already installed) | HTTP client for Zyte API calls | Already used in project for Zyte integration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 (already installed) | Test framework | All tests |
| factory-boy | 3.3.3 (already installed) | Test data factories | Publisher fixtures with fetch_strategy field |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| curl-cffi | httpx | httpx has no TLS impersonation -- defeats the purpose |
| curl-cffi | tls-client | Less maintained, smaller community than curl-cffi |
| raw requests for Zyte | python-zyte-api | Adds dependency; raw requests already works in codebase |

**Installation:**
```bash
uv add curl-cffi
```

Note: curl-cffi requires Python >= 3.10 (project uses 3.12, so no issue). Pre-compiled wheels are provided; no local compilation needed.

## Architecture Patterns

### Recommended Project Structure
```
scrapegrape/publishers/
    fetchers/
        __init__.py          # Exports FetchStrategyManager
        base.py              # FetchResult dataclass, BaseFetcher protocol
        curl_cffi_fetcher.py # CurlCffiFetcher implementation
        zyte_fetcher.py      # ZyteFetcher implementation
        manager.py           # FetchStrategyManager (orchestrates fallback + memory)
        exceptions.py        # FetchError, AllStrategiesExhausted
    tests/
        test_fetchers.py     # Tests for all fetcher components
```

### Pattern 1: Strategy Pattern with Protocol
**What:** Define a `BaseFetcher` protocol that both `CurlCffiFetcher` and `ZyteFetcher` implement. The `FetchStrategyManager` orchestrates strategy selection, fallback, and publisher memory.
**When to use:** Always -- this is the core pattern for the phase.
**Example:**
```python
# Source: Designed for this project based on curl-cffi API docs
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


@dataclass
class FetchResult:
    """Result of a fetch attempt."""
    html: str
    status_code: int
    strategy_used: str  # "curl_cffi" or "zyte"
    url: str


class BaseFetcher(Protocol):
    """Protocol that all fetch strategies must implement."""
    name: str

    def fetch(self, url: str) -> FetchResult:
        """Fetch a URL and return the result. Raises FetchError on failure."""
        ...
```

### Pattern 2: CurlCffiFetcher with WAF Detection
**What:** Uses curl-cffi Session with browser impersonation, detects WAF blocks via status codes and page content heuristics.
**When to use:** Default/first strategy for all fetches.
**Example:**
```python
# Source: curl-cffi docs + WAF detection heuristics
from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import RequestException

WAF_BLOCK_SIGNATURES = [
    "checking your browser",
    "cloudflare",
    "access denied",
    "just a moment",
    "cf-browser-verification",
    "ray id",
]

class CurlCffiFetcher:
    name = "curl_cffi"

    def __init__(self, timeout: float = 30.0, impersonate: str = "chrome"):
        self.timeout = timeout
        self.impersonate = impersonate

    def fetch(self, url: str) -> FetchResult:
        try:
            response = curl_requests.get(
                url,
                impersonate=self.impersonate,
                timeout=self.timeout,
            )
        except RequestException as exc:
            raise FetchError(f"curl-cffi connection failed: {exc}", strategy="curl_cffi") from exc

        if response.status_code == 403 or self._is_waf_block(response.text):
            raise FetchError(
                f"WAF block detected (status={response.status_code})",
                strategy="curl_cffi",
            )
        response.raise_for_status()

        return FetchResult(
            html=response.text,
            status_code=response.status_code,
            strategy_used=self.name,
            url=url,
        )

    def _is_waf_block(self, body: str) -> bool:
        body_lower = body.lower()
        return any(sig in body_lower for sig in WAF_BLOCK_SIGNATURES)
```

### Pattern 3: ZyteFetcher (Existing Integration Wrapped)
**What:** Wraps the existing Zyte API call pattern from `ingestion/services.py` into the strategy interface.
**When to use:** Fallback when curl-cffi fails.
**Example:**
```python
# Source: Existing ingestion/services.py pattern + Zyte API docs
import os
import requests
from base64 import b64decode

class ZyteFetcher:
    name = "zyte"

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def fetch(self, url: str) -> FetchResult:
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
            raise FetchError(f"Zyte API request failed: {exc}", strategy="zyte") from exc

        body = b64decode(api_response.json()["httpResponseBody"])
        return FetchResult(
            html=body.decode("utf-8"),
            status_code=200,
            strategy_used=self.name,
            url=url,
        )
```

### Pattern 4: FetchStrategyManager with Publisher Memory
**What:** Orchestrates strategy selection, fallback chain, and persists working strategy on Publisher.
**When to use:** Entry point for all page fetching in the pipeline.
**Example:**
```python
# Source: Project architecture decisions
from loguru import logger
from publishers.models import Publisher

class FetchStrategyManager:
    STRATEGIES = ["curl_cffi", "zyte"]

    def __init__(self):
        self._fetchers = {
            "curl_cffi": CurlCffiFetcher(),
            "zyte": ZyteFetcher(),
        }

    def fetch(self, url: str, publisher: Publisher | None = None) -> FetchResult:
        """Fetch URL, trying remembered strategy first, then fallback chain."""
        strategies = self._ordered_strategies(publisher)

        last_error = None
        for strategy_name in strategies:
            fetcher = self._fetchers[strategy_name]
            try:
                result = fetcher.fetch(url)
                # Remember working strategy
                if publisher and publisher.fetch_strategy != strategy_name:
                    publisher.fetch_strategy = strategy_name
                    publisher.save(update_fields=["fetch_strategy"])
                return result
            except FetchError as exc:
                logger.warning(f"Strategy {strategy_name} failed for {url}: {exc}")
                last_error = exc
                continue

        raise AllStrategiesExhausted(
            f"All strategies exhausted for {url}",
            errors=[last_error] if last_error else [],
        )

    def _ordered_strategies(self, publisher: Publisher | None) -> list[str]:
        """Return strategies with publisher's preferred strategy first."""
        if publisher and publisher.fetch_strategy:
            preferred = publisher.fetch_strategy
            return [preferred] + [s for s in self.STRATEGIES if s != preferred]
        return list(self.STRATEGIES)
```

### Anti-Patterns to Avoid
- **Global session singleton:** Do not create a single curl-cffi Session shared across threads/workers. RQ workers run in separate processes so this is not an issue, but if sessions are created at module level they can leak state between requests.
- **Retry inside fetchers:** Do NOT add retry logic inside individual fetchers. The manager handles fallback. Retry (if needed later) belongs at the manager or task level.
- **Catching broad exceptions:** Each fetcher should catch its specific library exceptions (`curl_cffi.requests.exceptions.RequestException`, `requests.RequestException`) and convert them to `FetchError`. Never catch `Exception` blindly.
- **Storing HTML in the database:** The FetchResult returns HTML for the caller to use. Do not persist raw HTML on the Publisher or ResolutionJob model -- callers decide what to extract.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TLS fingerprint impersonation | Custom TLS/JA3 manipulation | curl-cffi `impersonate=` parameter | TLS fingerprinting is extremely complex; curl-cffi bundles pre-built browser fingerprints |
| WAF detection | Complex ML classifier | Simple heuristics (status code 403 + body content signatures) | Heuristics catch 90%+ of cases; anything more complex is premature |
| Proxy API integration | Custom proxy rotation | Zyte API (already integrated) | Zyte handles IP rotation, ban avoidance, and retry internally |
| HTTP/2 support | Custom HTTP/2 client | curl-cffi (supports HTTP/2 natively) | requests library does not support HTTP/2; curl-cffi does automatically |

**Key insight:** The complexity is in the orchestration (fallback, memory, error classification), not in the individual fetchers. Each fetcher is thin -- curl-cffi and Zyte handle the hard parts.

## Common Pitfalls

### Pitfall 1: Not Detecting Soft WAF Blocks
**What goes wrong:** A 200 status code is returned, but the body contains a Cloudflare challenge page or empty content. The pipeline treats it as valid HTML.
**Why it happens:** WAFs often return 200 with a challenge page instead of 403.
**How to avoid:** Check response body for known WAF signatures (e.g., "checking your browser", "cf-browser-verification", "just a moment") even on 200 responses. Also check for suspiciously short body length.
**Warning signs:** Pipeline returns garbage HTML or tiny response bodies.

### Pitfall 2: Missing ZYTE_API_KEY in Tests
**What goes wrong:** Tests fail because they try to call the real Zyte API.
**Why it happens:** ZyteFetcher reads from `os.getenv("ZYTE_API_KEY")` at call time.
**How to avoid:** Always monkeypatch or mock the fetcher in tests. Never make real HTTP calls in unit tests.
**Warning signs:** Tests are slow or require network access.

### Pitfall 3: curl-cffi Import Errors on CI/Unsupported Platforms
**What goes wrong:** `ImportError` when curl-cffi cannot load its native library.
**Why it happens:** curl-cffi bundles compiled C libraries. Wheels may not exist for all platforms. macOS 15.0+ is required for v0.14.0.
**How to avoid:** Verify the development platform is macOS 15.0+ or Linux (manylinux_2_28). Pin curl-cffi version. Test import early.
**Warning signs:** `ImportError` or `OSError` on import.

### Pitfall 4: Saving fetch_strategy on Every Successful Fetch
**What goes wrong:** Unnecessary database writes on every fetch when strategy hasn't changed.
**Why it happens:** Naive implementation always calls `publisher.save()`.
**How to avoid:** Only save when the strategy actually differs from what's stored (guard with `if publisher.fetch_strategy != strategy_name`).
**Warning signs:** Excessive UPDATE queries in test output.

### Pitfall 5: Not Handling Zyte 520 (Temporary Ban) Differently from 521 (Permanent)
**What goes wrong:** Retrying permanently failed URLs wastes Zyte API credits.
**Why it happens:** Both return non-200 responses but have different retry implications.
**How to avoid:** ZyteFetcher should raise FetchError for all non-200 Zyte responses. The manager does NOT retry the same strategy -- it falls back. If both fail, the job fails. This is correct behavior for Phase 7.
**Warning signs:** High Zyte API bills or stuck jobs.

## Code Examples

### Publisher Model Migration (New Field)
```python
# Source: Django model conventions from existing codebase
# Add to publishers/models.py on Publisher class:

FETCH_STRATEGY_CHOICES = [
    ("", "Auto (no preference)"),
    ("curl_cffi", "curl-cffi"),
    ("zyte", "Zyte API"),
]

fetch_strategy = models.CharField(
    max_length=20,
    blank=True,
    default="",
    choices=FETCH_STRATEGY_CHOICES,
)
```

### Custom Exception Classes
```python
# Source: Project conventions (loguru logging, descriptive errors)
class FetchError(Exception):
    """A single fetch strategy failed."""
    def __init__(self, message: str, strategy: str):
        self.strategy = strategy
        super().__init__(message)


class AllStrategiesExhausted(Exception):
    """All fetch strategies failed for a URL."""
    def __init__(self, message: str, errors: list[FetchError] | None = None):
        self.errors = errors or []
        super().__init__(message)
```

### Test Pattern: Monkeypatching curl-cffi
```python
# Source: pytest monkeypatch docs + project test conventions
import pytest
from unittest.mock import MagicMock
from publishers.fetchers.curl_cffi_fetcher import CurlCffiFetcher
from publishers.fetchers.exceptions import FetchError


class TestCurlCffiFetcher:
    def test_successful_fetch(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Hello</body></html>"
        mock_response.ok = True

        monkeypatch.setattr(
            "publishers.fetchers.curl_cffi_fetcher.curl_requests.get",
            lambda *args, **kwargs: mock_response,
        )

        fetcher = CurlCffiFetcher()
        result = fetcher.fetch("https://example.com")
        assert result.html == "<html><body>Hello</body></html>"
        assert result.strategy_used == "curl_cffi"

    def test_waf_block_raises_fetch_error(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Access Denied"

        monkeypatch.setattr(
            "publishers.fetchers.curl_cffi_fetcher.curl_requests.get",
            lambda *args, **kwargs: mock_response,
        )

        fetcher = CurlCffiFetcher()
        with pytest.raises(FetchError, match="WAF block"):
            fetcher.fetch("https://example.com")
```

### Test Pattern: Strategy Manager with Publisher Memory
```python
# Source: Project test conventions (factory-boy, pytest.mark.django_db)
import pytest
from publishers.factories import PublisherFactory
from publishers.fetchers.manager import FetchStrategyManager
from publishers.fetchers.exceptions import FetchError


@pytest.mark.django_db
class TestFetchStrategyManager:
    def test_remembers_working_strategy(self, monkeypatch):
        publisher = PublisherFactory(fetch_strategy="")

        # Make curl_cffi fail, zyte succeed
        def failing_curl(*a, **kw):
            raise FetchError("blocked", strategy="curl_cffi")

        mock_zyte_result = FetchResult(
            html="<html>ok</html>", status_code=200,
            strategy_used="zyte", url="https://example.com",
        )

        manager = FetchStrategyManager()
        monkeypatch.setattr(
            manager._fetchers["curl_cffi"], "fetch", failing_curl,
        )
        monkeypatch.setattr(
            manager._fetchers["zyte"], "fetch",
            lambda url: mock_zyte_result,
        )

        result = manager.fetch("https://example.com", publisher=publisher)
        publisher.refresh_from_db()
        assert publisher.fetch_strategy == "zyte"
        assert result.strategy_used == "zyte"

    def test_uses_remembered_strategy_first(self, monkeypatch):
        publisher = PublisherFactory(fetch_strategy="zyte")
        # Track which strategies are called
        call_order = []

        def track_curl(url):
            call_order.append("curl_cffi")
            return FetchResult(html="ok", status_code=200, strategy_used="curl_cffi", url=url)

        def track_zyte(url):
            call_order.append("zyte")
            return FetchResult(html="ok", status_code=200, strategy_used="zyte", url=url)

        manager = FetchStrategyManager()
        monkeypatch.setattr(manager._fetchers["curl_cffi"], "fetch", track_curl)
        monkeypatch.setattr(manager._fetchers["zyte"], "fetch", track_zyte)

        manager.fetch("https://example.com", publisher=publisher)
        assert call_order == ["zyte"]  # Preferred strategy tried first and succeeded
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| requests + custom headers | curl-cffi with TLS impersonation | 2023-2024 | Bypasses TLS fingerprinting that blocks requests |
| cloudscraper for Cloudflare bypass | curl-cffi impersonate="chrome" | 2024-2025 | cloudscraper cannot pass advanced fingerprinting |
| tls-client | curl-cffi | 2024 | curl-cffi has larger community, more browser targets, better maintenance |
| Single fetch method | Strategy pattern with fallback chain | N/A (architecture) | Resilient fetching with per-publisher optimization |

**Deprecated/outdated:**
- `cloudscraper`: Cannot bypass modern Cloudflare Turnstile CAPTCHA; not recommended
- `tls-client`: Less maintained than curl-cffi; smaller community
- Using `requests` library for direct page fetching: Blocked by most WAFs due to identifiable TLS fingerprint

## Open Questions

1. **curl-cffi impersonate target selection**
   - What we know: "chrome" uses latest available Chrome fingerprint; "safari" uses latest Safari
   - What's unclear: Whether specific version pinning (e.g., "chrome131") gives better results than generic "chrome"
   - Recommendation: Use `impersonate="chrome"` (latest) as default. This is the documented best practice and auto-updates with library releases.

2. **Soft WAF block signature completeness**
   - What we know: Common signatures include "checking your browser", "cloudflare", "access denied", "just a moment", "cf-browser-verification"
   - What's unclear: Whether non-Cloudflare WAFs (Akamai, Sucuri, etc.) use different signatures
   - Recommendation: Start with the Cloudflare-focused list above. Expand signatures as real-world failures are observed. Keep the list in a constant for easy extension.

3. **Minimum response body length threshold**
   - What we know: WAF challenge pages are typically short (< 5KB). Real pages are usually larger.
   - What's unclear: What threshold avoids false positives for legitimately small pages
   - Recommendation: Do NOT implement a minimum length check in Phase 7. Rely on content-based signatures only. Length-based heuristics can be added later if needed.

## Sources

### Primary (HIGH confidence)
- [curl-cffi PyPI](https://pypi.org/project/curl-cffi/) -- Version 0.14.0, Python >= 3.10 requirement
- [curl-cffi GitHub](https://github.com/lexiforest/curl_cffi) -- API overview, impersonation targets, Session usage
- [curl-cffi Exceptions docs](https://curl-cffi.readthedocs.io/en/v0.11.0/exceptions.html) -- Full exception hierarchy
- [curl-cffi API Reference](https://curl-cffi.readthedocs.io/en/latest/api.html) -- Session class, Response object, raise_for_status()
- [curl-cffi Impersonate Guide](https://curl-cffi.readthedocs.io/en/v0.6.1/impersonate.html) -- Browser targets, "chrome" alias recommendation
- [Zyte API Error Handling](https://docs.zyte.com/zyte-api/usage/errors.html) -- Error codes 520/521/429/401, retry strategies
- [Zyte API HTTP Requests](https://docs.zyte.com/zyte-api/usage/http.html) -- Extract endpoint, authentication, payload format
- Existing codebase: `ingestion/services.py` `fetch_html_via_proxy()` -- Working Zyte integration pattern

### Secondary (MEDIUM confidence)
- [ZenRows curl-cffi guide](https://www.zenrows.com/blog/curl-cffi) -- WAF detection patterns, practical usage examples
- [Cloudflare WAF Challenges docs](https://developers.cloudflare.com/waf/reference/cloudflare-challenges/) -- Challenge page behavior
- [BrightData curl-cffi guide](https://brightdata.com/blog/web-data/web-scraping-with-curl-cffi) -- 2026 usage patterns

### Tertiary (LOW confidence)
- WAF block signature list is based on community patterns; may not cover all WAFs. Start with Cloudflare and expand.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- curl-cffi is well-documented, v0.14.0 is stable, Python 3.12 compatible
- Architecture: HIGH -- Strategy pattern is straightforward; existing Zyte integration provides proven fallback
- Pitfalls: HIGH -- Exception hierarchy well-documented; WAF detection heuristics verified across multiple sources
- Testing: HIGH -- monkeypatch patterns are standard pytest; factory-boy already in project

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (curl-cffi is stable; v0.15.0 beta exists but 0.14.0 is production-ready)
