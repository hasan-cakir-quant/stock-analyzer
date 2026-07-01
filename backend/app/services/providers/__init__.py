"""Pluggable data-source layer.

Every external source is a :class:`DataProvider` adapter advertising one or more
:class:`Capability` values. The public app ships three adapters:

  * :class:`SecEdgarProvider`  — fundamentals (SEC EDGAR official API)
  * :class:`YFinanceProvider`  — market data (Yahoo Finance via yfinance)
  * :class:`WikipediaProvider` — index constituents (Wikimedia API)

Import the shared singletons (``sec_provider`` / ``yfinance_provider`` /
``wikipedia_provider``) or look one up by capability via :func:`provider_for`.
Adding a source is local: write an adapter and register it here.
"""

from __future__ import annotations

from app.services.providers.base import (
    Capability,
    ClosingPriceResult,
    DataProvider,
    MarketSnapshot,
    ProviderError,
    UnsupportedCapability,
)
from app.services.providers.sec_edgar import SecEdgarProvider, SecLookupError
from app.services.providers.wikipedia import WikipediaProvider
from app.services.providers.yfinance import YFinanceProvider

sec_provider = SecEdgarProvider()
yfinance_provider = YFinanceProvider()
wikipedia_provider = WikipediaProvider()

_REGISTRY: tuple[DataProvider, ...] = (
    sec_provider,
    yfinance_provider,
    wikipedia_provider,
)


def all_providers() -> tuple[DataProvider, ...]:
    return _REGISTRY


def provider_for(capability: Capability) -> DataProvider:
    """Return the first registered provider advertising ``capability``."""
    for provider in _REGISTRY:
        if provider.supports(capability):
            return provider
    raise ProviderError(f"No provider registered for capability '{capability.value}'.")


__all__ = [
    "Capability",
    "ClosingPriceResult",
    "DataProvider",
    "MarketSnapshot",
    "ProviderError",
    "UnsupportedCapability",
    "SecEdgarProvider",
    "SecLookupError",
    "WikipediaProvider",
    "YFinanceProvider",
    "sec_provider",
    "yfinance_provider",
    "wikipedia_provider",
    "all_providers",
    "provider_for",
]
