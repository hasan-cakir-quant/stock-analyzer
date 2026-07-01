"""The DataProvider abstraction.

Every external data source is exposed as a swappable adapter that subclasses
``DataProvider``. The interface is *capability-based*: the three sources this
app ships with do genuinely different things —

  * SEC EDGAR  → company fundamentals (ticker→CIK lookup + XBRL companyfacts)
  * yfinance   → market data (live price/beta + historical closes)
  * Wikipedia  → index constituent lists (S&P 500 tickers)

so rather than forcing one uniform method set, each adapter declares which
``Capability`` values it supports and implements only those methods. Calling an
unsupported method raises ``UnsupportedCapability`` instead of returning a stub,
which keeps each adapter honest about what it actually provides.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from datetime import date
from enum import Enum


class Capability(str, Enum):
    """What a provider can do. An adapter advertises a subset of these."""

    FUNDAMENTALS = "fundamentals"  # ticker→CIK + financial statements
    MARKET_DATA = "market_data"  # live price/beta + historical closes
    CONSTITUENTS = "constituents"  # index membership lists


class ProviderError(RuntimeError):
    """A provider couldn't fulfil a request (network, parse, or upstream error)."""


class UnsupportedCapability(NotImplementedError):
    """Raised when a method is called on a provider that doesn't support it."""


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """A point-in-time market-data reading. Decimal-like values are carried as
    strings to avoid float-binary noise on the way to the API/DB."""

    symbol: str
    current_price: str | None
    beta: str | None
    source: str


@dataclass(frozen=True, slots=True)
class ClosingPriceResult:
    """One quarter's end-of-quarter close, or a reason it couldn't be resolved."""

    period: str
    end_date: date
    closing_price: str | None
    reason: str | None = None


class DataProvider(ABC):
    """Base class for every data-source adapter.

    Subclasses set ``name`` and ``capabilities`` and override the methods for
    the capabilities they advertise. The default method bodies raise
    ``UnsupportedCapability`` so an accidental call fails loudly.
    """

    name: str = "data-provider"
    capabilities: frozenset[Capability] = frozenset()

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    # — Capability.FUNDAMENTALS —————————————————————————————————————————————

    def lookup_cik(self, symbol: str) -> str | None:
        """Resolve a ticker to its zero-padded SEC CIK, or None if unlisted."""
        raise UnsupportedCapability(f"{self.name} does not provide fundamentals.")

    def fetch_company_facts(self, cik: str) -> str:
        """Return the raw XBRL companyfacts JSON payload for a CIK, as text."""
        raise UnsupportedCapability(f"{self.name} does not provide fundamentals.")

    # — Capability.MARKET_DATA ——————————————————————————————————————————————

    def get_market_snapshot(
        self, symbol: str, *, currency: str | None = None
    ) -> MarketSnapshot:
        """Return the live current price + beta for a symbol."""
        raise UnsupportedCapability(f"{self.name} does not provide market data.")

    def get_closing_prices(
        self,
        symbol: str,
        periods: list[tuple[str, date]],
        *,
        currency: str | None = None,
    ) -> list[ClosingPriceResult]:
        """Return the end-of-quarter close for each ``(period, end_date)`` pair —
        the last trading day on or before ``end_date``."""
        raise UnsupportedCapability(f"{self.name} does not provide market data.")

    # — Capability.CONSTITUENTS —————————————————————————————————————————————

    def get_constituents(self, index: str = "sp500") -> list[str]:
        """Return the current ticker symbols for a named index."""
        raise UnsupportedCapability(f"{self.name} does not provide constituents.")
