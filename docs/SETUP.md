# Local Setup & Run Guide

This guide walks through running the Portfolio Manager stack (MySQL database, FastAPI backend, static frontend) locally from a clean checkout. Commands below are exact and verified — use them as written rather than substituting equivalents.

Primary instructions are for **Windows (PowerShell)**. Where macOS/Linux differs, a note follows the relevant step.

## Prerequisites

- Docker Desktop (for MySQL via Docker Compose)
- Python 3.12+
- A modern web browser

## Steps

### 1. Start MySQL

From the repo root:

```
docker compose up -d
```

This starts a single `mysql` service (MySQL 8.0) with a database, user, and password matching `backend/.env.example`, persisted to a named Docker volume. It listens on `localhost:3306`.

### 2. Move into the backend directory

```
cd backend
```

### 3. Create and activate a virtual environment

**Windows (PowerShell):**
```
python -m venv venv && venv\Scripts\activate
```

**macOS/Linux:**
```
python -m venv venv
source venv/bin/activate
```

Your shell prompt should now be prefixed with `(venv)`.

### 4. Install dependencies

```
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, SQLAlchemy, PyMySQL, Pydantic, python-dotenv, pytest, httpx, and yfinance.

### 5. Configure environment variables

Copy `.env.example` to `.env` and adjust values if your local MySQL setup differs from the defaults:

```
copy .env.example .env
```

(macOS/Linux: `cp .env.example .env`)

The variables are `DB_HOST`, `DB_PORT` (default `3306`), `DB_USER`, `DB_PASSWORD`, `DB_NAME` (default `portfolio_manager`). Defaults line up with the `docker-compose.yml` MySQL service, so no changes are required for the standard local setup.

### 6. Run the API

```
uvicorn app.main:app --reload --port 8000
```

On startup, the app creates any missing database tables automatically (`Base.metadata.create_all`) — no manual migration step is needed for this project. (Alembic-based migrations are a possible future enhancement, not implemented here.)

The API is now live at `http://localhost:8000`.

### 7. Open the frontend

Either open the file directly in a browser:

```
frontend/index.html
```

...or serve it over HTTP (useful if your browser restricts `fetch` from `file://` origins):

```
python -m http.server 5500 --directory ../frontend
```

Then browse to `http://localhost:5500`. The frontend calls the backend at `http://localhost:8000/api`.

### 8. Explore the API docs

With the backend running, interactive documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 9. Run the test suite

From the `backend` directory (with the virtual environment activated):

```
cd backend && pytest
```

Tests run against an in-memory SQLite database and never touch your real MySQL instance or make real network calls to Yahoo Finance (price lookups are mocked).

## Troubleshooting

**MySQL connection refused**
Confirm the container is running with `docker compose up -d` (check `docker ps` for a `mysql` container listening on `3306`). If you just started it, MySQL can take a few seconds to finish initializing — wait and retry. Also verify `backend/.env` matches the credentials in `docker-compose.yml`/`.env.example`.

**Port 8000 already in use**
Another process is bound to port 8000. Either stop it, or run Uvicorn on a different port, e.g. `uvicorn app.main:app --reload --port 8001` — and update the base URL in `frontend/js/api.js` to match if you do.

**CORS errors in the browser console**
The backend enables permissive CORS (all origins) for development, so this is usually a sign the backend isn't actually running or you're hitting the wrong URL/port. Confirm the API is reachable at `http://localhost:8000/docs` and that `frontend/js/api.js` points at the correct base URL.

**yfinance returns no data / price refresh fails for a ticker**
This means Yahoo Finance had no data for the symbol you entered — typically an invalid, delisted, or misspelled ticker (or a malformed crypto pair, e.g. it should be `BTC-USD`, not `BTC`). The API returns a `422 TICKER_NOT_FOUND` error in this case; double-check the symbol. If instead you see a `502 UPSTREAM_UNAVAILABLE`, that indicates a network problem reaching Yahoo Finance rather than a bad symbol — check your internet connection and retry.
