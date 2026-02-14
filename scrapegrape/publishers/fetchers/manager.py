"""FetchStrategyManager: orchestrates fetch strategies with fallback and publisher memory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from .base import FetchResult
from .curl_cffi_fetcher import CurlCffiFetcher
from .exceptions import AllStrategiesExhausted, FetchError
from .zyte_fetcher import ZyteFetcher

if TYPE_CHECKING:
    from publishers.models import Publisher


class FetchStrategyManager:
    """Tries fetch strategies in order, with automatic fallback and per-publisher memory."""

    STRATEGIES = ["curl_cffi", "zyte"]

    def __init__(self) -> None:
        self._fetchers: dict[str, CurlCffiFetcher | ZyteFetcher] = {
            "curl_cffi": CurlCffiFetcher(),
            "zyte": ZyteFetcher(),
        }

    def fetch(self, url: str, publisher: Publisher | None = None) -> FetchResult:
        """Fetch *url*, trying the remembered strategy first then falling back.

        When a fallback strategy succeeds the working strategy is saved on the
        publisher record so subsequent fetches start with it.
        """
        strategies = self._ordered_strategies(publisher)
        errors: list[FetchError] = []

        for strategy_name in strategies:
            fetcher = self._fetchers[strategy_name]
            try:
                result = fetcher.fetch(url)

                # Remember the working strategy on the publisher if it changed.
                if publisher and publisher.fetch_strategy != strategy_name:
                    publisher.fetch_strategy = strategy_name
                    publisher.save(update_fields=["fetch_strategy"])

                return result
            except FetchError as exc:
                logger.warning(f"Strategy {strategy_name} failed for {url}: {exc}")
                errors.append(exc)
                continue

        raise AllStrategiesExhausted(
            f"All strategies exhausted for {url}",
            errors=errors,
        )

    def _ordered_strategies(self, publisher: Publisher | None) -> list[str]:
        """Return strategy names with the publisher's preferred strategy first."""
        if publisher and publisher.fetch_strategy:
            preferred = publisher.fetch_strategy
            return [preferred] + [s for s in self.STRATEGIES if s != preferred]
        return list(self.STRATEGIES)
