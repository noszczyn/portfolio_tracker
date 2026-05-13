import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

CACHE_TTL_SECONDS = 120
_PRICE_CACHE: dict[tuple[str, str, str], tuple[float, list[dict]]] = {}

def _ticker_candidates(ticker: str) -> list[str]:
    symbol = ticker.strip().upper()
    candidates = [symbol]
    # XTB / użytkownicy często używają innych suffixów niż Yahoo.
    if symbol.endswith(".PL"):
        candidates.append(symbol[:-3] + ".WA")
    if symbol.endswith(".US"):
        candidates.append(symbol[:-3])
    if symbol.endswith(".UK"):
        candidates.append(symbol[:-3] + ".L")
    return candidates

def fetch_prices(ticker: str, date_from: str, date_to: str) -> list[dict]:
    cache_key = (ticker.strip().upper(), date_from, date_to)
    now = time.time()
    cached = _PRICE_CACHE.get(cache_key)
    if cached and now - cached[0] <= CACHE_TTL_SECONDS:
        return cached[1]

    # yfinance traktuje parametr `end` jako wyłączny, więc dodajemy 1 dzień,
    # żeby zakres obejmował również `date_to`.
    start_dt = datetime.fromisoformat(date_from).date()
    end_dt = datetime.fromisoformat(date_to).date() + timedelta(days=1)

    df = pd.DataFrame()
    for candidate in _ticker_candidates(ticker):
        df = yf.download(
            candidate,
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
            progress=False,
            auto_adjust=True,
        )
        if not df.empty:
            break

    if df.empty:
        return []

    # yfinance 1.x zwraca MultiIndex kolumny — spłaszczamy do prostych nazw
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    result = []
    for date, row in df.iterrows():
        result.append({
            "date":   str(date.date()),
            "open":   round(float(row["Open"]),   2),
            "high":   round(float(row["High"]),   2),
            "low":    round(float(row["Low"]),    2),
            "close":  round(float(row["Close"]),  2),
            "volume": int(row["Volume"]),
        })
    _PRICE_CACHE[cache_key] = (now, result)
    return result