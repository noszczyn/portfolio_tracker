from pydantic import BaseModel, EmailStr

# Schemat dla danych przychodzących podczas rejestracji
class UserCreate(BaseModel):
    email: EmailStr
    password: str

# Schemat dla tokenu, który zwracamy po udanym logowaniu
class Token(BaseModel):
    access_token: str
    token_type: str