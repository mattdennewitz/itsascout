"""Tests for the fetch strategy module: CurlCffiFetcher, ZyteFetcher, FetchStrategyManager."""

import base64
from unittest.mock import MagicMock

import pytest
import requests

from publishers.factories import PublisherFactory
from publishers.fetchers.base import FetchResult
from publishers.fetchers.curl_cffi_fetcher import CurlCffiFetcher
from publishers.fetchers.exceptions import AllStrategiesExhausted, FetchError
from publishers.fetchers.manager import FetchStrategyManager
from publishers.fetchers.zyte_fetcher import ZyteFetcher
from publishers.models import Publisher


# ---------------------------------------------------------------------------
# CurlCffiFetcher
# ---------------------------------------------------------------------------
class TestCurlCffiFetcher:
    def test_successful_fetch(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Hello</body></html>"

        monkeypatch.setattr(
            "publishers.fetchers.curl_cffi_fetcher.curl_requests.get",
            lambda *args, **kwargs: mock_response,
        )

        fetcher = CurlCffiFetcher()
        result = fetcher.fetch("https://example.com")

        assert result.html == "<html><body>Hello</body></html>"
        assert result.strategy_used == "curl_cffi"
        assert result.status_code == 200
        assert result.url == "https://example.com"

    def test_403_raises_fetch_error(self, monkeypatch):
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

    def test_waf_signature_on_200_raises_fetch_error(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Please wait... checking your browser</html>"

        monkeypatch.setattr(
            "publishers.fetchers.curl_cffi_fetcher.curl_requests.get",
            lambda *args, **kwargs: mock_response,
        )

        fetcher = CurlCffiFetcher()
        with pytest.raises(FetchError):
            fetcher.fetch("https://example.com")

    def test_connection_error_raises_fetch_error(self, monkeypatch):
        from curl_cffi.requests.exceptions import RequestException

        monkeypatch.setattr(
            "publishers.fetchers.curl_cffi_fetcher.curl_requests.get",
            MagicMock(side_effect=RequestException("Connection refused")),
        )

        fetcher = CurlCffiFetcher()
        with pytest.raises(FetchError) as exc_info:
            fetcher.fetch("https://example.com")
        assert exc_info.value.strategy == "curl_cffi"


# ---------------------------------------------------------------------------
# ZyteFetcher
# ---------------------------------------------------------------------------
class TestZyteFetcher:
    def test_successful_fetch(self, monkeypatch):
        monkeypatch.setenv("ZYTE_API_KEY", "fake-key")

        html_content = "<html>Zyte</html>"
        encoded = base64.b64encode(html_content.encode()).decode()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"httpResponseBody": encoded}
        mock_response.raise_for_status = MagicMock()

        monkeypatch.setattr(
            "publishers.fetchers.zyte_fetcher.requests.post",
            lambda *args, **kwargs: mock_response,
        )

        fetcher = ZyteFetcher()
        result = fetcher.fetch("https://example.com")

        assert result.html == "<html>Zyte</html>"
        assert result.strategy_used == "zyte"
        assert result.status_code == 200

    def test_missing_api_key_raises_fetch_error(self, monkeypatch):
        monkeypatch.delenv("ZYTE_API_KEY", raising=False)

        fetcher = ZyteFetcher()
        with pytest.raises(FetchError, match="ZYTE_API_KEY"):
            fetcher.fetch("https://example.com")

    def test_api_error_raises_fetch_error(self, monkeypatch):
        monkeypatch.setenv("ZYTE_API_KEY", "fake-key")

        monkeypatch.setattr(
            "publishers.fetchers.zyte_fetcher.requests.post",
            MagicMock(side_effect=requests.RequestException("API error")),
        )

        fetcher = ZyteFetcher()
        with pytest.raises(FetchError) as exc_info:
            fetcher.fetch("https://example.com")
        assert exc_info.value.strategy == "zyte"


# ---------------------------------------------------------------------------
# FetchStrategyManager
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestFetchStrategyManager:
    def test_default_uses_curl_cffi_first(self, monkeypatch):
        call_order = []

        curl_result = FetchResult(
            html="<html>curl</html>",
            status_code=200,
            strategy_used="curl_cffi",
            url="https://example.com",
        )

        def track_curl(url):
            call_order.append("curl_cffi")
            return curl_result

        def track_zyte(url):
            call_order.append("zyte")
            return FetchResult(
                html="<html>zyte</html>",
                status_code=200,
                strategy_used="zyte",
                url=url,
            )

        manager = FetchStrategyManager()
        monkeypatch.setattr(manager._fetchers["curl_cffi"], "fetch", track_curl)
        monkeypatch.setattr(manager._fetchers["zyte"], "fetch", track_zyte)

        result = manager.fetch("https://example.com")

        assert result.strategy_used == "curl_cffi"
        assert call_order == ["curl_cffi"]

    def test_falls_back_to_zyte_on_curl_cffi_failure(self, monkeypatch):
        def failing_curl(url):
            raise FetchError("blocked", strategy="curl_cffi")

        zyte_result = FetchResult(
            html="<html>zyte</html>",
            status_code=200,
            strategy_used="zyte",
            url="https://example.com",
        )

        manager = FetchStrategyManager()
        monkeypatch.setattr(manager._fetchers["curl_cffi"], "fetch", failing_curl)
        monkeypatch.setattr(
            manager._fetchers["zyte"], "fetch", lambda url: zyte_result
        )

        result = manager.fetch("https://example.com")
        assert result.strategy_used == "zyte"

    def test_remembers_working_strategy_on_publisher(self, monkeypatch):
        publisher = PublisherFactory(fetch_strategy="")

        def failing_curl(url):
            raise FetchError("blocked", strategy="curl_cffi")

        zyte_result = FetchResult(
            html="<html>ok</html>",
            status_code=200,
            strategy_used="zyte",
            url="https://example.com",
        )

        manager = FetchStrategyManager()
        monkeypatch.setattr(manager._fetchers["curl_cffi"], "fetch", failing_curl)
        monkeypatch.setattr(
            manager._fetchers["zyte"], "fetch", lambda url: zyte_result
        )

        result = manager.fetch("https://example.com", publisher=publisher)
        publisher.refresh_from_db()

        assert result.strategy_used == "zyte"
        assert publisher.fetch_strategy == "zyte"

    def test_no_db_write_when_strategy_unchanged(self, monkeypatch, django_assert_num_queries):
        publisher = PublisherFactory(fetch_strategy="curl_cffi")

        curl_result = FetchResult(
            html="<html>ok</html>",
            status_code=200,
            strategy_used="curl_cffi",
            url="https://example.com",
        )

        manager = FetchStrategyManager()
        monkeypatch.setattr(
            manager._fetchers["curl_cffi"], "fetch", lambda url: curl_result
        )

        # Should only SELECT (no UPDATE) since strategy hasn't changed
        with django_assert_num_queries(0):
            manager.fetch("https://example.com", publisher=publisher)

    def test_uses_remembered_strategy_first(self, monkeypatch):
        publisher = PublisherFactory(fetch_strategy="zyte")
        call_order = []

        def track_curl(url):
            call_order.append("curl_cffi")
            return FetchResult(
                html="ok", status_code=200, strategy_used="curl_cffi", url=url
            )

        def track_zyte(url):
            call_order.append("zyte")
            return FetchResult(
                html="ok", status_code=200, strategy_used="zyte", url=url
            )

        manager = FetchStrategyManager()
        monkeypatch.setattr(manager._fetchers["curl_cffi"], "fetch", track_curl)
        monkeypatch.setattr(manager._fetchers["zyte"], "fetch", track_zyte)

        manager.fetch("https://example.com", publisher=publisher)
        assert call_order == ["zyte"]

    def test_all_strategies_exhausted(self, monkeypatch):
        def failing_curl(url):
            raise FetchError("curl failed", strategy="curl_cffi")

        def failing_zyte(url):
            raise FetchError("zyte failed", strategy="zyte")

        manager = FetchStrategyManager()
        monkeypatch.setattr(manager._fetchers["curl_cffi"], "fetch", failing_curl)
        monkeypatch.setattr(manager._fetchers["zyte"], "fetch", failing_zyte)

        with pytest.raises(AllStrategiesExhausted):
            manager.fetch("https://example.com")

    def test_fetch_without_publisher_works(self, monkeypatch):
        curl_result = FetchResult(
            html="<html>ok</html>",
            status_code=200,
            strategy_used="curl_cffi",
            url="https://example.com",
        )

        manager = FetchStrategyManager()
        monkeypatch.setattr(
            manager._fetchers["curl_cffi"], "fetch", lambda url: curl_result
        )

        result = manager.fetch("https://example.com")
        assert result.html == "<html>ok</html>"


# ---------------------------------------------------------------------------
# Publisher fetch_strategy field
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestPublisherFetchStrategy:
    def test_fetch_strategy_field_exists(self):
        publisher = PublisherFactory()
        assert hasattr(publisher, "fetch_strategy")
        assert publisher.fetch_strategy == ""

    def test_fetch_strategy_choices(self):
        field = Publisher._meta.get_field("fetch_strategy")
        choice_values = [c[0] for c in field.choices]
        assert "" in choice_values
        assert "curl_cffi" in choice_values
        assert "zyte" in choice_values
