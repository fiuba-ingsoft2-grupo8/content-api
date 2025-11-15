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
             patch("databases.collections_database.get_db", side_effect=_get_test_db), \
             patch("databases.metrics_database.get_db", side_effect=_get_test_db), \
             patch("databases.about_database.get_db", side_effect=_get_test_db), \
             patch("databases.activity_database.get_db", side_effect=_get_test_db), \
             patch("databases.share_database.get_db", side_effect=_get_test_db), \
             patch("controllers.liked_songs_controller.metrics_db.get_db", side_effect=_get_test_db):
            with TestClient(app) as test_client:
                yield test_client


@pytest.fixture
def sample_song_data():
    """Fixture providing sample song data for tests."""
    return {"title": "Test Song", "duration": "60"}


@pytest.fixture  
def sample_playlist_data():
    """Fixture providing sample playlist data for tests."""
    return {"name": "Test Playlist", "description": "A test playlist", "userId": "uu8432"}


@pytest.fixture()
def client_other_user(mock_db):
    """Create a test client with a different user for multi-user tests."""
    def _get_test_db():
        return mock_db

    # Mock verify_token to return a different user
    async def mock_verify_other_user(*args, **kwargs):
        return {"user_id": "other_user_456", "stage_name": "Other Artist", "user_type": "artist"}

    # Mock the get_db function and verify_token
    with patch("db.database.get_db", side_effect=_get_test_db):
        with patch("databases.songs_database.get_db", side_effect=_get_test_db), \
             patch("databases.playlists_database.get_db", side_effect=_get_test_db), \
             patch("databases.history_database.get_db", side_effect=_get_test_db), \
             patch("databases.collections_database.get_db", side_effect=_get_test_db), \
             patch("databases.metrics_database.get_db", side_effect=_get_test_db), \
             patch("databases.about_database.get_db", side_effect=_get_test_db), \
             patch("databases.activity_database.get_db", side_effect=_get_test_db), \
             patch("databases.share_database.get_db", side_effect=_get_test_db), \
             patch("controllers.liked_songs_controller.metrics_db.get_db", side_effect=_get_test_db), \
             patch("auth.verify_token", side_effect=mock_verify_other_user):
            with TestClient(app) as test_client:
                yield test_client