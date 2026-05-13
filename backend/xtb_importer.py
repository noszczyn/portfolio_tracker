import re
from datetime import datetime
from io import BytesIO

import pandas as pd
import yfinance as yf


SUPPORTED_TYPES = {
    "stock purchase": "BUY",
    "stock sale": "SELL",
    "close trade": "SELL",
}

SYMBOL_CURRENCY_SUFFIX = {
    ".US": "USD",
    ".DE": "EUR",
    ".UK": "GBP",
    ".L": "GBP",
    ".PL": "PLN",
    ".WA": "PLN",
}

YAHOO_SYMBOL_SUFFIX_FALLBACK = {
    ".PL": ".WA",
    ".US": "",
    ".UK": ".L",
}


def _to_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_qty_price(comment: object) -> tuple[float | None, float | None]:
    if comment is None or (isinstance(comment, float) and pd.isna(comment)):
        return (None, None)
    text = str(comment)
    # XTB potrafi zapisać wolumen jako "2/2.5 @ 114.29"
    # gdzie pierwsza liczba to zrealizowana część, a druga to wolumen docelowy.
    match = re.search(r"(\d+(?:[.,]\d+)?)(?:/\d+(?:[.,]\d+)?)?\s*@\s*(\d+(?:[.,]\d+)?)", text)
    if not match:
        return (None, None)
    qty = _to_float(match.group(1))
    price = _to_float(match.group(2))
    return (qty, price)


def _extract_account_currency(raw: pd.DataFrame, header_scan_rows: int = 15) -> str:
    rows = min(header_scan_rows, len(raw))
    for idx in range(rows):
        values = [str(v).strip().upper() for v in raw.iloc[idx].tolist() if pd.notna(v)]
        if "CURRENCY" not in values:
            continue
        # Waluta bywa obok "Currency" albo w następnym wierszu.
        for candidate in values:
            if re.fullmatch(r"[A-Z]{3}", candidate):
                return candidate
        if idx + 1 < len(raw):
            next_values = [str(v).strip().upper() for v in raw.iloc[idx + 1].tolist() if pd.notna(v)]
            for candidate in next_values:
                if re.fullmatch(r"[A-Z]{3}", candidate):
                    return candidate
    return "PLN"


def _to_yahoo_symbol(symbol: str) -> str:
    upper = symbol.upper()
    for suffix, replacement in YAHOO_SYMBOL_SUFFIX_FALLBACK.items():
        if upper.endswith(suffix):
            return upper[: -len(suffix)] + replacement
    return upper


def _normalize_provider_currency(value: str | None) -> str | None:
    if not value:
        return None
    upper = str(value).upper().strip()
    aliases = {
        "GBX": "GBP",
        "GBP": "GBP",
        "USDT": "USD",
    }
    return aliases.get(upper, upper)


def _infer_currency_from_instrument(symbol: str, account_currency: str, cache: dict[str, str]) -> str:
    upper_symbol = symbol.upper()
    if upper_symbol in cache:
        return cache[upper_symbol]

    yahoo_symbol = _to_yahoo_symbol(upper_symbol)
    try:
        ticker = yf.Ticker(yahoo_symbol)
        fast_info = getattr(ticker, "fast_info", None)
        provider_currency = None
        if fast_info:
            provider_currency = fast_info.get("currency")
        normalized = _normalize_provider_currency(provider_currency)
        if normalized and re.fullmatch(r"[A-Z]{3}", normalized):
            cache[upper_symbol] = normalized
            return normalized
    except Exception:
        pass

    # Fallback po suffixie tylko gdy provider nie zwrócił waluty.
    for suffix, currency in SYMBOL_CURRENCY_SUFFIX.items():
        if upper_symbol.endswith(suffix):
            cache[upper_symbol] = currency
            return currency

    cache[upper_symbol] = account_currency
    return account_currency


