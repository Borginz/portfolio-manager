"""Portfolio summary + performance endpoints, plus the bulk price-refresh
route is on the holdings router per the spec (POST /api/holdings/refresh-prices).
This module only has the two GET endpoints under /api/portfolio.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=schemas.PortfolioSummary)
def summary(db: Session = Depends(get_db)):
    return crud.get_portfolio_summary(db)


@router.get("/performance", response_model=schemas.PerformanceResponse)
def performance(
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    limit: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    from_date, to_date, limit_value = crud.parse_performance_params(from_, to, limit)
    points = crud.get_performance(db, from_date, to_date, limit_value)
    return {"points": points}
