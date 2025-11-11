import pytest
from datetime import datetime


class TestActivityEndpoints:
    """Test suite for activity endpoints."""

    def test_get_user_activity_no_activity(self, client):
        """Get activity for a user with no activity."""
        response = client.get("/activity/test_user_123")
        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        # User has no activity yet, should return empty list
        assert len(data) == 0

    def test_get_user_activity_with_likes(self, client):
        """Get activity for a user with likes."""
        # Create a song
        song = client.post("/songs", json={"title": "Test Song", "duration": "180"}).json()["data"]
        
        # Like the song by adding it to liked songs playlist
        client.post(f"/likedSongs/{song['_id']}")
        
        # Get activity
        response = client.get("/activity/test_user_123")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 1
        
        # Find the like activity
        like_activities = [a for a in data if a["type"] == "like"]
        assert len(like_activities) >= 1
        like = like_activities[0]
        assert like["userId"] == "test_user_123"
        assert like["targetType"] == "song"
        assert "song" in like
        assert like["song"]["_id"] == song["_id"]

    def test_get_user_activity_with_plays(self, client):
        """Get activity for a user with song plays."""
        # Create a song
        song = client.post("/songs", json={"title": "Played Song", "duration": "200"}).json()["data"]
        
        # Play the song (this adds it to history and records a play)
        client.post("/history", json={"songId": song["_id"]})
        
        # Get activity
        response = client.get("/activity/test_user_123")
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Should have at least one play activity
        play_activities = [a for a in data if a["type"] == "play"]
        assert len(play_activities) >= 1
        play = play_activities[0]
        assert play["userId"] == "test_user_123"
        assert play["songId"] == song["_id"]
        assert "song" in play

    def test_get_user_activity_with_published_playlist(self, client):
        """Get activity for a user with published playlists."""
        # Create a playlist
        playlist = client.post("/playlists", json={
            "name": "Test Playlist",
            "description": "Test Description"
        }).json()["data"]
        
        # Publish it
        client.post(f"/playlists/{playlist['id']}/publish")
        
        # Get activity
        response = client.get("/activity/test_user_123")
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Should have playlist_published activity
        playlist_activities = [a for a in data if a["type"] == "playlist_published"]
        assert len(playlist_activities) >= 1
        pl_activity = playlist_activities[0]
        assert pl_activity["userId"] == "test_user_123"
        assert pl_activity["playlistId"] == playlist["id"]
        assert pl_activity["playlistName"] == "Test Playlist"

    def test_get_user_activity_mixed(self, client):
        """Get activity for a user with multiple types of activities."""
        # Create a song
        song = client.post("/songs", json={"title": "Mixed Activity Song", "duration": "150"}).json()["data"]
        
        # Like the song
        client.post(f"/likedSongs/{song['_id']}")
        
        # Play the song
        client.post("/history", json={"songId": song["_id"]})
        
        # Create and publish a playlist
        playlist = client.post("/playlists", json={
            "name": "Mixed Activity Playlist",
            "description": "Test"
        }).json()["data"]
        client.post(f"/playlists/{playlist['id']}/publish")
        
        # Get activity
        response = client.get("/activity/test_user_123")
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Should have multiple types of activities
        types = set([a["type"] for a in data])
        assert "like" in types
        assert "play" in types
        assert "playlist_published" in types

    def test_get_user_activity_with_limit(self, client):
        """Test that the limit parameter works correctly."""
        # Create multiple songs and like them
        for i in range(10):
            song = client.post("/songs", json={
                "title": f"Song {i}",
                "duration": "180"
            }).json()["data"]
            client.post(f"/likedSongs/{song['_id']}")
        
        # Get activity with limit of 5
        response = client.get("/activity/test_user_123?limit=5")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) <= 5

    def test_get_user_activity_chronological_order(self, client):
        """Test that activities are ordered chronologically (most recent first)."""
        # Create songs and like them
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        client.post(f"/likedSongs/{song1['_id']}")
        
        song2 = client.post("/songs", json={"title": "Song 2", "duration": "180"}).json()["data"]
        client.post(f"/likedSongs/{song2['_id']}")
        
        # Get activity
        response = client.get("/activity/test_user_123")
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Verify chronological order (most recent first)
        if len(data) >= 2:
            timestamps = [datetime.fromisoformat(a["timestamp"].replace("Z", "+00:00")) for a in data]
            for i in range(len(timestamps) - 1):
                assert timestamps[i] >= timestamps[i + 1], "Activities should be ordered from most recent to oldest"

    def test_get_following_activity_empty(self, client):
        """Test getting following activity feed when not following anyone."""
        response = client.get("/activity?limit=50")
        assert response.status_code == 200
        data = response.json()["data"]
        # Should return empty list since follows feature is not implemented yet
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_following_activity_with_limit(self, client):
        """Test that the limit parameter works for following activity."""
        response = client.get("/activity?limit=10")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) <= 10

    def test_invalid_limit_too_high(self, client):
        """Test that limit above 100 returns validation error."""
        response = client.get("/activity/test_user_123?limit=150")
        assert response.status_code == 400

    def test_invalid_limit_too_low(self, client):
        """Test that limit below 1 returns validation error."""
        response = client.get("/activity/test_user_123?limit=0")
        assert response.status_code == 400

    def test_activity_includes_enriched_data(self, client):
        """Test that activities include enriched data about songs, collections, etc."""
        # Create and like a song
        song = client.post("/songs", json={
            "title": "Enriched Song",
            "duration": "180"
        }).json()["data"]
        client.post(f"/likedSongs/{song['_id']}")
        
        # Get activity
        response = client.get("/activity/test_user_123")
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Find like activity and verify enrichment
        like_activities = [a for a in data if a["type"] == "like"]
        if like_activities:
            like = like_activities[0]
            assert "song" in like
            assert like["song"]["title"] == "Enriched Song"
            assert like["song"]["artist"] == "Test Artist"

