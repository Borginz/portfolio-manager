# Local Setup & Run Guide

This guide walks through running the Portfolio Manager stack (MySQL database, FastAPI backend, static frontend) locally from a clean checkout, with no Docker required.

Primary instructions are for **Windows (PowerShell)**. Where macOS/Linux differs, a note follows the relevant step.

## Prerequisites

- MySQL Community Server 8.x
- Python 3.12+
- A modern web browser

## Steps

### 1. Install MySQL

If you don't already have MySQL installed:

**Windows:** Download and run the **MySQL Installer** from https://dev.mysql.com/downloads/installer/ (choose "mysql-installer-community"). Pick the default "Developer Default" or "Server only" setup type, and when prompted:
- Set a root password you'll remember (or leave it blank for a local training machine — not recommended outside of local dev).
- Leave the port at the default `3306`.
- Let the installer configure MySQL as a Windows service and start it automatically — this is the default and means MySQL will just be running in the background from now on (check with `Get-Service MySQL*`; start/stop with `Start-Service`/`Stop-Service`).

**macOS:** `brew install mysql && brew services start mysql`

**Linux (Debian/Ubuntu):** `sudo apt install mysql-server && sudo systemctl enable --now mysql`

### 2. Create the database and app user

Open a MySQL client (`mysql -u root -p`, or MySQL Workbench if you installed it) and run:

```sql
CREATE DATABASE IF NOT EXISTS portfolio_manager;
CREATE USER IF NOT EXISTS 'portfolio_user'@'localhost' IDENTIFIED BY 'changeme';
GRANT ALL PRIVILEGES ON portfolio_manager.* TO 'portfolio_user'@'localhost';
FLUSH PRIVILEGES;
```

These are the exact credentials `backend/.env.example` expects, so no further config is needed if you use them as-is. Feel free to pick a different password — just update `backend/.env` to match (step 5).

### 3. Move into the backend directory

```
cd backend
```

### 4. Create and activate a virtual environment

**Windows (PowerShell):**
```
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```
python -m venv venv
source venv/bin/activate
```

Your shell prompt should now be prefixed with `(venv)`.

### 5. Install dependencies

```
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, SQLAlchemy, PyMySQL, Pydantic, python-dotenv, pytest, httpx, and yfinance.

### 6. Configure environment variables

Copy `.env.example` to `.env` and adjust values if your local MySQL setup differs from the defaults:

**Windows:** `copy .env.example .env`
**macOS/Linux:** `cp .env.example .env`

The variables are `DB_HOST` (default `localhost`), `DB_PORT` (default `3306`), `DB_USER`, `DB_PASSWORD`, `DB_NAME` (default `portfolio_manager`). Defaults line up with the database/user created in step 2, so no changes are required if you used those exact commands.

### 7. Run the API

```
uvicorn app.main:app --reload --port 8000
```

On startup, the app creates any missing database tables automatically (`Base.metadata.create_all`) — no manual migration step is needed for this project. (Alembic-based migrations are a possible future enhancement, not implemented here.)

The API is now live at `http://localhost:8000`.

### 8. Open the frontend

Either open the file directly in a browser:

```
frontend/index.html
```

...or serve it over HTTP (useful if your browser restricts `fetch` from `file://` origins):

```
python -m http.server 5500 --directory ../frontend
```

Then browse to `http://localhost:5500`. The frontend calls the backend at `http://localhost:8000/api`.

### 9. Explore the API docs

With the backend running, interactive documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 10. Run the test suite

From the `backend` directory (with the virtual environment activated):

```
pytest
```

Tests run against an in-memory SQLite database and never touch your real MySQL instance or make real network calls to Yahoo Finance (price lookups are mocked) — you don't need MySQL running to run the tests.

## Troubleshooting

**MySQL connection refused**
Confirm MySQL is actually running: `Get-Service MySQL*` on Windows (should show `Running`), or `brew services list` / `systemctl status mysql` on macOS/Linux. If it's stopped, start it (`Start-Service MySQL84`, `brew services start mysql`, or `sudo systemctl start mysql`). Also verify `backend/.env` matches the user/password/database you created in step 2.

**No MySQL Windows service / installer wasn't run as admin**
If you installed just the MySQL Server ZIP/MSI without the full installer wizard (or lack admin rights to register a service), you can run the server directly instead: initialize a data directory once with `mysqld --initialize-insecure --datadir="<path>"`, then start it with `mysqld --datadir="<path>" --port=3306` each time you need it running (leave that terminal open, or launch it as a background process). This is a fallback for restricted environments — a normal install with the official installer avoids all of this.

**Port 8000 already in use**
Another process is bound to port 8000. Either stop it, or run Uvicorn on a different port, e.g. `uvicorn app.main:app --reload --port 8001` — and update `API_BASE` in `frontend/js/api.js` to match if you do.

**CORS errors in the browser console**
The backend enables permissive CORS (all origins) for development, so this is usually a sign the backend isn't actually running or you're hitting the wrong URL/port. Confirm the API is reachable at `http://localhost:8000/docs` and that `frontend/js/api.js` points at the correct base URL.

**yfinance returns no data / price refresh fails for a ticker**
This means Yahoo Finance had no data for the symbol you entered — typically an invalid, delisted, or misspelled ticker. The API returns a `422 TICKER_NOT_FOUND` error in this case; double-check the symbol. If instead you see a `502 UPSTREAM_UNAVAILABLE`, that indicates a network problem reaching Yahoo Finance rather than a bad symbol — check your internet connection and retry.
