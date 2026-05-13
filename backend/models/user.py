from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id:         Mapped[int] = mapped_column(primary_key=True) 
    email:      Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password:   Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)