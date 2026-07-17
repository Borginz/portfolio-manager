import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.database import Base, get_db

SQLALCHEMY_TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Point the app's startup-time `Base.metadata.create_all(bind=engine)` at the
# in-memory SQLite engine instead of the real MySQL engine, so importing/
# starting the app in tests never tries to reach a real database.
main_module.engine = test_engine


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


main_module.app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    with TestClient(main_module.app) as c:
        yield c
