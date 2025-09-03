import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from testcontainers.mysql import MySqlContainer

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from main import app
from db.database import Base, get_db


@pytest.fixture(scope="session")
def mysql_container():
    with MySqlContainer("mysql:8.0") as mysql:
        yield mysql


@pytest.fixture(scope="session")
def engine(mysql_container):
    dsn = mysql_container.get_connection_url()
    dsn = dsn.replace("mysql://", "mysql+pymysql://")
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
        
        # Reset auto-increment counters to ensure consistent test behavior
        # This prevents IDs from accumulating across tests
        try:
            with engine.connect() as reset_conn:
                reset_conn.execute(text("ALTER TABLE songs AUTO_INCREMENT = 1"))
                reset_conn.execute(text("ALTER TABLE playlists AUTO_INCREMENT = 1"))
                reset_conn.commit()
        except Exception as e:
            print(f"Warning: Failed to reset auto-increment counters: {e}")
        
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
