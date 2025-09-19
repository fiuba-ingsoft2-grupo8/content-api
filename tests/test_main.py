import pytest
from bson import ObjectId
from datetime import datetime


@pytest.fixture
def sample_song_data():
    return {"title": "Test Song", "artist": "Test Artist"}


@pytest.fixture  
def sample_playlist_data():
    return {"name": "Test Playlist", "description": "A test playlist"}


class TestSongEndpoints:
    """Test suite for song-related API endpoints."""

    def test_create_song_success(self, client, sample_song_data):
        """Test successful creation of a new song."""
        response = client.post("/songs", json=sample_song_data)

        assert response.status_code == 201
        data = response.json()
        assert "data" in data
        assert data["data"]["title"] == sample_song_data["title"]
        assert data["data"]["artist"] == sample_song_data["artist"]
        assert "_id" in data["data"]
        # Verify the returned ID is a valid ObjectId string
        assert ObjectId.is_valid(data["data"]["_id"])

    def test_create_song_validation_error(self, client):
        """Test validation errors when creating a song with invalid data."""
        # Test missing request body
        response = client.post("/songs")
        assert response.status_code == 400
        assert response.json()["title"] == "Bad Request"
        assert response.json()["detail"] == "Invalid request body"

        # Test missing artist field
        response = client.post("/songs", json={"title": "Test Song"})
        assert response.status_code == 400

        # Test invalid data types
        response = client.post("/songs", json={"title": 123, "artist": "Test Artist"})
        assert response.status_code == 400