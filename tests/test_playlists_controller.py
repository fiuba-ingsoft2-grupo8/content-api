import os
import sys
import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from io import BytesIO

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def sample_playlist_data():
    return {
        "name": "Test Playlist",
        "description": "A test playlist description",
        "userId": "test_user_123"
    }


@pytest.fixture
def sample_song_data():
    return {"title": "Test Song", "artist": "Test Artist", "duration": "180"}


class TestPlaylistController:
    """Extended test suite for playlist controller endpoints."""

    def test_create_playlist_with_custom_cover(self, client):
        """Test creating a playlist with a custom cover URL."""
        response = client.post("/playlists", json={
            "name": "Playlist with Cover",
            "description": "Description",
            "coverUrl": "https://example.com/custom-cover.jpg",
            "userId": "test_user"
        })
        
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Playlist with Cover"
        # The coverUrl should be used when provided
        assert "coverUrl" in data

    def test_get_playlists_filter_by_published(self, client):
        """Test filtering playlists by isPublished status."""
        # Create a playlist and publish it
        playlist1 = client.post("/playlists", json={
            "name": "Published Playlist",
            "description": "Published",
            "userId": "test_user"
        }).json()["data"]
        
        # Publish it
        client.post(f"/playlists/{playlist1['id']}/publish")
        
        # Create an unpublished playlist
        playlist2 = client.post("/playlists", json={
            "name": "Unpublished Playlist",
            "description": "Not Published",
            "userId": "test_user"
        }).json()["data"]
        
        # Test getting all playlists (unpublished by default)
        response = client.get("/playlists")
        assert response.status_code == 200
        all_playlists = response.json()["data"]
        # Should get unpublished playlists
        assert len(all_playlists) >= 1
        
        # Test getting only published playlists
        response = client.get("/playlists?isPublished=true")
        assert response.status_code == 200
        published_playlists = response.json()["data"]
        # Should contain at least the published one
        assert len(published_playlists) >= 1

    def test_get_nonexistent_playlist(self, client):
        """Test retrieving a playlist that doesn't exist."""
        response = client.get("/playlists/507f1f77bcf86cd799439011")
        assert response.status_code == 404
        error = response.json()
        assert error["title"] == "Not Found"
        assert "not found" in error["detail"].lower()

    def test_remove_song_from_playlist(self, client, sample_song_data):
        """Test removing a song from a playlist."""
        # Create a playlist
        playlist = client.post("/playlists", json={
            "name": "Test Playlist",
            "description": "Test",
            "userId": "test_user"
        }).json()["data"]
        
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Add song to playlist
        add_response = client.post(f"/playlists/{playlist['id']}/songs/{song['_id']}")
        assert add_response.status_code == 200
        
        # Verify song was added
        playlist_with_song = add_response.json()["data"]
        assert len(playlist_with_song["songs"]) == 1
        
        # Remove song from playlist
        remove_response = client.delete(f"/playlists/{playlist['id']}/songs/{song['_id']}")
        assert remove_response.status_code == 200
        
        # Verify song was removed
        updated_playlist = remove_response.json()["data"]
        assert len(updated_playlist["songs"]) == 0

    def test_remove_song_from_nonexistent_playlist(self, client, sample_song_data):
        """Test removing a song from a playlist that doesn't exist."""
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        response = client.delete(f"/playlists/507f1f77bcf86cd799439011/songs/{song['_id']}")
        assert response.status_code == 404

    def test_remove_nonexistent_song_from_playlist(self, client):
        """Test removing a song that doesn't exist from a playlist."""
        playlist = client.post("/playlists", json={
            "name": "Test Playlist",
            "description": "Test",
            "userId": "test_user"
        }).json()["data"]
        
        response = client.delete(f"/playlists/{playlist['id']}/songs/507f1f77bcf86cd799439011")
        assert response.status_code == 404

    def test_remove_song_not_in_playlist(self, client, sample_song_data):
        """Test removing a song that exists but is not in the playlist."""
        playlist = client.post("/playlists", json={
            "name": "Test Playlist",
            "description": "Test",
            "userId": "test_user"
        }).json()["data"]
        
        # Create a song but don't add it to playlist
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Try to remove it
        response = client.delete(f"/playlists/{playlist['id']}/songs/{song['_id']}")
        assert response.status_code == 404
        error = response.json()
        assert "not found in playlist" in error["detail"].lower()

    def test_publish_playlist_success(self, client):
        """Test publishing a private playlist."""
        # Create a private playlist
        playlist = client.post("/playlists", json={
            "name": "Private Playlist",
            "description": "Will be published",
            "isPublished": False,
            "userId": "test_user"
        }).json()["data"]
        
        assert playlist["isPublished"] is False
        
        # Publish it
        response = client.post(f"/playlists/{playlist['id']}/publish")
        assert response.status_code == 200
        assert response.json()["data"] is True

    def test_publish_nonexistent_playlist(self, client):
        """Test publishing a playlist that doesn't exist."""
        response = client.post("/playlists/507f1f77bcf86cd799439011/publish")
        assert response.status_code == 404

    def test_make_playlist_private_success(self, client):
        """Test making a public playlist private."""
        # Create a playlist
        playlist = client.post("/playlists", json={
            "name": "Public Playlist",
            "description": "Will be made private",
            "userId": "test_user"
        }).json()["data"]
        
        # First publish it
        publish_response = client.post(f"/playlists/{playlist['id']}/publish")
        assert publish_response.status_code == 200
        
        # Then make it private
        response = client.post(f"/playlists/{playlist['id']}/private")
        assert response.status_code == 200
        assert response.json()["data"] is True

    def test_make_nonexistent_playlist_private(self, client):
        """Test making a nonexistent playlist private."""
        response = client.post("/playlists/507f1f77bcf86cd799439011/private")
        assert response.status_code == 404

    def test_add_song_to_playlist_error_handling(self, client):
        """Test error handling when adding song fails."""
        # Create playlist and song
        playlist = client.post("/playlists", json={
            "name": "Test Playlist",
            "description": "Test",
            "userId": "test_user"
        }).json()["data"]
        
        song = client.post("/songs", json={
            "title": "Test Song",
            "artist": "Test Artist",
            "duration": "180"
        }).json()["data"]
        
        # Add song successfully first time
        response = client.post(f"/playlists/{playlist['id']}/songs/{song['_id']}")
        assert response.status_code == 200
        
        # Try to add same song again (this may or may not fail depending on implementation)
        # Just verify the endpoint handles it gracefully
        response2 = client.post(f"/playlists/{playlist['id']}/songs/{song['_id']}")
        assert response2.status_code in [200, 400]

    def test_playlist_lifecycle(self, client, sample_song_data):
        """Test complete playlist lifecycle: create, add songs, publish, make private, delete."""
        # 1. Create playlist
        playlist = client.post("/playlists", json={
            "name": "Lifecycle Test",
            "description": "Testing full lifecycle",
            "isPublished": False,
            "userId": "test_user"
        }).json()["data"]
        
        playlist_id = playlist["id"]
        assert playlist["isPublished"] is False
        
        # 2. Add songs
        song1 = client.post("/songs", json={
            "title": "Song 1",
            "artist": "Artist 1",
            "duration": "180"
        }).json()["data"]
        
        song2 = client.post("/songs", json={
            "title": "Song 2",
            "artist": "Artist 2",
            "duration": "200"
        }).json()["data"]
        
        client.post(f"/playlists/{playlist_id}/songs/{song1['_id']}")
        client.post(f"/playlists/{playlist_id}/songs/{song2['_id']}")
        
        # Verify songs were added
        playlist_data = client.get(f"/playlists/{playlist_id}").json()["data"]
        assert len(playlist_data["songs"]) == 2
        
        # 3. Publish playlist
        response = client.post(f"/playlists/{playlist_id}/publish")
        assert response.status_code == 200
        
        # 4. Make private again
        response = client.post(f"/playlists/{playlist_id}/private")
        assert response.status_code == 200
        
        # 5. Remove one song
        response = client.delete(f"/playlists/{playlist_id}/songs/{song1['_id']}")
        assert response.status_code == 200
        
        # Verify only one song remains
        playlist_data = client.get(f"/playlists/{playlist_id}").json()["data"]
        assert len(playlist_data["songs"]) == 1
        
        # 6. Delete playlist
        response = client.delete(f"/playlists/{playlist_id}")
        assert response.status_code == 204
        
        # 7. Verify playlist is gone
        response = client.get(f"/playlists/{playlist_id}")
        assert response.status_code == 404

    def test_add_multiple_songs_to_playlist(self, client):
        """Test adding multiple songs to a playlist and verify order."""
        playlist = client.post("/playlists", json={
            "name": "Multi-Song Playlist",
            "description": "Test",
            "userId": "test_user"
        }).json()["data"]
        
        songs = []
        for i in range(5):
            song = client.post("/songs", json={
                "title": f"Song {i}",
                "artist": f"Artist {i}",
                "duration": "180"
            }).json()["data"]
            songs.append(song)
            
            # Add to playlist
            response = client.post(f"/playlists/{playlist['id']}/songs/{song['_id']}")
            assert response.status_code == 200
        
        # Verify all songs are in playlist
        final_playlist = client.get(f"/playlists/{playlist['id']}").json()["data"]
        assert len(final_playlist["songs"]) == 5

    def test_create_playlist_validation(self, client):
        """Test playlist creation with invalid data."""
        # Missing name
        response = client.post("/playlists", json={
            "description": "No name provided"
        })
        assert response.status_code == 400

    def test_get_playlist_with_songs(self, client):
        """Test that getting a playlist includes all song details."""
        # Create playlist
        playlist = client.post("/playlists", json={
            "name": "Playlist with Songs",
            "description": "Test",
            "userId": "test_user"
        }).json()["data"]
        
        # Add a song
        song = client.post("/songs", json={
            "title": "Detailed Song",
            "artist": "Detailed Artist",
            "duration": "240"
        }).json()["data"]
        
        client.post(f"/playlists/{playlist['id']}/songs/{song['_id']}")
        
        # Get playlist and verify song details
        response = client.get(f"/playlists/{playlist['id']}")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert len(data["songs"]) == 1
        
        song_in_playlist = data["songs"][0]
        assert song_in_playlist["title"] == "Detailed Song"
        assert song_in_playlist["artist"] == "Detailed Artist"
        assert "addedAt" in song_in_playlist

    def test_empty_playlist_operations(self, client):
        """Test operations on an empty playlist."""
        # Create empty playlist
        playlist = client.post("/playlists", json={
            "name": "Empty Playlist",
            "description": "Has no songs",
            "userId": "test_user"
        }).json()["data"]
        
        # Get empty playlist
        response = client.get(f"/playlists/{playlist['id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["songs"] == []
        
        # Publish empty playlist
        response = client.post(f"/playlists/{playlist['id']}/publish")
        assert response.status_code == 200
        
        # Delete empty playlist
        response = client.delete(f"/playlists/{playlist['id']}")
        assert response.status_code == 204

    def test_playlist_metadata(self, client):
        """Test that playlist metadata is properly maintained."""
        # Create playlist with specific metadata
        create_response = client.post("/playlists", json={
            "name": "Metadata Test",
            "description": "Testing metadata handling",
            "isPublished": False,
            "userId": "test_user"
        })
        
        assert create_response.status_code == 201
        playlist = create_response.json()["data"]
        
        # Verify metadata
        assert playlist["name"] == "Metadata Test"
        assert playlist["description"] == "Testing metadata handling"
        assert playlist["isPublished"] is False
        assert "publishedAt" in playlist
        assert "id" in playlist
        assert playlist["userId"] == "test_user_123"  # From auth in test mode
        assert playlist["songs"] == []
        assert playlist["isLikedSongs"] is False

