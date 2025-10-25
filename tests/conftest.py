import os
import sys
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import mongomock

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from main import app
from db.database import get_db


@pytest.fixture(scope="function")
def mock_db():
    """Create a fresh MongoDB mock for each test."""
    client = mongomock.MongoClient()
    db = client.content_db
    yield db
    client.close()


@pytest.fixture()
def client(mock_db):
    """Create a test client with mocked database."""
    def _get_test_db():
        return mock_db

    # Mock the get_db function to return our test database
    with patch("db.database.get_db", side_effect=_get_test_db):
        # Also patch in the database modules that import get_db
        with patch("databases.songs_database.get_db", side_effect=_get_test_db), \
             patch("databases.playlists_database.get_db", side_effect=_get_test_db), \
             patch("databases.history_database.get_db", side_effect=_get_test_db), \
             patch("databases.collections_database.get_db", side_effect=_get_test_db):
            with TestClient(app) as test_client:
                yield test_client