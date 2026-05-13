from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id:           Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    ticker:       Mapped[str] = mapped_column(String(20), nullable=False)
    type:         Mapped[str] = mapped_column(String(20), nullable=False)
    quantity:     Mapped[float] = mapped_column(Float, nullable=False)
    price:        Mapped[float] = mapped_column(Float, nullable=False)
    currency:     Mapped[str] = mapped_column(String(3), default="PLN")
    commission:   Mapped[float] = mapped_column(Float, default=0.0)
    executed_at:  Mapped[datetime] = mapped_column(DateTime, nullable=False)