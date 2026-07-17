"""CRUD + price-refresh endpoints for holdings.

Routers only orchestrate HTTP concerns (status codes, headers, query/path
parsing) and delegate everything else to crud.py. Validation/DB/business
errors are raised as exceptions here and translated to the shared error
envelope by the global exception handlers registered in main.py.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Response
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.get("", response_model=list[schemas.HoldingResponse])
def list_holdings(db: Session = Depends(get_db)):
    holdings = crud.list_holdings(db)
    return [crud.to_response_dict(h) for h in holdings]


@router.get("/{holding_id}", response_model=schemas.HoldingResponse)
def get_holding(holding_id: str, db: Session = Depends(get_db)):
    holding = crud.get_holding_or_404(db, holding_id)
    return crud.to_response_dict(holding)


@router.post("", response_model=schemas.HoldingResponse, status_code=201)
def create_holding(response: Response, payload: dict = Body(default_factory=dict), db: Session = Depends(get_db)):
    holding, merged = crud.create_holding(db, payload)
    # A symbol matching an existing holding merges into it instead of
    # creating a new row — 200 (existing resource updated) rather than
    # 201 (new resource created) reflects that accurately.
    if merged:
        response.status_code = 200
    response.headers["Location"] = f"/api/holdings/{holding.id}"
    return crud.to_response_dict(holding)


@router.patch("/{holding_id}", response_model=schemas.HoldingResponse)
def update_holding(holding_id: str, payload: dict = Body(default_factory=dict), db: Session = Depends(get_db)):
    holding = crud.get_holding_or_404(db, holding_id)
    holding = crud.update_holding(db, holding, payload)
    return crud.to_response_dict(holding)


@router.delete("/{holding_id}", status_code=204)
def delete_holding(holding_id: str, db: Session = Depends(get_db)):
    holding = crud.get_holding_or_404(db, holding_id)
    crud.delete_holding(db, holding)
    return Response(status_code=204)


@router.post("/{holding_id}/refresh-price", response_model=schemas.HoldingResponse)
def refresh_price(
    holding_id: str,
    payload: Optional[dict] = Body(default=None),
    db: Session = Depends(get_db),
):
    holding = crud.refresh_single_price(db, holding_id)
    return crud.to_response_dict(holding)


@router.post(
    "/refresh-prices",
    response_model=schemas.RefreshPricesResponse,
    response_model_exclude_none=True,
)
def refresh_prices(db: Session = Depends(get_db)):
    return crud.refresh_all_prices(db)
