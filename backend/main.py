from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import List

# Importy Twoich plików
from models.portfolio import Portfolio
from models.transaction import Transaction
from price_fetcher import fetch_prices
from portfolio_value import get_portfolio_value_history, get_portfolio_summary
from datetime import date
from database import get_db
from models.user import User
from fastapi.middleware.cors import CORSMiddleware
import schemas
import auth
from xtb_importer import parse_xtb_transactions

app = FastAPI(title="Portfolio Tracker", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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


@app.get("/portfolios/{portfolio_id}/history", response_model=List[schemas.TransactionResponse])
def get_portfolio_history(
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

    return db.query(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).order_by(Transaction.executed_at.desc()).all()

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


@app.post("/transactions/import/xtb", response_model=schemas.ImportSummary)
async def import_xtb_transactions(
    portfolio_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == current_user.id
    ).first()
    if not portfolio:
        raise HTTPException(status_code=403, detail="Not your portfolio")

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Wymagany plik .xlsx z XTB.")

    file_bytes = await file.read()
    try:
        parsed_transactions, errors = parse_xtb_transactions(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    imported = 0
    skipped = 0

    for tx in parsed_transactions:
        tx_total = round(abs(float(tx["quantity"]) * float(tx["price"])), 2)
        exact_match = db.query(Transaction).filter(
            Transaction.portfolio_id == portfolio_id,
            Transaction.type == tx["type"],
            Transaction.ticker == tx["ticker"],
            Transaction.quantity == tx["quantity"],
            Transaction.price == tx["price"],
            Transaction.executed_at == tx["executed_at"],
        ).first()

        if exact_match:
            # Dla wcześniej zaimportowanych danych aktualizujemy walutę/prowizję,
            # żeby kolejne importy poprawiały starsze rekordy.
            updated = False
            if exact_match.currency != tx["currency"]:
                exact_match.currency = tx["currency"]
                updated = True
            if round(float(exact_match.commission or 0.0), 6) != round(float(tx["commission"] or 0.0), 6):
                exact_match.commission = tx["commission"]
                updated = True

            if updated:
                imported += 1
            else:
                skipped += 1
            continue

        # Migracja starych, błędnych importów: dopasuj po tym samym czasie/tickerze/typie
        # i bardzo podobnej wartości transakcji (qty * price), a potem nadpisz qty/price.
        value_candidates = db.query(Transaction).filter(
            Transaction.portfolio_id == portfolio_id,
            Transaction.type == tx["type"],
            Transaction.ticker == tx["ticker"],
            Transaction.executed_at == tx["executed_at"],
        ).all()

        matched_by_value = None
        best_diff = 10**9
        for candidate in value_candidates:
            candidate_total = round(abs(float(candidate.quantity or 0.0) * float(candidate.price or 0.0)), 2)
            diff = abs(candidate_total - tx_total)
            if diff < best_diff:
                best_diff = diff
                matched_by_value = candidate

        if matched_by_value and best_diff <= 0.05:
            matched_by_value.quantity = tx["quantity"]
            matched_by_value.price = tx["price"]
            matched_by_value.currency = tx["currency"]
            matched_by_value.commission = tx["commission"]
            imported += 1
            continue

        # Backward-compat: dla starych rekordów z błędnym parserem próbujemy
        # bezpiecznej aktualizacji TYLKO gdy kandydat jest jednoznaczny.
        loose_candidates = db.query(Transaction).filter(
            Transaction.portfolio_id == portfolio_id,
            Transaction.type == tx["type"],
            Transaction.ticker == tx["ticker"],
            Transaction.executed_at == tx["executed_at"],
        ).all()
        if len(loose_candidates) == 1:
            existing = loose_candidates[0]
            existing.quantity = tx["quantity"]
            existing.price = tx["price"]
            existing.currency = tx["currency"]
            existing.commission = tx["commission"]
            imported += 1
            continue

        new_transaction = Transaction(
            portfolio_id=portfolio_id,
            type=tx["type"],
            ticker=tx["ticker"],
            quantity=tx["quantity"],
            price=tx["price"],
            commission=tx["commission"],
            currency=tx["currency"],
            executed_at=tx["executed_at"],
        )
        db.add(new_transaction)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors}

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

@app.get("/portfolios/{portfolio_id}/chart", response_model=List[schemas.PortfolioChartPoint])
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


@app.get("/portfolios/{portfolio_id}/summary", response_model=schemas.PortfolioSummaryResponse)
def get_portfolio_summary_endpoint(
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

    return get_portfolio_summary(portfolio_id, db)