def _read_cash_history(file_bytes: bytes) -> pd.DataFrame:
    raw = pd.read_excel(BytesIO(file_bytes), sheet_name="CASH OPERATION HISTORY", header=None, engine="openpyxl")
    header_idx = None
    for idx, row in raw.iterrows():
        values = [str(v).strip() for v in row.tolist() if pd.notna(v)]
        if {"ID", "Type", "Time", "Comment", "Symbol", "Amount"}.issubset(set(values)):
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("Nie znaleziono tabeli operacji gotówkowych w pliku XTB.")

    headers = [str(v).strip() if pd.notna(v) else f"col_{i}" for i, v in enumerate(raw.iloc[header_idx].tolist())]
    data = raw.iloc[header_idx + 1 :].copy()
    data.columns = headers
    data = data.dropna(how="all").reset_index(drop=True)
    return data[[col for col in ["ID", "Type", "Time", "Comment", "Symbol", "Amount"] if col in data.columns]]


def parse_xtb_transactions(file_bytes: bytes) -> tuple[list[dict], list[str]]:
    raw = pd.read_excel(BytesIO(file_bytes), sheet_name="CASH OPERATION HISTORY", header=None, engine="openpyxl")
    account_currency = _extract_account_currency(raw)
    data = _read_cash_history(file_bytes)
    parsed: list[dict] = []
    errors: list[str] = []
    currency_cache: dict[str, str] = {}

    for _, row in data.iterrows():
        type_raw = str(row.get("Type", "")).strip().lower()

        executed_at = pd.to_datetime(row.get("Time"), errors="coerce")
        if pd.isna(executed_at):
            errors.append("Pominięto wiersz: niepoprawna data.")
            continue

        # Obsługa cashflow do poprawnego invested/stopa zwrotu.
        if "deposit" in type_raw:
            amount = _to_float(row.get("Amount"))
            if amount is None or amount <= 0:
                continue
            parsed.append(
                {
                    "type": "DEPOSIT",
                    "ticker": "CASH",
                    "quantity": 1.0,
                    "price": round(abs(amount), 6),
                    "commission": 0.0,
                    "currency": account_currency,
                    "executed_at": datetime.fromtimestamp(executed_at.timestamp()),
                }
            )
            continue

        if "withdraw" in type_raw:
            amount = _to_float(row.get("Amount"))
            if amount is None or amount == 0:
                continue
            parsed.append(
                {
                    "type": "WITHDRAWAL",
                    "ticker": "CASH",
                    "quantity": 1.0,
                    "price": round(abs(amount), 6),
                    "commission": 0.0,
                    "currency": account_currency,
                    "executed_at": datetime.fromtimestamp(executed_at.timestamp()),
                }
            )
            continue

        if type_raw not in SUPPORTED_TYPES:
            continue

        symbol = str(row.get("Symbol", "")).strip().upper()
        if not symbol or symbol.lower() == "nan":
            errors.append("Pominięto wiersz bez symbolu.")
            continue
        quantity, price = _extract_qty_price(row.get("Comment"))
        if quantity is None or price is None:
            errors.append(f"Pominięto {symbol}: nie udało się odczytać ilości/ceny z komentarza.")
            continue

        amount = _to_float(row.get("Amount"))
        trade_value = abs(amount) if amount is not None else quantity * price
        raw_diff = max(trade_value - (quantity * price), 0.0)
        # Jeśli różnica jest duża, to zwykle efekt konwersji walut / formatu XTB,
        # a nie realna prowizja transakcyjna.
        commission = raw_diff if raw_diff <= max(5.0, 0.05 * max(trade_value, 1.0)) else 0.0
        commission = round(commission, 6)

        account_unit_price = trade_value / quantity if quantity > 0 else price

        parsed.append(
            {
                "type": SUPPORTED_TYPES[type_raw],
                "ticker": symbol,
                "quantity": round(abs(quantity), 6),
                # Dla poprawnego salda gotówki używamy jednostkowej ceny w walucie konta.
                "price": round(account_unit_price, 6),
                "commission": commission,
                "currency": account_currency,
                "executed_at": datetime.fromtimestamp(executed_at.timestamp()),
            }
        )

    return parsed, errors
