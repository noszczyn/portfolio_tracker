from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text # Dodane dla db-check

# Importy Twoich plików
from database import SessionLocal, engine
from models.user import User
import schemas
import auth

app = FastAPI(title="Portfolio Tracker", version="0.1.0")

# --- ZALEŻNOŚĆ DO BAZY DANYCH ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- ENDPOINTY HEALTH CHECK ---
@app.get("/")
def health_check():
    return {"status": "ok"}

@app.get("/db-check")
def db_check():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        return {"postgres" : result.scalar()}


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