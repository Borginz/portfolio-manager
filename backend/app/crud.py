"""All DB reads/writes and business/validation logic live here.

Routers (routers/holdings.py, routers/portfolio.py) call only functions in
this module (plus price_service.py directly, per the layout) — they never
touch the DB session or yfinance themselves.

Custom exceptions defined here (`ValidationError`, `HoldingNotFoundError`)
are translated into the shared error envelope by global exception handlers
registered in main.py.
"""

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from . import models, price_service


def _utcnow() -> datetime:
    """Naive UTC `datetime`, matching the naive `DateTime` columns in
    models.py (schemas.py's serializer treats naive datetimes as UTC and
    renders them with a trailing 'Z')."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


MAX_PERFORMANCE_LIMIT = 2000
DEFAULT_PERFORMANCE_LIMIT = 500


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ValidationError(Exception):
    """A request failed field-level validation.

    `details` is a list of {"field": ..., "message": ...} dicts, matching
    the shared error envelope's `error.details` shape.
    """

    def __init__(self, message: str, details: list):
        self.message = message
        self.details = details
        super().__init__(message)


class HoldingNotFoundError(Exception):
    def __init__(self, holding_id):
        self.holding_id = holding_id
        super().__init__(f"Holding {holding_id} not found.")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _round_money(value) -> float:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _round_percent(value) -> float:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _to_decimal(value) -> Optional[Decimal]:
    """Best-effort conversion; returns None if `value` isn't numeric."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def to_response_dict(holding: models.Holding) -> dict:
    quantity = Decimal(holding.quantity)
    cost_basis_per_unit = Decimal(holding.cost_basis_per_unit)
    current_price = Decimal(holding.current_price)

    cost_basis_total = quantity * cost_basis_per_unit
    market_value = quantity * current_price
    unrealized_pl = market_value - cost_basis_total
    if cost_basis_total == 0:
        unrealized_pl_percent = Decimal("0")
    else:
        unrealized_pl_percent = (unrealized_pl / cost_basis_total) * 100

    return {
        "id": holding.id,
        "symbol": holding.symbol,
        "name": holding.name,
        "quantity": float(quantity),
        "cost_basis_per_unit": _round_money(cost_basis_per_unit),
        "cost_basis_total": _round_money(cost_basis_total),
        "current_price": _round_money(current_price),
        "market_value": _round_money(market_value),
        "unrealized_pl": _round_money(unrealized_pl),
        "unrealized_pl_percent": _round_percent(unrealized_pl_percent),
        "purchase_date": holding.purchase_date,
        "last_price_updated_at": holding.last_price_updated_at,
        "created_at": holding.created_at,
        "updated_at": holding.updated_at,
    }


def _create_snapshot(db: Session) -> None:
    holdings = db.query(models.Holding).all()
    total = Decimal("0")
    for h in holdings:
        total += Decimal(h.quantity) * Decimal(h.current_price)
    snapshot = models.PortfolioSnapshot(timestamp=_utcnow(), total_value=total)
    db.add(snapshot)
    db.commit()


# ---------------------------------------------------------------------------
# Holding validation (shared shape for POST full-create / PATCH merge)
# ---------------------------------------------------------------------------


def _validate_name(data: dict, errors: list, required: bool, current: Optional[str]) -> Optional[str]:
    if "name" not in data:
        if required:
            errors.append({"field": "name", "message": "name is required"})
        return current
    raw = data.get("name")
    if raw is None or not isinstance(raw, str) or not raw.strip():
        errors.append({"field": "name", "message": "name is required and must be 1-200 characters"})
        return current
    trimmed = raw.strip()
    if len(trimmed) > 200:
        errors.append({"field": "name", "message": "name must be at most 200 characters"})
        return current
    return trimmed


def _validate_symbol(data: dict, errors: list, is_create: bool, current: Optional[str]) -> Optional[str]:
    """Every holding is a stock, so `symbol` is always required on create and
    freely editable (but still required) on update. Only touches the value
    if the `symbol` key is present (on update) — for create, `data` always
    effectively "contains" the key since absence and explicit null both
    mean "not supplied"."""
    key_present = "symbol" in data or is_create
    if not key_present:
        return current

    raw = data.get("symbol")
    supplied = raw is not None and str(raw).strip() != ""

    if not supplied:
        errors.append({"field": "symbol", "message": "symbol is required"})
        return current
    trimmed = str(raw).strip().upper()
    if not (1 <= len(trimmed) <= 20):
        errors.append({"field": "symbol", "message": "symbol must be 1-20 characters"})
        return current
    return trimmed


def _validate_quantity(data: dict, errors: list, required: bool, current: Optional[Decimal]) -> Optional[Decimal]:
    if "quantity" not in data:
        if required:
            errors.append({"field": "quantity", "message": "quantity is required"})
        return current
    raw = data.get("quantity")
    if raw is None:
        errors.append({"field": "quantity", "message": "quantity is required"})
        return current
    value = _to_decimal(raw)
    if value is None:
        errors.append({"field": "quantity", "message": "quantity must be a number"})
        return current
    if value <= 0:
        errors.append({"field": "quantity", "message": "quantity must be greater than 0"})
        return current
    return value


