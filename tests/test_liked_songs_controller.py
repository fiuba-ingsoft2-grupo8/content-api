import pytest


class TestLikedSongsEndpoints:
    """Test suite for liked songs related API endpoints."""

    def test_create_liked_songs_playlist(self, client):
        """Create a 'Liked Songs' playlist for a user."""
        response = client.post("/likedSongs")

        assert response.status_code == 201

        data = response.json()["data"]

        assert data["name"] == "Liked Songs"
        assert data["description"] == ""
        assert data["isPublished"] is True
        # In test mode, userId comes from auth token (test_user_123)
        assert data["userId"] == "test_user_123"
        assert isinstance(data["publishedAt"], str)
        assert data["songs"] == []
        assert data["isLikedSongs"] is True

        playlist_id = data["id"]
        get_response = client.get(f"/likedSongs")
        assert get_response.status_code == 200
        fetched = get_response.json()["data"]
        assert fetched["name"] == "Liked Songs"
        assert fetched["userId"] == "test_user_123"

    def test_add_song_to_liked_songs(self, client):
        """Add a song to the user's liked songs playlist."""
        playlist_response = client.post("/likedSongs")
        assert playlist_response.status_code == 201
        playlist_id = playlist_response.json()["data"]["id"]

        song_response = client.post("/songs", json={"title": "Fortnight", "duration": "60"})
        assert song_response.status_code == 201
        song_id = song_response.json()["data"]["_id"]

        # The endpoint changed to have songId in the URL path
        add_response = client.post(f"/likedSongs/{song_id}")
        assert add_response.status_code == 200
        data = add_response.json()["data"]
        assert data["id"] == playlist_id
        assert len(data["songs"]) == 1
        assert data["songs"][0]["id"] == song_id

        get_response = client.get(f"/likedSongs")
        assert get_response.status_code == 200
        fetched = get_response.json()["data"]
        assert any(song["id"] == song_id for song in fetched["songs"])

    def test_remove_song_from_liked_songs(self, client):
        """Remove a song from the user's liked songs playlist."""
        playlist = client.post("/likedSongs").json()["data"]

        song = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]
        client.post(f"/likedSongs/{song['_id']}")

        # The endpoint changed to have songId in the URL path
        response = client.delete(f"/likedSongs/{song['_id']}")
        assert response.status_code == 200

        get_response = client.get(f"/likedSongs")
        assert get_response.status_code == 200
        data = get_response.json()["data"]
        assert data["songs"] == []

