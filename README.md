# Portfolio Manager

A single-user stock portfolio tracker: a Python/FastAPI REST API backed by MySQL, paired with a plain HTML/CSS/JS frontend. It tracks stock holdings, computes cost basis / market value / unrealized P&L, charts portfolio performance over time, and can refresh live prices on demand via Yahoo Finance (`yfinance`).

This is a beginner-friendly training/reference project: single user, no authentication, one asset type (stocks), single currency (USD assumed, no FX support). Keeping the scope small on purpose — see [docs/TRAINING_BRIEF.md](docs/TRAINING_BRIEF.md) for ideas on what to add next.

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (ORM), Pydantic v2 (schemas), Uvicorn (ASGI server)
- **Database:** MySQL, installed and run directly on your machine — no Docker required
- **Live prices:** `yfinance` (Yahoo Finance) for on-demand price refresh
- **Frontend:** Plain HTML, CSS, and JavaScript (ES modules) — no framework, no build step
- **Testing:** `pytest` + FastAPI's `TestClient` (`httpx`), against an in-memory SQLite database (no MySQL needed to run tests)

## Features

- Track stock holdings: symbol, company name, shares, cost basis, current price, purchase date
- Automatic calculation of cost basis, market value, unrealized P&L, and unrealized P&L % per holding
- Portfolio summary: total value, total cost basis, total return %
- Portfolio performance history (line chart), backed by point-in-time snapshots taken automatically on every holding change or price refresh
- One-click live price refresh for a single holding or all holdings at once, via Yahoo Finance
- Clear, consistent error responses with field-level validation detail
- Interactive API docs out of the box (Swagger UI / ReDoc)

## Quick start

1. Install MySQL locally (see **[docs/SETUP.md](docs/SETUP.md)** if you don't have it yet) and create the `portfolio_manager` database.
2. `cd backend`
3. Create and activate a virtual environment, then `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and adjust if needed
5. `uvicorn app.main:app --reload --port 8000` — starts the API
6. Open `frontend/index.html` in a browser (or serve it with `python -m http.server 5500 --directory ../frontend`)

API docs: `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc`.

For the full, exact step-by-step instructions (including how to install MySQL, Windows vs. macOS/Linux differences, and troubleshooting), see **[docs/SETUP.md](docs/SETUP.md)**.

## API overview

| Method | Path | Description |
|---|---|---|
| GET | `/api/holdings` | List all holdings |
| GET | `/api/holdings/{id}` | Get a single holding |
| POST | `/api/holdings` | Create a holding |
| PATCH | `/api/holdings/{id}` | Partially update a holding |
| DELETE | `/api/holdings/{id}` | Delete a holding |
| POST | `/api/holdings/{id}/refresh-price` | Refresh one holding's price from Yahoo Finance |
| POST | `/api/holdings/refresh-prices` | Refresh all holdings' prices |
| GET | `/api/portfolio/summary` | Total value, total cost basis, total return % |
| GET | `/api/portfolio/performance` | Historical portfolio value points, for the performance chart |

## Project origin

This project was built from a training brief preserved at [`docs/TRAINING_BRIEF.md`](docs/TRAINING_BRIEF.md). That document is the original source of the product requirements and UI mockups this system implements — including ideas for later enhancements (bonds, crypto, cash, multi-user) once the stock-only basics are solid.
