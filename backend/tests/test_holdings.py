def test_create_and_get_holding(client):
    payload = {
        "symbol": "aapl",
        "name": "Apple Inc.",
        "quantity": 10,
        "cost_basis_per_unit": 150.00,
        "current_price": 195.50,
        "purchase_date": "2024-03-15",
    }
    resp = client.post("/api/holdings", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["cost_basis_total"] == 1500.00
    assert body["market_value"] == 1955.00
    assert body["unrealized_pl"] == 455.00
    assert body["last_price_updated_at"] is None
    holding_id = body["id"]
    assert resp.headers["location"] == f"/api/holdings/{holding_id}"

    get_resp = client.get(f"/api/holdings/{holding_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == holding_id


def test_create_holding_defaults_current_price_to_cost_basis(client):
    payload = {
        "symbol": "MSFT",
        "name": "Microsoft",
        "quantity": 2,
        "cost_basis_per_unit": 300,
    }
    resp = client.post("/api/holdings", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["current_price"] == 300.00
    assert body["unrealized_pl"] == 0.00


def test_create_holding_validation_error_collects_all_fields(client):
    payload = {"quantity": 0}
    resp = client.post("/api/holdings", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    fields = {d["field"] for d in body["error"]["details"]}
    assert "name" in fields
    assert "symbol" in fields
    assert "quantity" in fields
    assert "cost_basis_per_unit" in fields


def test_create_holding_symbol_required(client):
    payload = {
        "name": "Apple Inc.",
        "quantity": 1,
        "cost_basis_per_unit": 100,
    }
    resp = client.post("/api/holdings", json=payload)
    assert resp.status_code == 400
    fields = {d["field"] for d in resp.json()["error"]["details"]}
    assert "symbol" in fields


def test_create_holding_malformed_json_body(client):
    resp = client.post(
        "/api/holdings",
        content="{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "details" not in body["error"]


def test_list_holdings_empty(client):
    resp = client.get("/api/holdings")
    assert resp.status_code == 200
    assert resp.json() == []


def test_update_holding(client):
    payload = {
        "symbol": "MSFT",
        "name": "Microsoft",
        "quantity": 5,
        "cost_basis_per_unit": 300,
        "current_price": 310,
    }
    created = client.post("/api/holdings", json=payload).json()
    update_resp = client.patch(f"/api/holdings/{created['id']}", json={"quantity": 8, "current_price": 320})
    assert update_resp.status_code == 200
    body = update_resp.json()
    assert body["quantity"] == 8
    assert body["current_price"] == 320.00
    assert body["market_value"] == 2560.00
    assert body["last_price_updated_at"] is None


def test_update_holding_symbol(client):
    payload = {"symbol": "GOOG", "name": "Alphabet", "quantity": 1, "cost_basis_per_unit": 100}
    created = client.post("/api/holdings", json=payload).json()
    resp = client.patch(f"/api/holdings/{created['id']}", json={"symbol": "goog2", "name": "Alphabet Inc."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Alphabet Inc."
    assert body["symbol"] == "GOOG2"


def test_update_holding_symbol_cannot_be_blanked(client):
    payload = {"symbol": "GOOG", "name": "Alphabet", "quantity": 1, "cost_basis_per_unit": 100}
    created = client.post("/api/holdings", json=payload).json()
    resp = client.patch(f"/api/holdings/{created['id']}", json={"symbol": ""})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_holding_not_found(client):
    resp = client.patch("/api/holdings/9999", json={"quantity": 1})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_get_holding_non_integer_id_is_404(client):
    resp = client.get("/api/holdings/abc")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_delete_holding(client):
    payload = {"symbol": "AAPL", "name": "Apple", "quantity": 100, "cost_basis_per_unit": 10}
    created = client.post("/api/holdings", json=payload).json()
    resp = client.delete(f"/api/holdings/{created['id']}")
    assert resp.status_code == 204
    get_resp = client.get(f"/api/holdings/{created['id']}")
    assert get_resp.status_code == 404


def test_delete_holding_not_found(client):
    resp = client.delete("/api/holdings/12345")
    assert resp.status_code == 404


def test_refresh_price_success(client, monkeypatch):
    from app import price_service

    payload = {"symbol": "AAPL", "name": "Apple Inc.", "quantity": 10, "cost_basis_per_unit": 150}
    created = client.post("/api/holdings", json=payload).json()

    monkeypatch.setattr(price_service, "get_latest_price", lambda symbol: 210.55)

    resp = client.post(f"/api/holdings/{created['id']}/refresh-price")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_price"] == 210.55
    assert body["last_price_updated_at"] is not None


def test_refresh_price_not_found(client):
    resp = client.post("/api/holdings/9999/refresh-price")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_refresh_price_ticker_not_found(client, monkeypatch):
    from app import price_service

    payload = {"symbol": "ZZZZ", "name": "Bad Ticker", "quantity": 1, "cost_basis_per_unit": 10}
    created = client.post("/api/holdings", json=payload).json()

    def fake_price(symbol):
        raise price_service.TickerNotFoundError(
            f"No price data returned by Yahoo Finance for symbol '{symbol}'."
        )

    monkeypatch.setattr(price_service, "get_latest_price", fake_price)
    resp = client.post(f"/api/holdings/{created['id']}/refresh-price")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TICKER_NOT_FOUND"


def test_refresh_price_upstream_unavailable(client, monkeypatch):
    from app import price_service

    payload = {"symbol": "AAPL", "name": "Apple Inc.", "quantity": 1, "cost_basis_per_unit": 10}
    created = client.post("/api/holdings", json=payload).json()

    def fake_price(symbol):
        raise price_service.UpstreamUnavailableError("Failed to reach Yahoo Finance: timeout")

    monkeypatch.setattr(price_service, "get_latest_price", fake_price)
    resp = client.post(f"/api/holdings/{created['id']}/refresh-price")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_refresh_prices_bulk(client, monkeypatch):
    from app import price_service

    client.post(
        "/api/holdings",
        json={"symbol": "AAPL", "name": "Apple", "quantity": 1, "cost_basis_per_unit": 100},
    )
    client.post(
        "/api/holdings",
        json={"symbol": "ZZZZ", "name": "Bad", "quantity": 1, "cost_basis_per_unit": 10},
    )

    def fake_price(symbol):
        if symbol == "ZZZZ":
            raise price_service.TickerNotFoundError("No price data returned by Yahoo Finance for symbol 'ZZZZ'.")
        return 123.45

    monkeypatch.setattr(price_service, "get_latest_price", fake_price)
    resp = client.post("/api/holdings/refresh-prices")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_eligible"] == 2
    assert body["succeeded"] == 1
    assert body["failed"] == 1
    assert len(body["results"]) == 2
    statuses = [r["status"] for r in body["results"]]
    assert "ERROR" in statuses
    assert "SUCCESS" in statuses
    error_item = next(r for r in body["results"] if r["status"] == "ERROR")
    assert "current_price" not in error_item
    assert error_item["error"]["code"] == "TICKER_NOT_FOUND"
    success_item = next(r for r in body["results"] if r["status"] == "SUCCESS")
    assert "error" not in success_item
    assert success_item["current_price"] == 123.45


def test_refresh_prices_bulk_no_holdings(client):
    resp = client.post("/api/holdings/refresh-prices")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_eligible"] == 0
    assert body["succeeded"] == 0
    assert body["failed"] == 0
    assert body["results"] == []
