from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal

# Schemat dla danych przychodzących podczas rejestracji
class UserCreate(BaseModel):
    email: EmailStr
    password: str

# Schemat dla tokenu, który zwracamy po udanym logowaniu
class Token(BaseModel):
    access_token: str
    token_type: str

# Schemat opisujący użytkownika zwracanego przez API (BEZ HASŁA!)
class UserResponse(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True

# --- SCHEMATY DLA PORTFELA ---

# Dane potrzebne do utworzenia portfela
class PortfolioCreate(BaseModel):
    name: str
    currency: str = "PLN"

# Dane zwracane przez API
class PortfolioResponse(BaseModel):
    id: int
    name: str
    currency: str
    user_id: int

    class Config:
        from_attributes = True

class TransactionCreate(BaseModel):
    portfolio_id: int
    ticker: str
    type: Literal["BUY", "SELL"]
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    currency: str = "PLN"
    commission: float = Field(default=0.0, ge=0)
    executed_at: datetime

class TransactionResponse(BaseModel):
    id: int
    portfolio_id: int
    ticker: str
    type: str
    quantity: float
    price: float
    currency: str
    commission: float
    executed_at: datetime

    class Config:
        from_attributes = True

class PriceResponse(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PortfolioChartPoint(BaseModel):
    date: str
    value: float
    invested: float | None = None


class ImportSummary(BaseModel):
    imported: int
    skipped: int
    errors: list[str]