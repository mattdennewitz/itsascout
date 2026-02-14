"""Custom exceptions for the fetch strategy module."""

from __future__ import annotations


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
