"""SQLAlchemy engine/session setup.

Reads MySQL connection info from environment variables (via python-dotenv)
and exposes the standard SQLAlchemy building blocks used across the app:
`engine`, `SessionLocal`, `Base`, and the `get_db` FastAPI dependency.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "portfolio_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")
DB_NAME = os.getenv("DB_NAME", "portfolio_manager")

SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
