"""SEC EDGAR data provider — official-API fundamentals adapter.

Implements ``Capability.FUNDAMENTALS`` against SEC's **official** endpoints:

  * ticker→CIK registry — ``https://www.sec.gov/files/company_tickers.json``
    (~13k entries, a few hundred KB), pulled once per process and cached in
    memory for an hour.
  * company facts — ``https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json``,
    every XBRL fact the issuer has reported (usually 5–25 MB of JSON), fetched
    on demand.

SEC requires every automated request to send a descriptive ``User-Agent`` that
identifies the caller (a generic UA gets blocked). It's read from the
``SEC_EDGAR_USER_AGENT`` setting so each deployment can supply its own contact.
"""

from __future__ import annotations

import gzip
import json
import logging
import threading
import time
import zlib
from urllib import error as urlerror
from urllib import request as urlrequest

from app.core.config import get_settings
from app.services.providers.base import Capability, DataProvider, ProviderError

logger = logging.getLogger(__name__)

_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_CACHE_TTL_SECONDS = 3600
# Companyfacts JSON for very active filers (Microsoft, Apple) lands around
# 15–25 MB. Anything larger than this is almost certainly a problem, not a
# legitimate filer payload — fail fast rather than buffer indefinitely.
_MAX_COMPANY_FACTS_BYTES = 50 * 1024 * 1024


class SecLookupError(ProviderError):
    """Raised when EDGAR is unreachable or returns an unparseable payload."""


def _user_agent() -> str:
    return get_settings().sec_edgar_user_agent


# Module-level ticker cache shared across provider instances.
_lock = threading.Lock()
_cache: dict[str, str] = {}
_cache_loaded_at: float = 0.0


def _fetch_company_tickers() -> dict[str, str]:
    """Download the ticker→CIK registry. Returns an uppercased ticker map
    whose values are the canonical zero-padded 10-digit CIK strings."""
    request = urlrequest.Request(
        _COMPANY_TICKERS_URL,
        headers={
            "User-Agent": _user_agent(),
            "Accept": "application/json",
        },
    )
    try:
        with urlrequest.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urlerror.URLError, TimeoutError, json.JSONDecodeError) as err:
        raise SecLookupError(f"Couldn't reach SEC EDGAR: {err}") from err

    # Payload is a dict keyed by string indices; each value has
    # `cik_str` (int) and `ticker` (str).
    mapping: dict[str, str] = {}
    for entry in payload.values():
        ticker = str(entry.get("ticker", "")).strip().upper()
        cik = entry.get("cik_str")
        if not ticker or cik is None:
            continue
        mapping[ticker] = f"{int(cik):010d}"
    if not mapping:
        raise SecLookupError("SEC EDGAR returned an empty ticker registry.")
    return mapping


def _load_cache(force: bool = False) -> dict[str, str]:
    global _cache, _cache_loaded_at
    now = time.monotonic()
    with _lock:
        if force or not _cache or (now - _cache_loaded_at) > _CACHE_TTL_SECONDS:
            logger.info("Loading SEC EDGAR ticker registry")
            _cache = _fetch_company_tickers()
            _cache_loaded_at = now
        return _cache


class SecEdgarProvider(DataProvider):
    """Fundamentals adapter backed by SEC EDGAR's official JSON APIs."""

    name = "sec-edgar"
    capabilities = frozenset({Capability.FUNDAMENTALS})

    def lookup_cik(self, symbol: str) -> str | None:
        """Return the zero-padded CIK for ``symbol``, or None if EDGAR doesn't
        list it."""
        if not symbol:
            return None
        cache = _load_cache()
        return cache.get(symbol.strip().upper())

    def fetch_company_facts(self, cik: str) -> str:
        """Download the raw companyfacts JSON for ``cik`` and return it as text.

        Returned as-is so callers can hand it straight to the EDGAR import
        parser, which works against a JSON string.
        """
        cik_clean = (cik or "").strip()
        if not cik_clean:
            raise SecLookupError("CIK is empty.")
        # Pad to canonical 10 digits; EDGAR refuses unpadded values.
        try:
            cik_clean = f"{int(cik_clean):010d}"
        except ValueError as err:
            raise SecLookupError(f"CIK is not numeric: {cik!r}") from err

        url = _COMPANY_FACTS_URL.format(cik=cik_clean)

        request = urlrequest.Request(
            url,
            headers={
                "User-Agent": _user_agent(),
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            },
        )
        try:
            with urlrequest.urlopen(request, timeout=30) as response:
                raw = response.read(_MAX_COMPANY_FACTS_BYTES + 1)
                # urllib (unlike `requests`) doesn't auto-decompress, so the
                # Content-Encoding header determines what we actually got.
                encoding = (response.headers.get("Content-Encoding") or "").lower()
        except urlerror.HTTPError as err:
            if err.code == 404:
                raise SecLookupError(
                    f"EDGAR has no companyfacts for CIK {cik_clean}."
                ) from err
            raise SecLookupError(
                f"EDGAR returned HTTP {err.code} for CIK {cik_clean}."
            ) from err
        except (urlerror.URLError, TimeoutError) as err:
            raise SecLookupError(f"Couldn't reach EDGAR companyfacts: {err}") from err

        if len(raw) > _MAX_COMPANY_FACTS_BYTES:
            raise SecLookupError(
                f"EDGAR companyfacts payload exceeded "
                f"{_MAX_COMPANY_FACTS_BYTES // (1024 * 1024)} MB."
            )

        try:
            if encoding == "gzip":
                raw = gzip.decompress(raw)
            elif encoding == "deflate":
                # `deflate` is technically zlib-wrapped; some servers omit the
                # wrapper, so fall back to raw inflate if the first try fails.
                try:
                    raw = zlib.decompress(raw)
                except zlib.error:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        except (OSError, zlib.error) as err:
            raise SecLookupError(
                f"Couldn't decompress EDGAR response ({encoding}) for CIK "
                f"{cik_clean}: {err}"
            ) from err

        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as err:
            raise SecLookupError(
                f"EDGAR returned non-UTF-8 bytes for CIK {cik_clean}."
            ) from err
