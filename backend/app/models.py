"""SQLAlchemy ORM models.

`asset_type` is stored as a plain string (validated at the crud.py layer
against the four allowed values) rather than a DB-level ENUM, so the same
model works identically against MySQL in production and SQLite in tests.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String

from .database import Base


def _utcnow() -> datetime:
    """Naive UTC now(), used as a DB-side fallback default. crud.py always
    supplies created_at/updated_at/timestamp explicitly; this default only
    matters if a row is ever inserted without going through crud.py."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_type = Column(String(10), nullable=False, index=True)
    symbol = Column(String(20), nullable=True)
    name = Column(String(200), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False)
    cost_basis_per_unit = Column(Numeric(24, 8), nullable=False)
    current_price = Column(Numeric(24, 8), nullable=False)
    purchase_date = Column(Date, nullable=True)
    last_price_updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=_utcnow, index=True)
    total_value = Column(Numeric(24, 8), nullable=False)
