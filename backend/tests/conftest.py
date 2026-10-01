import os
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as database
from app.database import Base

# 全程内存 sqlite，单一连接，避免 lifespan/请求各拿一条连接看到不同库
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
database.engine = test_engine
database.SessionLocal = TestSession

import app.main as main  # noqa: E402
main.engine = test_engine
main.SessionLocal = TestSession

from fastapi.testclient import TestClient  # noqa: E402
from app.services.seed import seed_if_empty  # noqa: E402


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    s = TestSession()
    seed_if_empty(s)
    s.close()
    yield TestSession


@pytest.fixture
def client(db):
    with TestClient(main.app) as c:
        yield c
