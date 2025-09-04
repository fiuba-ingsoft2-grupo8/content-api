import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from testcontainers.postgres import PostgresContainer

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from main import app
from db.database import Base, get_db


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def engine(postgres_container):
    dsn = postgres_container.get_connection_url()
    engine = create_engine(dsn, pool_pre_ping=True, future=True)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(
        bind=connection, autoflush=False, autocommit=False, future=True
    )
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        
        # Reset sequence counters to ensure consistent test behavior
        # This prevents IDs from accumulating across tests
        try:
            with engine.connect() as reset_conn:
                reset_conn.execute(text("ALTER SEQUENCE songs_id_seq RESTART WITH 1"))
                reset_conn.execute(text("ALTER SEQUENCE playlists_id_seq RESTART WITH 1"))
                reset_conn.commit()
        except Exception as e:
            print(f"Warning: Failed to reset sequence counters: {e}")
        
        connection.close()


@pytest.fixture()
def client(db):
    def _get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
