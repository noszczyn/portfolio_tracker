from fastapi import FastAPI
from sqlalchemy import create_engine, text

app = FastAPI(title="Portfolio Tracker", version="0.1.0")

@app.get("/")
def health_check():
    return {"status": "ok"}

DATABASE_URL = "postgresql://dev:dev@localhost:5432/portfolio"
engine = create_engine(DATABASE_URL)

@app.get("/db-check")
def db_check():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        return {"postgres" : result.scalar()}