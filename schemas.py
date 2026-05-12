from pydantic import BaseModel, EmailStr
from datetime import datetime

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
    type: str
    quantity: float
    price: float
    currency: str = "PLN"
    commission: float = 0.0
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