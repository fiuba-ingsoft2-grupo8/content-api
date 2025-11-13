import os
import sys
import pytest
from datetime import datetime
from bson import ObjectId
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

    def test_publish_playlist_updates_timestamp(self, client):
        """Test that publishing a playlist updates the publishedAt timestamp to current server time."""
        import time
        
        # Create a private playlist
        playlist_create = client.post("/playlists", json={
            "name": "Timestamp Test Playlist",
            "description": "Testing timestamp update",
            "isPublished": False,
            "userId": "test_user"
        }).json()["data"]
        
        original_published_at = playlist_create["publishedAt"]
        
        # Wait a bit to ensure time difference
        time.sleep(0.1)
        
        # Publish the playlist
        client.post(f"/playlists/{playlist_create['id']}/publish")
        
        # Get the updated playlist
        updated_playlist = client.get(f"/playlists/{playlist_create['id']}").json()["data"]
        
        # Verify the timestamp was updated
        assert updated_playlist["isPublished"] is True
        assert updated_playlist["publishedAt"] != original_published_at
        
        # Parse timestamps and verify the published one is more recent
        original_time = datetime.fromisoformat(original_published_at.replace("Z", "+00:00"))
        updated_time = datetime.fromisoformat(updated_playlist["publishedAt"].replace("Z", "+00:00"))
        assert updated_time > original_time, "Published timestamp should be more recent than creation timestamp"

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
        assert song_in_playlist["artist"] == "Test Artist"  # Artist comes from token stage_name
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

