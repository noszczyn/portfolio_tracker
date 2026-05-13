from datetime import date, timedelta
from sqlalchemy.orm import Session
from models.transaction import Transaction
from price_fetcher import fetch_prices

def get_portfolio_value_history(portfolio_id: int, date_from: date, date_to: date, db: Session) -> list[dict]:
    transactions = db.query(Transaction).filter(
        Transaction.portfolio_id == portfolio_id,
        Transaction.executed_at <= date_to
    ).all()

    if not transactions:
        return []

    tickers = list(set(t.ticker for t in transactions))

    # Pobierz ceny wszystkich tickerów za cały zakres
    prices: dict[str, dict[str, float]] = {}
    for ticker in tickers:
        data = fetch_prices(ticker, str(date_from), str(date_to))
        prices[ticker] = {row["date"]: row["close"] for row in data}

    result = []
    current = date_from
    while current <= date_to:
        day_str = str(current)

        # Pozycje na dany dzień
        positions: dict[str, float] = {}
        for t in transactions:
            if t.executed_at.date() <= current:
                qty = positions.get(t.ticker, 0)
                if t.type == "BUY":
                    positions[t.ticker] = qty + t.quantity
                elif t.type == "SELL":
                    positions[t.ticker] = qty - t.quantity

        # Wartość = ilość × cena zamknięcia
        total = 0.0
        for ticker, qty in positions.items():
            close = prices.get(ticker, {}).get(day_str)
            if close and qty > 0:
                total += qty * close

        if total > 0:
            result.append({"date": day_str, "value": round(total, 2)})

        current += timedelta(days=1)

    return result