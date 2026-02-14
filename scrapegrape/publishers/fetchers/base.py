"""Base types for the fetch strategy module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class FetchResult:
    """Result of a fetch attempt."""

    html: str
    status_code: int
    strategy_used: str
    url: str


class BaseFetcher(Protocol):
    """Protocol that all fetch strategies must implement."""

    name: str

    def fetch(self, url: str) -> FetchResult:
        """Fetch a URL and return the result. Raises FetchError on failure."""
        ...
