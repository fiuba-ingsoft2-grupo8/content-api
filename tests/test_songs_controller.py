import pytest
from bson import ObjectId


class TestSongEndpoints:
    """Test suite for song-related API endpoints."""

    def test_create_song_success(self, client, sample_song_data):
        """Test successful creation of a new song."""
        response = client.post("/songs", json=sample_song_data)

        assert response.status_code == 201
        data = response.json()
        assert "data" in data
        assert data["data"]["title"] == sample_song_data["title"]
        assert data["data"]["artist"] == "Test Artist"  # Artist comes from token stage_name
        assert "_id" in data["data"]
        assert ObjectId.is_valid(data["data"]["_id"])


    def test_create_song_validation_error(self, client):
        """Test validation errors when creating a song with invalid data."""
        response = client.post("/songs")
        assert response.status_code == 400
        assert response.json()["title"] == "Bad Request"
        assert response.json()["detail"] == "Invalid request body"

        response = client.post("/songs", json={"title": "Test Song"})
        assert response.status_code == 400

        response = client.post("/songs", json={"title": 123})
        assert response.status_code == 400

    def test_get_empty_song_list(self, client):
        """Should return empty song list initially."""
        response = client.get("/songs")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 0

    def test_get_song_by_id(self, client, sample_song_data):
        """Should fetch song by ID after creation."""
        created = client.post("/songs", json=sample_song_data).json()["data"]

        response = client.get(f"/songs/{created['_id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["_id"] == created["_id"]
        assert data["title"] == sample_song_data["title"]

    def test_update_song(self, client, sample_song_data):
        """Should update existing song fields."""
        created = client.post("/songs", json=sample_song_data).json()["data"]

        update_data = {"title": "Fortnight", "artist": "Taylor Swift ft. Post Malone", "duration": "60"}
        response = client.put(f"/songs/{created['_id']}", json=update_data)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["title"] == "Fortnight"
        assert data["artist"] == "Taylor Swift ft. Post Malone"  # Artist can still be updated

    def test_delete_song(self, client, sample_song_data):
        """Should delete a song and return 404 on fetch."""
        created = client.post("/songs", json=sample_song_data).json()["data"]

        response = client.delete(f"/songs/{created['_id']}")
        assert response.status_code == 204

        check = client.get(f"/songs/{created['_id']}")
        assert check.status_code == 404

    def test_create_song_missing_title(self, client):
        """Should not create a song if title is missing."""
        response = client.post("/songs", json={"duration": "60"})
        assert response.status_code == 400

    def test_get_nonexistent_song(self, client):
        """Should return 404 when song ID does not exist."""
        response = client.get("/songs/68ceb28af48aee23d3c773ea")
        assert response.status_code == 404

