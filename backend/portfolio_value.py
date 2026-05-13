from datetime import date, timedelta
from bisect import bisect_right
from functools import lru_cache
from sqlalchemy.orm import Session
from models.transaction import Transaction
from price_fetcher import fetch_prices
import yfinance as yf

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


def _ticker_candidates(ticker: str) -> list[str]:
    symbol = (ticker or "").strip().upper()
    # Preferujemy symbole kompatybilne z Yahoo, żeby uniknąć 404 i błędnych walut.
    if symbol.endswith(".PL"):
        return [symbol[:-3] + ".WA", symbol]
    if symbol.endswith(".US"):
        return [symbol[:-3], symbol]
    if symbol.endswith(".UK"):
        return [symbol[:-3] + ".L", symbol]
    return [symbol]


def _normalize_provider_currency(value: str | None) -> str | None:
    if not value:
        return None
    upper = str(value).upper().strip()
    aliases = {
        "GBX": "GBP",
        "USDT": "USD",
    }
    return aliases.get(upper, upper)


@lru_cache(maxsize=512)
def _provider_currency_for_ticker(ticker: str) -> str | None:
    for candidate in _ticker_candidates(ticker):
        try:
            info = getattr(yf.Ticker(candidate), "fast_info", None)
            currency = _normalize_provider_currency(info.get("currency") if info else None)
            if currency and len(currency) == 3:
                return currency
        except Exception:
            continue
    return None


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
    ).order_by(Transaction.executed_at.asc(), Transaction.id.asc()).all()

    if not transactions:
        return []

    tickers = list(set(t.ticker for t in transactions))
    instrument_currency_by_ticker = {}
    for ticker in tickers:
        instrument_currency_by_ticker[ticker] = _provider_currency_for_ticker(ticker)
    currencies = list(set(_resolve_currency(t.ticker, t.currency) for t in transactions))
    currencies.extend(
        c for c in instrument_currency_by_ticker.values()
        if c and c != "PLN"
    )
    currencies = list(set(currencies))

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
    tx_index = 0
    invested = 0.0
    cash_balance = 0.0
    positions: dict[str, dict[str, float | str]] = {}

    while current <= date_to:
        day_str = str(current)

        # Przetwarzamy każdą transakcję tylko raz, do dnia bieżącego (zamiast od zera każdego dnia).
        while tx_index < len(transactions) and transactions[tx_index].executed_at.date() <= current:
            t = transactions[tx_index]
            tx_index += 1

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
            provider_currency = instrument_currency_by_ticker.get(t.ticker)
            if provider_currency:
                instrument_currency = provider_currency

            position = positions.get(t.ticker, {"qty": 0.0, "currency": instrument_currency})
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


def get_portfolio_summary(portfolio_id: int, db: Session) -> dict:
    today = date.today()
    price_from = today - timedelta(days=30)

    transactions = db.query(Transaction).filter(
        Transaction.portfolio_id == portfolio_id,
        Transaction.executed_at <= today
    ).order_by(Transaction.executed_at.asc(), Transaction.id.asc()).all()

    if not transactions:
        return {"total_value_pln": 0.0, "total_pnl_pln": 0.0, "items": []}

    tickers = sorted(set(t.ticker for t in transactions if t.type in ("BUY", "SELL") and t.ticker != "CASH"))
    instrument_currency_by_ticker = {ticker: _provider_currency_for_ticker(ticker) for ticker in tickers}

    tx_currencies = set((t.currency or "PLN").upper() for t in transactions)
    instrument_currencies = set(
        (instrument_currency_by_ticker.get(ticker) or _resolve_currency(ticker, "PLN")).upper()
        for ticker in tickers
    )
    all_currencies = tx_currencies.union(instrument_currencies)

    fx_rates: dict[str, list[tuple[str, float]]] = {}
    for currency in all_currencies:
        if currency == "PLN":
            continue
        fx_symbol = FX_TICKERS.get(currency)
        if not fx_symbol:
            continue
        fx_data = fetch_prices(fx_symbol, str(price_from), str(today))
        fx_rates[currency] = _series_to_sorted_items(fx_data)

    positions: dict[str, dict[str, float]] = {}
    for t in transactions:
        if t.type not in ("BUY", "SELL") or t.ticker == "CASH":
            continue

        ticker = t.ticker
        tx_currency = (t.currency or "PLN").upper()
        tx_day = str(t.executed_at.date())
        tx_fx = 1.0
        if tx_currency != "PLN":
            tx_fx = _last_known_value(fx_rates.get(tx_currency, []), tx_day) or 0.0
            if tx_fx <= 0:
                tx_fx = 0.0

        qty = float(t.quantity or 0.0)
        gross = float(t.price or 0.0) * qty
        commission = float(t.commission or 0.0)
        tx_value_pln = (gross + commission) * tx_fx if t.type == "BUY" else (gross - commission) * tx_fx

        if ticker not in positions:
            positions[ticker] = {"qty": 0.0, "cost_pln": 0.0}
        pos = positions[ticker]

        if t.type == "BUY":
            pos["qty"] += qty
            pos["cost_pln"] += tx_value_pln
        elif t.type == "SELL" and pos["qty"] > 0:
            sell_qty = min(pos["qty"], qty)
            avg_cost = pos["cost_pln"] / pos["qty"] if pos["qty"] > 0 else 0.0
            pos["qty"] -= sell_qty
            pos["cost_pln"] = max(0.0, pos["cost_pln"] - (avg_cost * sell_qty))

    items = []
    total_value = 0.0
    total_pnl = 0.0

    for ticker, pos in positions.items():
        qty = float(pos["qty"])
        if qty <= 0:
            continue

        price_rows = fetch_prices(ticker, str(price_from), str(today))
        price_series = _series_to_sorted_items(price_rows)
        close = _last_known_value(price_series, str(today))
        if close is None:
            continue

        instrument_currency = (
            instrument_currency_by_ticker.get(ticker)
            or _resolve_currency(ticker, "PLN")
        ).upper()
        fx_rate = 1.0
        if instrument_currency != "PLN":
            fx_rate = _last_known_value(fx_rates.get(instrument_currency, []), str(today)) or 0.0
            if fx_rate <= 0:
                continue

        current_price_pln = close * fx_rate
        market_value = qty * current_price_pln
        cost_pln = float(pos["cost_pln"])
        pnl = market_value - cost_pln
        return_pct = (pnl / cost_pln * 100) if cost_pln > 0 else 0.0
        avg_buy_price_pln = (cost_pln / qty) if qty > 0 else 0.0

        total_value += market_value
        total_pnl += pnl

        items.append({
            "ticker": ticker,
            "quantity": round(qty, 6),
            "avg_buy_price_pln": round(avg_buy_price_pln, 2),
            "current_price_pln": round(current_price_pln, 2),
            "market_value_pln": round(market_value, 2),
            "share_pct": 0.0,
            "return_pct": round(return_pct, 2),
            "pnl_pln": round(pnl, 2),
        })

    if total_value > 0:
        for item in items:
            item["share_pct"] = round((item["market_value_pln"] / total_value) * 100, 2)

    items.sort(key=lambda x: x["market_value_pln"], reverse=True)

    return {
        "total_value_pln": round(total_value, 2),
        "total_pnl_pln": round(total_pnl, 2),
        "items": items,
    }