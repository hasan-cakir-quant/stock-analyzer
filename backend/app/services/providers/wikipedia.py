"""Wikipedia data provider — index-constituents adapter via the Wikimedia API.

Implements ``Capability.CONSTITUENTS``. The current S&P 500 membership lives in
the ``id="constituents"`` table on
``https://en.wikipedia.org/wiki/List_of_S%26P_500_companies``.

Rather than scraping rendered HTML, this adapter calls the **MediaWiki Action
API** (``action=parse&prop=wikitext``) and parses the table's wikitext. The
ticker is the first cell of each data row; it may appear as an external link
(``[https://… AAPL]``), a stock-exchange template (``{{NYSE|MMM}}``), or plain
text, so a small normaliser pulls the symbol out of each form.

The Wikimedia API rejects requests without a descriptive ``User-Agent``; it's
read from the ``WIKIPEDIA_USER_AGENT`` setting so each deployment supplies its
own contact.
"""

from __future__ import annotations

import html as html_lib
import logging
import re

import httpx

from app.core.config import get_settings
from app.services.providers.base import Capability, DataProvider, ProviderError

logger = logging.getLogger(__name__)

_API_URL = "https://en.wikipedia.org/w/api.php"
_SP500_PAGE = "List_of_S&P_500_companies"
# Tickers are uppercase letters with the occasional dot or hyphen (BRK.B, BF.B).
_TICKER_RE = re.compile(r"^[A-Z][A-Z.\-]{0,9}$")
# Exchange templates that wrap a ticker, e.g. {{NYSE|MMM}} / {{Nasdaq|AAPL}}.
_EXCHANGE_TEMPLATE_RE = re.compile(
    r"\{\{\s*(?:NYSE|Nasdaq|NASDAQ|NYSEAMERICAN|CBOE)\s*\|\s*([^}|]+?)\s*\}\}"
)
# External link: [https://example.com/… DISPLAY TEXT].
_EXTERNAL_LINK_RE = re.compile(r"\[https?://\S+\s+([^\]]+)\]")


def _fetch_sp500_wikitext() -> str:
    """Fetch the raw wikitext of the S&P 500 companies page via the Action API."""
    settings = get_settings()
    try:
        resp = httpx.get(
            _API_URL,
            params={
                "action": "parse",
                "page": _SP500_PAGE,
                "prop": "wikitext",
                "format": "json",
                "formatversion": "2",
                "redirects": "1",
            },
            headers={"User-Agent": settings.wikipedia_user_agent},
            timeout=30.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as err:
        raise ProviderError(
            f"Couldn't fetch the S&P 500 list from the Wikimedia API: {err}"
        ) from err
    except ValueError as err:  # JSON decode
        raise ProviderError("Wikimedia API returned an unparseable response.") from err

    if "error" in payload:
        info = payload["error"].get("info", "unknown error")
        raise ProviderError(f"Wikimedia API error: {info}")

    wikitext = payload.get("parse", {}).get("wikitext")
    if not isinstance(wikitext, str) or not wikitext:
        raise ProviderError("Wikimedia API response carried no wikitext.")
    return wikitext


def _isolate_constituents_table(wikitext: str) -> str:
    """Return just the ``id="constituents"`` wikitable block."""
    anchor = wikitext.find('id="constituents"')
    if anchor == -1:
        raise ProviderError("Couldn't locate the constituents table in the wikitext.")
    # The table opens with `{|` at/just before the anchor and closes at `|}`.
    table_start = wikitext.rfind("{|", 0, anchor)
    if table_start == -1:
        table_start = anchor
    table_end = wikitext.find("\n|}", anchor)
    if table_end == -1:
        table_end = len(wikitext)
    return wikitext[table_start:table_end]


def _first_cell(row: str) -> str | None:
    """Return the first data cell of a wikitext table row, or None for a
    header-only / empty row."""
    # A row is a sequence of lines; data cells start with `|` (but not `|-`,
    # and not `|+` caption). Cells on one line are separated by `||`.
    for line in row.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith(("|-", "|+")):
            continue
        body = stripped[1:]
        # First cell only — split on the `||` inline-cell separator.
        first = body.split("||", 1)[0]
        return first.strip()
    return None


def _extract_symbol(cell: str) -> str | None:
    """Pull a ticker symbol out of a constituents-table first cell, whatever
    markup form it takes."""
    text = cell

    template = _EXCHANGE_TEMPLATE_RE.search(text)
    if template:
        text = template.group(1)
    else:
        link = _EXTERNAL_LINK_RE.search(text)
        if link:
            text = link.group(1)

    # Collapse internal links [[Target|Display]] / [[Target]] to their text.
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", text)
    # Drop any remaining templates and HTML tags.
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text).strip()
    # Cell styling like `style="..." | TEXT` can leave a trailing pipe segment.
    if "|" in text:
        text = text.rsplit("|", 1)[-1].strip()

    return text if _TICKER_RE.match(text) else None


class WikipediaProvider(DataProvider):
    """Index-constituents adapter backed by the Wikimedia (MediaWiki) API."""

    name = "wikipedia"
    capabilities = frozenset({Capability.CONSTITUENTS})

    def get_constituents(self, index: str = "sp500") -> list[str]:
        if index != "sp500":
            raise ProviderError(f"Unsupported index '{index}'. Only 'sp500' is known.")

        wikitext = _fetch_sp500_wikitext()
        table = _isolate_constituents_table(wikitext)

        symbols: list[str] = []
        seen: set[str] = set()
        for row in table.split("|-"):
            cell = _first_cell(row)
            if cell is None:
                continue
            symbol = _extract_symbol(cell)
            if symbol and symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)

        if not symbols:
            raise ProviderError(
                "Parsed the constituents table but found no ticker symbols."
            )
        return symbols
