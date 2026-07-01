"""Yahoo Finance data provider — market-data adapter backed by yfinance.

Implements ``Capability.MARKET_DATA``:

  * ``get_market_snapshot`` — live current price + beta.
  * ``get_closing_prices`` — the end-of-quarter close (last trading day on or
    before each quarter's end date) for a set of periods.

Yahoo data is unofficial, so missing fields come back as ``None`` rather than
an error wherever possible; only an outright fetch failure raises
``ProviderError``. yfinance is imported lazily so the rest of the app still
imports cleanly if the optional dependency is absent.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.services.providers.base import (
    Capability,
    ClosingPriceResult,
    DataProvider,
    MarketSnapshot,
    ProviderError,
)

logger = logging.getLogger(__name__)

# Yahoo Finance ticker conventions — equities on non-US exchanges need an
# exchange suffix to disambiguate. Keyed by the stock's `currency` since that's
# the simplest signal we already store. Extend as more non-US stocks land in
# the portfolio.
_YF_SUFFIX_BY_CURRENCY: dict[str, str] = {
    "TRY": ".IS",  # Borsa Istanbul (e.g. ASELS → ASELS.IS)
}


def _to_decimal_str(value: object) -> str | None:
    if value is None:
        return None
    try:
        # Going via str avoids float-binary noise (e.g. 1.23 → "1.2300000000000001").
        return str(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _import_yfinance():
    try:
        import yfinance as yf

        return yf
    except ImportError as err:
        raise ProviderError("yfinance is not installed on the server.") from err


class YFinanceProvider(DataProvider):
    """Market-data adapter backed by the ``yfinance`` library."""

    name = "yfinance"
    capabilities = frozenset({Capability.MARKET_DATA})

    def _yf_ticker(self, symbol: str, currency: str | None) -> str:
        """Map a portfolio symbol → its Yahoo Finance ticker.

        Appends the per-exchange suffix when the currency tells us the stock
        isn't on a US market. If the symbol already carries a dot (e.g. the user
        typed ``ASELS.IS`` directly) the suffix is not added twice.
        """
        if currency and "." not in symbol:
            suffix = _YF_SUFFIX_BY_CURRENCY.get(currency.upper())
            if suffix:
                return f"{symbol}{suffix}"
        return symbol

    def get_market_snapshot(
        self, symbol: str, *, currency: str | None = None
    ) -> MarketSnapshot:
        yf = _import_yfinance()
        yf_symbol = self._yf_ticker(symbol, currency)

        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info or {}
        except Exception as err:  # yfinance raises a variety of network/parse errors
            logger.warning(
                "yfinance lookup failed for %s (yf=%s): %s", symbol, yf_symbol, err
            )
            raise ProviderError(
                f"Couldn't reach Yahoo Finance for '{symbol}'."
            ) from err

        # Yahoo flips between these keys depending on market hours / asset type.
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        beta = info.get("beta")

        return MarketSnapshot(
            symbol=symbol,
            current_price=_to_decimal_str(price),
            beta=_to_decimal_str(beta),
            source=self.name,
        )

    def get_closing_prices(
        self,
        symbol: str,
        periods: list[tuple[str, date]],
        *,
        currency: str | None = None,
    ) -> list[ClosingPriceResult]:
        if not periods:
            return []

        yf = _import_yfinance()
        yf_symbol = self._yf_ticker(symbol, currency)

        # One history() call covers every requested quarter. Pad the window so
        # holiday-extended quarter-ends still find a trading day to fall back to.
        earliest = min(end for _, end in periods)
        latest = max(end for _, end in periods)
        start = earliest - timedelta(days=10)
        end_window = latest + timedelta(days=1)  # `end` is exclusive in yfinance

        try:
            ticker = yf.Ticker(yf_symbol)
            history = ticker.history(
                start=start.isoformat(),
                end=end_window.isoformat(),
                auto_adjust=False,
            )
        except Exception as err:
            logger.warning(
                "yfinance history failed for %s (yf=%s): %s", symbol, yf_symbol, err
            )
            raise ProviderError(
                f"Couldn't reach Yahoo Finance for '{symbol}'."
            ) from err

        if history is None or history.empty or "Close" not in history.columns:
            raise ProviderError(f"No price history found for '{symbol}'.")

        # `history.index` is a DatetimeIndex (tz-aware on equities). Drop tz so
        # date comparison against our `date` objects stays trivial.
        closes = history["Close"]
        try:
            closes.index = closes.index.tz_localize(None)
        except TypeError:
            # Already tz-naive — yfinance is inconsistent across asset types.
            pass

        results: list[ClosingPriceResult] = []
        for period, end in periods:
            # Pick the last trading day on or before the quarter's end date.
            mask = closes.index.date <= end
            eligible = closes[mask]
            if eligible.empty:
                results.append(
                    ClosingPriceResult(
                        period=period,
                        end_date=end,
                        closing_price=None,
                        reason="No trading day on or before this quarter's end date.",
                    )
                )
                continue
            close_value = eligible.iloc[-1]
            results.append(
                ClosingPriceResult(
                    period=period,
                    end_date=end,
                    closing_price=_to_decimal_str(float(close_value)),
                )
            )
        return results
