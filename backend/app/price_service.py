"""Live price lookups via yfinance.

Exposes `get_latest_price(ticker) -> float`. Callers (crud.py) never see raw
yfinance/network exceptions: this module normalizes every failure mode into
one of two typed exceptions so routers can turn them into clean HTTP
responses instead of crashing:

- `TickerNotFoundError` — yfinance reached Yahoo Finance fine but returned
  no usable price data for the symbol (bad/delisted/mistyped ticker).
- `UpstreamUnavailableError` — the network call itself failed (timeout,
  DNS, connection error, or any other unexpected yfinance exception).
"""

import yfinance as yf


class PriceLookupError(Exception):
    """Base class for all price-lookup failures."""


class TickerNotFoundError(PriceLookupError):
    """Yahoo Finance returned no price data for the given ticker."""


class UpstreamUnavailableError(PriceLookupError):
    """Yahoo Finance could not be reached (network/timeout/unexpected error)."""


def get_latest_price(ticker: str) -> float:
    """Return the latest known price for `ticker` as a float.

    Raises `TickerNotFoundError` if the symbol is invalid/delisted (no data
    returned), or `UpstreamUnavailableError` if the network call itself
    fails.
    """
    if not ticker:
        raise TickerNotFoundError("No ticker symbol supplied for price lookup.")

    try:
        t = yf.Ticker(ticker)

        price = None

        # Prefer the cheap "fast_info" path when available.
        try:
            fast_info = t.fast_info
            if fast_info is not None:
                candidate = None
                try:
                    candidate = fast_info.get("last_price")
                except AttributeError:
                    candidate = getattr(fast_info, "last_price", None)
                if candidate is not None:
                    price = float(candidate)
        except Exception:
            price = None

        if price is None:
            history = t.history(period="5d")
            if history is not None and not history.empty and "Close" in history:
                closes = history["Close"].dropna()
                if not closes.empty:
                    price = float(closes.iloc[-1])

        if price is None:
            raise TickerNotFoundError(
                f"No price data returned by Yahoo Finance for symbol '{ticker}'."
            )

        return price

    except TickerNotFoundError:
        raise
    except Exception as exc:  # network errors, timeouts, unexpected yfinance failures
        raise UpstreamUnavailableError(
            f"Failed to reach Yahoo Finance while refreshing symbol '{ticker}': {exc}"
        ) from exc
