from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text # Dodane dla db-check
from jose import JWTError, jwt
from typing import List

# Importy Twoich plików
from models.portfolio import Portfolio
from models.transaction import Transaction
from price_fetcher import fetch_prices
from portfolio_value import get_portfolio_value_history
from datetime import date
from database import SessionLocal, engine, get_db
from models.user import User
import schemas
import auth

app = FastAPI(title="Portfolio Tracker", version="0.1.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# --- ZALEŻNOŚĆ DO POBIERANIA ZALOGOWANEGO UŻYTKOWNIKA ---
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Dekodujemy token używając tego samego sekretnego klucza
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # 2. Szukamy użytkownika w bazie na podstawie maila z tokenu
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
        
    return user


# --- REJESTRACJA ---
@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    
    new_user = User(email=user.email, password=hashed_password)
    db.add(new_user)
    db.commit()
    
    return {"message": "User created successfully"}


# --- LOGOWANIE ---
@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not auth.verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# --- ENDPOINT TYLKO DLA ZALOGOWANYCH ---
@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


# --- PORTFOLIOS ---

# POST /portfolios — Utwórz nowy portfel
@app.post("/portfolios", response_model=schemas.PortfolioResponse, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    portfolio: schemas.PortfolioCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    new_portfolio = Portfolio(
        name=portfolio.name,
        currency=portfolio.currency,
        user_id=current_user.id # Automatycznie przypisujemy do zalogowanego usera
    )
    db.add(new_portfolio)
    db.commit()
    db.refresh(new_portfolio)
    return new_portfolio

# GET /portfolios — Lista portfeli zalogowanego usera
@app.get("/portfolios", response_model=List[schemas.PortfolioResponse])
def get_user_portfolios(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    return db.query(Portfolio).filter(Portfolio.user_id == current_user.id).all()

# DELETE /portfolios/{id} — Usuń portfel (tylko jeśli należy do Ciebie)
@app.delete("/portfolios/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    portfolio_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == current_user.id
    ).first()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found or not owned by you")

    db.delete(portfolio)
    db.commit()
    return None

# POST /transactions — dodaj transakcję
@app.post("/transactions", response_model=schemas.TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == transaction.portfolio_id,
        Portfolio.user_id == current_user.id
    ).first()
    if not portfolio:
        raise HTTPException(status_code=403, detail="Not your portfolio")

    new_transaction = Transaction(**transaction.model_dump())
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    return new_transaction

# GET /transactions?portfolio_id=X — lista transakcji
@app.get("/transactions", response_model=List[schemas.TransactionResponse])
def get_transactions(
    portfolio_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == current_user.id
    ).first()
    if not portfolio:
        raise HTTPException(status_code=403, detail="Not your portfolio")

    return db.query(Transaction).filter(Transaction.portfolio_id == portfolio_id).all()

# DELETE /transactions/{id} — usuń transakcję
@app.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction = db.query(Transaction).join(Portfolio).filter(
        Transaction.id == transaction_id,
        Portfolio.user_id == current_user.id
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found or not owned by you")

    db.delete(transaction)
    db.commit()
    return None

@app.get("/prices/{ticker}", response_model=List[schemas.PriceResponse])
def get_prices(
    ticker: str,
    date_from: str,
    date_to: str,
    current_user: User = Depends(get_current_user)
):
    prices = fetch_prices(ticker, date_from, date_to)
    if not prices:
        raise HTTPException(status_code=404, detail="No data found for this ticker")
    return prices

@app.get("/portfolios/{portfolio_id}/chart")
def get_portfolio_chart(
    portfolio_id: int,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == current_user.id
    ).first()
    if not portfolio:
        raise HTTPException(status_code=403, detail="Not your portfolio")

    return get_portfolio_value_history(portfolio_id, date_from, date_to, db)