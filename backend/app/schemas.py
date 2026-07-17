"""Pydantic v2 schemas — response/output shapes for the API.

Request bodies for POST/PATCH /api/holdings are accepted as plain `dict`
(see routers/holdings.py) and validated by hand in crud.py, because the
spec requires collecting *all* field violations together (not pydantic's
fail-on-first-type-error semantics) and requires type-conditional rules
(e.g. `symbol` required only for STOCK/CRYPTO) that are awkward to express
declaratively. The schemas below are used for response serialization
(`response_model=...`), which is where FastAPI/Pydantic v2 add real value
(automatic OpenAPI docs, response shape guarantees).
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, PlainSerializer


class AssetType(str, Enum):
    STOCK = "STOCK"
    BOND = "BOND"
    CRYPTO = "CRYPTO"
    CASH = "CASH"


def _serialize_utc_z(dt: datetime) -> str:
    """Render datetimes as ISO 8601 UTC with a trailing 'Z', e.g.
    '2026-07-17T14:32:00Z', matching the spec's timestamp convention
    (stored datetimes are naive-UTC; treated as UTC if tz-naive)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


# datetime fields render as "...Z" instead of pydantic's default "+00:00" offset.
UtcDateTime = Annotated[datetime, PlainSerializer(_serialize_utc_z, return_type=str)]


# ---------------------------------------------------------------------------
# Holding
# ---------------------------------------------------------------------------


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_type: AssetType
    symbol: Optional[str] = None
    name: str
    quantity: float
    cost_basis_per_unit: float
    cost_basis_total: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_percent: float
    purchase_date: Optional[date] = None
    is_refreshable: bool
    last_price_updated_at: Optional[UtcDateTime] = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


# ---------------------------------------------------------------------------
# Error envelope (shared shape, §5)
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Optional[List[ErrorDetail]] = None


class ErrorResponse(BaseModel):
    error: ErrorBody


# ---------------------------------------------------------------------------
# Bulk price refresh (§3.7)
# ---------------------------------------------------------------------------


class RefreshResultItem(BaseModel):
    id: int
    symbol: Optional[str] = None
    status: str
    previous_price: Optional[float] = None
    current_price: Optional[float] = None
    error: Optional[ErrorBody] = None


class RefreshPricesResponse(BaseModel):
    refreshed_at: UtcDateTime
    total_eligible: int
    succeeded: int
    failed: int
    results: List[RefreshResultItem]


# ---------------------------------------------------------------------------
# Portfolio summary (§4.1)
# ---------------------------------------------------------------------------


class AssetTypeSummary(BaseModel):
    asset_type: AssetType
    market_value: float
    cost_basis: float
    unrealized_pl: float
    percent_of_portfolio: float


class PortfolioSummary(BaseModel):
    as_of: UtcDateTime
    total_market_value: float
    total_cost_basis: float
    total_unrealized_pl: float
    total_return_percent: float
    by_asset_type: List[AssetTypeSummary]
    holdings_count: int


# ---------------------------------------------------------------------------
# Portfolio performance (§4.2)
# ---------------------------------------------------------------------------


class PerformancePoint(BaseModel):
    timestamp: UtcDateTime
    total_value: float


class PerformanceResponse(BaseModel):
    points: List[PerformancePoint]
