# Portfolio Manager

A single-user portfolio tracking application: a Python/FastAPI REST API backed by MySQL, paired with a plain HTML/CSS/JS frontend. It tracks stock, bond, crypto, and cash holdings, computes cost basis / market value / unrealized P&L, charts asset allocation and performance over time, and can refresh live prices for stock and crypto holdings on demand via Yahoo Finance (`yfinance`).

This is a training/reference project: single user, no authentication, single portfolio, single currency (USD assumed, no FX support). Multi-user support and authentication are explicit future enhancements, out of scope for now.

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (ORM), Pydantic v2 (schemas), Uvicorn (ASGI server)
- **Database:** MySQL 8.0 (via `pymysql` driver), run locally through Docker Compose
- **Live prices:** `yfinance` (Yahoo Finance) for on-demand price refresh of STOCK/CRYPTO holdings
- **Frontend:** Plain HTML, CSS, and JavaScript (ES modules) — no framework, no build step
- **Testing:** `pytest` + FastAPI's `TestClient` (`httpx`), against an in-memory SQLite database

## Features

- Track holdings across four asset types: `STOCK`, `BOND`, `CRYPTO`, `CASH`
- Automatic calculation of cost basis, market value, unrealized P&L, and unrealized P&L % per holding
- Portfolio summary: total value, total return %, and a breakdown by asset type (for the allocation donut chart and summary tiles)
- Portfolio performance history (line chart), backed by point-in-time snapshots taken automatically on every holding mutation and price refresh
- One-click live price refresh for a single holding or for all eligible (STOCK/CRYPTO) holdings at once, via Yahoo Finance
- Clear, consistent error responses with field-level validation detail
- Interactive API docs out of the box (Swagger UI / ReDoc)

## Quick start

1. `docker compose up -d` — starts MySQL
2. `cd backend`
3. Create and activate a virtual environment, then `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and adjust if needed
5. `uvicorn app.main:app --reload --port 8000` — starts the API
6. Open `frontend/index.html` in a browser (or serve it with `python -m http.server 5500 --directory ../frontend`)

API docs: `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc`.

For the full, exact step-by-step instructions (including Windows vs. macOS/Linux differences and troubleshooting), see **[docs/SETUP.md](docs/SETUP.md)**.

## API overview

Full request/response shapes, validation rules, and error codes are documented in the domain spec; this table is a quick reference only.

| Method | Path | Description |
|---|---|---|
| GET | `/api/holdings` | List all holdings |
| GET | `/api/holdings/{id}` | Get a single holding |
| POST | `/api/holdings` | Create a holding |
| PATCH | `/api/holdings/{id}` | Partially update a holding |
| DELETE | `/api/holdings/{id}` | Delete a holding |
| POST | `/api/holdings/{id}/refresh-price` | Refresh one holding's price from Yahoo Finance |
| POST | `/api/holdings/refresh-prices` | Refresh all eligible (STOCK/CRYPTO) holdings' prices |
| GET | `/api/portfolio/summary` | Total value, total return %, and per-asset-type breakdown |
| GET | `/api/portfolio/performance` | Historical portfolio value points, for the performance chart |

## Project origin

This project was built from a training brief preserved at [`docs/TRAINING_BRIEF.md`](docs/TRAINING_BRIEF.md). That document is the original source of the product requirements and UI mockups this system implements.
