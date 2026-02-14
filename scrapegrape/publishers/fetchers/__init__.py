"""Fetch strategy module: curl-cffi default, Zyte API fallback, per-publisher memory."""

from .base import FetchResult
from .exceptions import AllStrategiesExhausted, FetchError
from .manager import FetchStrategyManager

__all__ = [
    "FetchStrategyManager",
    "FetchResult",
    "FetchError",
    "AllStrategiesExhausted",
]
