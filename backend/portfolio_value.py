from datetime import date, timedelta
from bisect import bisect_right
from sqlalchemy.orm import Session
from models.transaction import Transaction
from price_fetcher import fetch_prices

FX_TICKERS = {
    "USD": "USDPLN=X",
    "EUR": "EURPLN=X",
    "GBP": "GBPPLN=X",
    "CHF": "CHFPLN=X",
}

TICKER_SUFFIX_CURRENCY = {
    ".US": "USD",
    ".DE": "EUR",
    ".UK": "GBP",
    ".L": "GBP",
    ".GB": "GBP",
    ".SW": "CHF",
}


def _series_to_sorted_items(rows: list[dict]) -> list[tuple[str, float]]:
    return sorted((row["date"], row["close"]) for row in rows)


def _last_known_value(series: list[tuple[str, float]], day_str: str) -> float | None:
    if not series:
        return None
    keys = [d for d, _ in series]
    idx = bisect_right(keys, day_str) - 1
    if idx < 0:
        return None
    return series[idx][1]


def _resolve_currency(ticker: str, stored_currency: str) -> str:
    currency = (stored_currency or "PLN").upper()
    if currency != "PLN":
        return currency
    symbol = (ticker or "").upper()
    for suffix, inferred in TICKER_SUFFIX_CURRENCY.items():
        if symbol.endswith(suffix):
            return inferred
    return currency


def get_portfolio_value_history(portfolio_id: int, date_from: date, date_to: date, db: Session) -> list[dict]:
    transactions = db.query(Transaction).filter(
        Transaction.portfolio_id == portfolio_id,
        Transaction.executed_at <= date_to
    ).all()

    if not transactions:
        return []

    tickers = list(set(t.ticker for t in transactions))
    currencies = list(set(_resolve_currency(t.ticker, t.currency) for t in transactions))

    # Pobierz ceny wszystkich tickerów za cały zakres
    prices: dict[str, list[tuple[str, float]]] = {}
    for ticker in tickers:
        data = fetch_prices(ticker, str(date_from), str(date_to))
        prices[ticker] = _series_to_sorted_items(data)

    fx_rates: dict[str, list[tuple[str, float]]] = {}
    for currency in currencies:
        if currency == "PLN":
            continue
        fx_symbol = FX_TICKERS.get(currency)
        if not fx_symbol:
            continue
        fx_data = fetch_prices(fx_symbol, str(date_from), str(date_to))
        fx_rates[currency] = _series_to_sorted_items(fx_data)

    result = []
    current = date_from
    while current <= date_to:
        day_str = str(current)

        # Pozycje, wpłaty i saldo gotówki (w PLN) na dany dzień.
        positions: dict[str, dict[str, float | str]] = {}
        invested = 0.0
        cash_balance = 0.0
        for t in transactions:
            if t.executed_at.date() <= current:
                tx_currency = (t.currency or "PLN").upper()
                tx_day_str = str(t.executed_at.date())
                fx_for_tx = 1.0
                if tx_currency != "PLN":
                    fx_for_tx = _last_known_value(fx_rates.get(tx_currency, []), tx_day_str) or 0.0
                    if fx_for_tx <= 0:
                        fx_for_tx = 0.0

                if t.type == "DEPOSIT":
                    amount_pln = t.price * fx_for_tx
                    invested += amount_pln
                    cash_balance += amount_pln
                    continue
                if t.type == "WITHDRAWAL":
                    amount_pln = t.price * fx_for_tx
                    invested -= amount_pln
                    cash_balance -= amount_pln
                    continue

                if t.type == "BUY":
                    tx_value_pln = (t.price * t.quantity + t.commission) * fx_for_tx
                    cash_balance -= tx_value_pln
                elif t.type == "SELL":
                    tx_value_pln = (t.price * t.quantity - t.commission) * fx_for_tx
                    cash_balance += tx_value_pln

                instrument_currency = _resolve_currency(t.ticker, t.currency)
                position = positions.get(t.ticker, {"qty": 0.0, "currency": _resolve_currency(t.ticker, t.currency)})
                qty = float(position["qty"])
                if t.type == "BUY":
                    position["qty"] = qty + t.quantity
                    position["currency"] = instrument_currency
                elif t.type == "SELL":
                    position["qty"] = qty - t.quantity
                positions[t.ticker] = position

        # Wartość = ilość × cena zamknięcia × kurs waluty do PLN
        total = 0.0
        for ticker, position in positions.items():
            qty = float(position["qty"])
            currency = str(position["currency"])
            if qty <= 0:
                continue

            close = _last_known_value(prices.get(ticker, []), day_str)
            if close is None:
                continue

            fx_rate = 1.0
            if currency != "PLN":
                fx_rate = _last_known_value(fx_rates.get(currency, []), day_str) or 0.0
                if fx_rate <= 0:
                    continue

            total += qty * close * fx_rate

        equity = total + cash_balance
        if equity > 0 or invested > 0:
            result.append({"date": day_str, "value": round(equity, 2), "invested": round(max(invested, 0.0), 2)})

        current += timedelta(days=1)

    return result