def _validate_price_field(
    data: dict, errors: list, field_name: str, required: bool, current: Optional[Decimal]
) -> Optional[Decimal]:
    if field_name not in data:
        if required:
            errors.append({"field": field_name, "message": f"{field_name} is required"})
        return current
    raw = data.get(field_name)
    if raw is None:
        if required:
            errors.append({"field": field_name, "message": f"{field_name} is required"})
            return current
        return None  # explicit null on an optional field -> "not supplied"
    value = _to_decimal(raw)
    if value is None:
        errors.append({"field": field_name, "message": f"{field_name} must be a number"})
        return current
    if value < 0:
        errors.append({"field": field_name, "message": f"{field_name} must be >= 0"})
        return current
    return value


def _validate_purchase_date(data: dict, errors: list, current: Optional[date]) -> Optional[date]:
    if "purchase_date" not in data:
        return current
    raw = data.get("purchase_date")
    if raw is None:
        return None
    try:
        parsed = date.fromisoformat(str(raw))
    except ValueError:
        errors.append({"field": "purchase_date", "message": "purchase_date must be a valid ISO date (YYYY-MM-DD)"})
        return current
    if parsed > date.today():
        errors.append({"field": "purchase_date", "message": "purchase_date must not be later than today"})
        return current
    return parsed


# ---------------------------------------------------------------------------
# Holding CRUD
# ---------------------------------------------------------------------------


def list_holdings(db: Session) -> list:
    return db.query(models.Holding).order_by(models.Holding.id.asc()).all()


def get_holding(db: Session, holding_id: int) -> Optional[models.Holding]:
    return db.query(models.Holding).filter(models.Holding.id == holding_id).first()


def get_holding_or_404(db: Session, raw_id) -> models.Holding:
    try:
        holding_id = int(raw_id)
    except (TypeError, ValueError):
        raise HoldingNotFoundError(raw_id)
    holding = get_holding(db, holding_id)
    if holding is None:
        raise HoldingNotFoundError(raw_id)
    return holding


