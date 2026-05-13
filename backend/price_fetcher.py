import yfinance as yf
import pandas as pd

def _ticker_candidates(ticker: str) -> list[str]:
    symbol = ticker.strip().upper()
    candidates = [symbol]
    # Użytkownicy często wpisują GPW jako .PL, a Yahoo używa .WA.
    if symbol.endswith(".PL"):
        candidates.append(symbol[:-3] + ".WA")
    return candidates

def fetch_prices(ticker: str, date_from: str, date_to: str) -> list[dict]:
    df = pd.DataFrame()
    for candidate in _ticker_candidates(ticker):
        df = yf.download(candidate, start=date_from, end=date_to, progress=False, auto_adjust=True)
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
    return result