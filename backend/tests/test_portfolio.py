def test_summary_empty_portfolio(client):
    resp = client.get("/api/portfolio/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_market_value"] == 0
    assert body["total_cost_basis"] == 0
    assert body["total_unrealized_pl"] == 0
    assert body["total_return_percent"] == 0
    assert body["holdings_count"] == 0


def test_summary_with_holdings(client):
    client.post(
        "/api/holdings",
        json={
            "symbol": "AAPL",
            "name": "Apple",
            "quantity": 10,
            "cost_basis_per_unit": 100,
            "current_price": 150,
        },
    )
    client.post(
        "/api/holdings",
        json={
            "symbol": "MSFT",
            "name": "Microsoft",
            "quantity": 5,
            "cost_basis_per_unit": 100,
            "current_price": 100,
        },
    )

    resp = client.get("/api/portfolio/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["holdings_count"] == 2
    assert body["total_market_value"] == 2000.00
    assert body["total_cost_basis"] == 1500.00
    assert body["total_unrealized_pl"] == 500.00
    assert body["total_return_percent"] == round(500 / 1500 * 100, 2)


def test_performance_empty(client):
    resp = client.get("/api/portfolio/performance")
    assert resp.status_code == 200
    assert resp.json() == {"points": []}


def test_performance_after_holding_created(client):
    client.post(
        "/api/holdings",
        json={"symbol": "AAPL", "name": "Apple", "quantity": 10, "cost_basis_per_unit": 100},
    )
    resp = client.get("/api/portfolio/performance")
    assert resp.status_code == 200
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["total_value"] == 1000.00


def test_performance_multiple_snapshots_sorted_ascending(client):
    client.post(
        "/api/holdings",
        json={"symbol": "AAPL", "name": "Apple", "quantity": 1, "cost_basis_per_unit": 100},
    )
    created = client.post(
        "/api/holdings",
        json={"symbol": "MSFT", "name": "Microsoft", "quantity": 2, "cost_basis_per_unit": 100},
    ).json()
    client.patch(f"/api/holdings/{created['id']}", json={"quantity": 3})

    resp = client.get("/api/portfolio/performance")
    points = resp.json()["points"]
    assert len(points) == 3
    values = [p["total_value"] for p in points]
    assert values == [100.00, 300.00, 400.00]
    timestamps = [p["timestamp"] for p in points]
    assert timestamps == sorted(timestamps)


def test_performance_invalid_from_date(client):
    resp = client.get("/api/portfolio/performance", params={"from": "not-a-date"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_performance_from_after_to(client):
    resp = client.get(
        "/api/portfolio/performance",
        params={"from": "2026-01-01", "to": "2025-01-01"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_performance_invalid_limit(client):
    resp = client.get("/api/portfolio/performance", params={"limit": "0"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_performance_limit_clamped_not_error(client):
    client.post(
        "/api/holdings",
        json={"symbol": "AAPL", "name": "Apple", "quantity": 1, "cost_basis_per_unit": 100},
    )
    resp = client.get("/api/portfolio/performance", params={"limit": 5000})
    assert resp.status_code == 200