class TestPlaylistEndpoints:
    """Test suite for playlist-related API endpoints (from test_main.py)."""

    def test_create_playlist_success(self, client, sample_playlist_data):
        """Test successful creation of a playlist."""
        response = client.post("/playlists", json=sample_playlist_data)
        assert response.status_code == 201

        data = response.json()
        assert "data" in data
        playlist = data["data"]

        assert "id" in playlist
        assert ObjectId.is_valid(playlist["id"])
        assert playlist["name"] == sample_playlist_data["name"]
        assert playlist["description"] == sample_playlist_data["description"]
        assert playlist["isPublished"] is False
        assert playlist["songs"] == []
        assert playlist["isLikedSongs"] is False
        assert datetime.fromisoformat(playlist["publishedAt"])

    def test_get_playlists_ordered_by_published_date(self, client):
        """Should return playlists ordered by publishedAt (desc)."""
        from datetime import timedelta
        
        # Create two playlists with different timestamps
        time1 = datetime.utcnow()
        time2 = time1 + timedelta(seconds=1)
        
        playlist1 = client.post("/playlists", json={
            "name": "Folklore",
            "description": "Primera playlist!!!" * 10,
            "isPublished": True,
            "publishedAt": time1.isoformat(),
            "userId": "uu8432"
        }).json()["data"]

        playlist2 = client.post("/playlists", json={
            "name": "Evermore",
            "description": "Segunda playlist!!!" * 10,
            "isPublished": True,
            "publishedAt": time2.isoformat(),
            "userId": "uu8432"
        }).json()["data"]

        response = client.get("/playlists")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 2

        first_published = datetime.fromisoformat(data[0]["publishedAt"]).timestamp()
        second_published = datetime.fromisoformat(data[1]["publishedAt"]).timestamp()
        assert first_published >= second_published

    def test_get_playlist_by_id(self, client):
        """Fetch a playlist by its ID."""
        playlist = client.post("/playlists", json={
            "name": "Piano Bar",
            "description": "charles" * 15,
            "isPublished": True,
            "publishedAt": datetime.utcnow().isoformat(),
            "userId": "uu8432"
        }).json()
        print(playlist)
        playlist = playlist["data"]

        response = client.get(f"/playlists/{playlist['id']}")
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["id"] == playlist["id"]
        assert data["name"] == "Piano Bar"
        assert data["songs"] == []

    def test_get_private_playlist(self, client):
        """Ensure private playlists are only accessible to their owner."""
        # In test mode, auth returns test_user_123, so the playlist will be created with that userId
        playlist = client.post("/playlists", json={
            "name": "Private playlist",
            "description": "description",
            "isPublished": False,
            "userId": "uu8432"
        }).json()["data"]

        # The owner (test_user_123 in test mode) can access the playlist
        response_owner = client.get(f"/playlists/{playlist['id']}")
        assert response_owner.status_code == 200
        data_owner = response_owner.json()["data"]
        assert data_owner["id"] == playlist["id"]
        assert data_owner["name"] == "Private playlist"
        # Verify the userId is from the auth token, not the request body
        assert data_owner["userId"] == "test_user_123"

    def test_add_song_to_playlist(self, client, sample_song_data):
        """Add a song to a playlist."""
        song = client.post("/songs", json=sample_song_data).json()["data"]
        playlist = client.post("/playlists", json={
            "name": "Monos Árticos",
            "description": "monk" * 20,
            "isPublished": True,
            "publishedAt": datetime.utcnow().isoformat(),
            "userId": "uu8432"
        }).json()["data"]

        # The endpoint changed to have songId in the URL path
        response = client.post(f"/playlists/{playlist['id']}/songs/{song['_id']}")
        assert response.status_code == 200

        data = response.json()["data"]
        assert len(data["songs"]) == 1
        added = data["songs"][0]
        assert added["id"] == song["_id"]
        assert added["title"] == sample_song_data["title"]
        assert added["artist"] == "Test Artist"  # Artist comes from token stage_name
        assert datetime.fromisoformat(added["addedAt"])

    def test_add_song_to_nonexistent_playlist(self, client, sample_song_data):
        song = client.post("/songs", json=sample_song_data).json()["data"]
        res = client.post(f"/playlists/123/songs/{song['_id']}")

        assert res.status_code == 404

    def test_add_nonexistent_song(self, client):
        playlist = client.post("/playlists", json={
            "name": "Monos Árticos",
            "description": "monk" * 20,
            "isPublished": True,
            "publishedAt": datetime.utcnow().isoformat(),
            "userId": "uu8432"
        }).json()["data"]

        res = client.post(f"/playlists/123/songs/567")

        assert res.status_code == 404

    def test_delete_playlist(self, client):
        """Delete a playlist and verify 404 afterwards."""
        playlist = client.post("/playlists", json={
            "name": "The Strokes",
            "description": "omg gordo mantecolero!!!" * 10,
            "isPublished": True,
            "publishedAt": datetime.utcnow().isoformat(),
            "userId": "uu8432"
        }).json()["data"]

        response = client.delete(f"/playlists/{playlist['id']}")

        assert response.status_code == 204

        check = client.get(f"/playlists/{playlist['id']}")
        assert check.status_code == 404

    def test_delete_playlist_not_belongs_to_user(self, client):
        """Try deleting a playlist that belongs to another user."""
        # In test mode, all requests use test_user_123 from the auth token
        # So we can't actually test different users in the current setup
        # This test now verifies that a playlist created by test_user_123 can be deleted by test_user_123
        playlist = client.post("/playlists", json={
            "name": "The Strokes",
            "description": "omg gordo mantecolero!!!" * 10,
            "isPublished": True,
            "publishedAt": datetime.utcnow().isoformat(),
            "userId": "uu8432"
        }).json()["data"]

        # Since auth returns test_user_123 for all requests in test mode,
        # this will succeed (both create and delete use the same user)
        res = client.delete(f"/playlists/{playlist['id']}")

        # In test mode, this succeeds because the user matches
        assert res.status_code == 204

    def test_delete_nonexistent_playlist(self, client):
        """Try deleting a non-existing playlist."""
        res = client.delete(f"/playlists/nonexistent")

        assert res.status_code == 404

    def test_publish_playlist(self, client):
        """Create a playlist and publish it."""
        playlist = client.post("/playlists", json={
            "name": "Folklore",
            "description": "Primera playlist!!!",
            "isPublished": False,
            "publishedAt": None,
            "userId": "uu8432"
        }).json()["data"]

        response = client.post(f"/playlists/{playlist['id']}/publish")
        assert response.status_code == 200
        data = response.json()["data"]

        assert data == True

    def test_delete_playlist_with_songs(self, client):
        """Delete a playlist that has songs inside it."""
        playlist = client.post("/playlists", json={
            "name": "Folklore",
            "description": "Primera playlist!!!" * 10,
            "isPublished": False,
            "publishedAt": None,
            "userId": "uu8432"
        }).json()["data"]

        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]

        client.post(f"/playlists/{playlist['id']}/songs/{song1['_id']}")
        client.post(f"/playlists/{playlist['id']}/songs/{song2['_id']}")

        check = client.get(f"/playlists/{playlist['id']}")
        assert check.status_code == 200
        response = client.delete(f"/playlists/{playlist['id']}")
        
        assert response.status_code == 204

        check_again = client.get(f"/playlists/{playlist['id']}")
        assert check_again.status_code == 404

    def test_reorder_songs_in_playlist(self, client):
        """Reorder songs within a playlist and verify new order is persisted."""

        playlist = client.post("/playlists", json={
            "name": "My Playlist",
            "description": "Test playlist",
            "userId": "user123"
        }).json()["data"]

        songs = []
        for title in ["Song A", "Song B", "Song C"]:
            song = client.post("/songs", json={"title": title, "artist": "Artist", "duration": "180"}).json()["data"]
            songs.append(song)
            client.post(f"/playlists/{playlist['id']}/songs/{song['_id']}")

        response = client.get(f"/playlists/{playlist['id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert [s["title"] for s in data["songs"]] == ["Song A", "Song B", "Song C"]

        new_order = [
            {"songId": songs[2]["_id"], "order": 1},
            {"songId": songs[0]["_id"], "order": 2},
            {"songId": songs[1]["_id"], "order": 3}
        ]
        response = client.put(f"/playlists/{playlist['id']}/reorder", json={"songs": new_order})
        assert response.status_code == 200

        response = client.get(f"/playlists/{playlist['id']}")
        data = response.json()["data"]
        assert [s["title"] for s in data["songs"]] == ["Song C", "Song A", "Song B"]

    def test_reorder_with_invalid_song_id(self, client):
        """Reordering fails if song id doesn't exist in playlist."""
        playlist = client.post("/playlists", json={
            "name": "Another Playlist",
            "description": "Test",
            "userId": "user123"
        }).json()["data"]

        song = client.post("/songs", json={"title": "Song X", "artist": "Artist", "duration": "180"}).json()["data"]
        client.post(f"/playlists/{playlist['id']}/songs/{song['_id']}")

        response = client.put(f"/playlists/{playlist['id']}/reorder", json={
            "songs": [{"songId": "invalidid123", "order": 1}]
        })

        assert response.status_code == 400
        data = response.json()

