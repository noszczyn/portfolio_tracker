from pydantic import BaseModel, EmailStr

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