def create_holding(db: Session, data: dict) -> models.Holding:
    if not isinstance(data, dict):
        data = {}
    errors: list = []

    name = _validate_name(data, errors, required=True, current=None)
    symbol = _validate_symbol(data, errors, is_create=True, current=None)
    quantity = _validate_quantity(data, errors, required=True, current=None)
    cost_basis_per_unit = _validate_price_field(
        data, errors, "cost_basis_per_unit", required=True, current=None
    )
    current_price = _validate_price_field(
        data, errors, "current_price", required=False, current=None
    )
    purchase_date = _validate_purchase_date(data, errors, current=None)

    if errors:
        raise ValidationError("Validation failed for holding.", errors)

    if current_price is None:
        current_price = cost_basis_per_unit

    now = _utcnow()
    holding = models.Holding(
        symbol=symbol,
        name=name,
        quantity=quantity,
        cost_basis_per_unit=cost_basis_per_unit,
        current_price=current_price,
        purchase_date=purchase_date,
        last_price_updated_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    _create_snapshot(db)
    return holding


def update_holding(db: Session, holding: models.Holding, data: dict) -> models.Holding:
    if not isinstance(data, dict):
        data = {}
    errors: list = []

    name = _validate_name(data, errors, required=False, current=holding.name)
    symbol = _validate_symbol(data, errors, is_create=False, current=holding.symbol)
    quantity = _validate_quantity(data, errors, required=False, current=Decimal(holding.quantity))

    cost_basis_per_unit = _validate_price_field(
        data, errors, "cost_basis_per_unit", required=False, current=Decimal(holding.cost_basis_per_unit)
    )
    if cost_basis_per_unit is None:
        cost_basis_per_unit = Decimal(holding.cost_basis_per_unit)
    current_price = _validate_price_field(
        data, errors, "current_price", required=False, current=Decimal(holding.current_price)
    )
    if current_price is None:
        current_price = Decimal(holding.current_price)

    purchase_date = _validate_purchase_date(data, errors, current=holding.purchase_date)

    if errors:
        raise ValidationError("Validation failed for holding update.", errors)

    holding.name = name
    holding.symbol = symbol
    holding.quantity = quantity
    holding.cost_basis_per_unit = cost_basis_per_unit
    holding.current_price = current_price
    holding.purchase_date = purchase_date
    holding.updated_at = _utcnow()

    db.commit()
    db.refresh(holding)
    _create_snapshot(db)
    return holding


def delete_holding(db: Session, holding: models.Holding) -> None:
    db.delete(holding)
    db.commit()
    _create_snapshot(db)


# ---------------------------------------------------------------------------
# Price refresh
# ---------------------------------------------------------------------------


def apply_price_refresh(db: Session, holding: models.Holding, price: float) -> models.Holding:
    now = _utcnow()
    holding.current_price = Decimal(str(price))
    holding.last_price_updated_at = now
    holding.updated_at = now
    db.commit()
    db.refresh(holding)
    _create_snapshot(db)
    return holding


def refresh_single_price(db: Session, raw_id) -> models.Holding:
    holding = get_holding_or_404(db, raw_id)
    price = price_service.get_latest_price(holding.symbol)
    return apply_price_refresh(db, holding, price)


def refresh_all_prices(db: Session) -> dict:
    holdings = db.query(models.Holding).order_by(models.Holding.id.asc()).all()
    total_eligible = len(holdings)
    refreshed_at = _utcnow()
    results = []
    succeeded = 0
    failed = 0

    for holding in holdings:
        try:
            price = price_service.get_latest_price(holding.symbol)
        except price_service.TickerNotFoundError as exc:
            failed += 1
            results.append(
                {
                    "id": holding.id,
                    "symbol": holding.symbol,
                    "status": "ERROR",
                    "error": {"code": "TICKER_NOT_FOUND", "message": str(exc)},
                }
            )
            continue
        except price_service.UpstreamUnavailableError as exc:
            failed += 1
            results.append(
                {
                    "id": holding.id,
                    "symbol": holding.symbol,
                    "status": "ERROR",
                    "error": {"code": "UPSTREAM_UNAVAILABLE", "message": str(exc)},
                }
            )
            continue

        previous_price = _round_money(Decimal(holding.current_price))
        holding.current_price = Decimal(str(price))
        holding.last_price_updated_at = refreshed_at
        holding.updated_at = refreshed_at
        succeeded += 1
        results.append(
            {
                "id": holding.id,
                "symbol": holding.symbol,
                "status": "SUCCESS",
                "previous_price": previous_price,
                "current_price": _round_money(Decimal(holding.current_price)),
            }
        )

    if succeeded > 0:
        db.commit()
        _create_snapshot(db)
    else:
        db.rollback()

    return {
        "refreshed_at": refreshed_at,
        "total_eligible": total_eligible,
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Portfolio summary / performance
# ---------------------------------------------------------------------------


def get_portfolio_summary(db: Session) -> dict:
    holdings = db.query(models.Holding).all()

    total_market_value = Decimal("0")
    total_cost_basis = Decimal("0")

    for h in holdings:
        quantity = Decimal(h.quantity)
        total_market_value += quantity * Decimal(h.current_price)
        total_cost_basis += quantity * Decimal(h.cost_basis_per_unit)

    total_unrealized_pl = total_market_value - total_cost_basis
    total_return_percent = (
        Decimal("0") if total_cost_basis == 0 else (total_unrealized_pl / total_cost_basis) * 100
    )

    return {
        "as_of": _utcnow(),
        "total_market_value": _round_money(total_market_value),
        "total_cost_basis": _round_money(total_cost_basis),
        "total_unrealized_pl": _round_money(total_unrealized_pl),
        "total_return_percent": _round_percent(total_return_percent),
        "holdings_count": len(holdings),
    }


def parse_performance_params(from_raw, to_raw, limit_raw):
    """Validates/normalizes the `from`/`to`/`limit` query params for
    GET /api/portfolio/performance. Returns (from_date, to_date, limit)."""
    errors: list = []
    from_date = None
    to_date = None
    limit = DEFAULT_PERFORMANCE_LIMIT

    if from_raw:
        try:
            from_date = date.fromisoformat(from_raw)
        except ValueError:
            errors.append({"field": "from", "message": "from must be a valid ISO date (YYYY-MM-DD)"})

    if to_raw:
        try:
            to_date = date.fromisoformat(to_raw)
        except ValueError:
            errors.append({"field": "to", "message": "to must be a valid ISO date (YYYY-MM-DD)"})

    if from_date is not None and to_date is not None and from_date > to_date:
        errors.append({"field": "from", "message": "from must not be later than to"})

    if limit_raw is not None and limit_raw != "":
        try:
            limit = int(limit_raw)
            if limit <= 0:
                errors.append({"field": "limit", "message": "limit must be a positive integer"})
        except ValueError:
            errors.append({"field": "limit", "message": "limit must be a positive integer"})

    if errors:
        raise ValidationError("Invalid performance query parameters.", errors)

    if limit > MAX_PERFORMANCE_LIMIT:
        limit = MAX_PERFORMANCE_LIMIT

    return from_date, to_date, limit


def get_performance(db: Session, from_date: Optional[date], to_date: Optional[date], limit: int) -> list:
    query = db.query(models.PortfolioSnapshot)
    if from_date is not None:
        query = query.filter(models.PortfolioSnapshot.timestamp >= datetime.combine(from_date, datetime.min.time()))
    if to_date is not None:
        query = query.filter(models.PortfolioSnapshot.timestamp <= datetime.combine(to_date, datetime.max.time()))

    rows = query.order_by(models.PortfolioSnapshot.timestamp.desc()).limit(limit).all()
    rows.sort(key=lambda r: r.timestamp)

    return [{"timestamp": r.timestamp, "total_value": _round_money(Decimal(r.total_value))} for r in rows]
