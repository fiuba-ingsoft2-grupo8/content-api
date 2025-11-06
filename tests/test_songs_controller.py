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


class TestSongPublishingRules:
    """Test suite for song publishing and visibility rules."""

    def test_standalone_song_is_visible(self, client, sample_song_data):
        """A song not in any collection should be visible."""
        created = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Should be visible in list
        response = client.get("/songs")
        assert response.status_code == 200
        songs = response.json()["data"]
        assert len(songs) == 1
        assert songs[0]["_id"] == created["_id"]
        
        # Should be visible by ID
        response = client.get(f"/songs/{created['_id']}")
        assert response.status_code == 200
        assert response.json()["data"]["_id"] == created["_id"]

    def test_song_in_unpublished_collection_is_hidden(self, client, sample_song_data):
        """A song in an unpublished collection should not be visible."""
        from datetime import datetime, timedelta, timezone
        
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create a collection with future release date
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        collection_data = {
            "name": "Future Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song["_id"]}],
            "releaseDate": future_date
        }
        collection = client.post("/collections", json=collection_data).json()["data"]
        
        # Song should NOT be visible in list
        response = client.get("/songs")
        assert response.status_code == 200
        songs = response.json()["data"]
        assert len(songs) == 0
        
        # Song should NOT be accessible by ID
        response = client.get(f"/songs/{song['_id']}")
        assert response.status_code == 404

    def test_song_in_published_collection_is_visible(self, client, sample_song_data):
        """A song in a published collection should be visible."""
        from datetime import datetime, timezone
        
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create a published collection (no future date)
        collection_data = {
            "name": "Published Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song["_id"]}],
            "releaseDate": datetime.now(timezone.utc).isoformat()
        }
        collection = client.post("/collections", json=collection_data).json()["data"]
        
        # Song should be visible in list
        response = client.get("/songs")
        assert response.status_code == 200
        songs = response.json()["data"]
        assert len(songs) == 1
        assert songs[0]["_id"] == song["_id"]
        
        # Song should be accessible by ID
        response = client.get(f"/songs/{song['_id']}")
        assert response.status_code == 200
        assert response.json()["data"]["_id"] == song["_id"]

    def test_owner_can_see_unpublished_songs_with_flag(self, client, sample_song_data):
        """Owner should see their unpublished songs when includeUnpublished=true."""
        from datetime import datetime, timedelta, timezone
        
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create an unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        collection_data = {
            "name": "Future Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song["_id"]}],
            "releaseDate": future_date
        }
        collection = client.post("/collections", json=collection_data).json()["data"]
        
        # Without flag, song is not visible
        response = client.get("/songs")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 0
        
        # With flag, owner can see it
        response = client.get("/songs?includeUnpublished=true")
        assert response.status_code == 200
        songs = response.json()["data"]
        assert len(songs) == 1
        assert songs[0]["_id"] == song["_id"]
        
        # Can also access by ID with flag
        response = client.get(f"/songs/{song['_id']}?includeUnpublished=true")
        assert response.status_code == 200
        assert response.json()["data"]["_id"] == song["_id"]

    def test_early_release_song_is_visible_after_early_date(self, client, sample_song_data):
        """A song with early_release_date should be visible after that date."""
        from datetime import datetime, timedelta, timezone
        
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create a collection with future release date and early release for the song
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        early_date = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()  # 1 hour ago
        
        collection_data = {
            "name": "Future Album with Early Single",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song["_id"], "earlyReleaseDate": early_date}],
            "releaseDate": future_date
        }
        collection = client.post("/collections", json=collection_data).json()["data"]
        
        # Song should be visible (early release date has passed)
        response = client.get("/songs")
        assert response.status_code == 200
        songs = response.json()["data"]
        assert len(songs) == 1
        assert songs[0]["_id"] == song["_id"]
        
        # Song should be accessible by ID
        response = client.get(f"/songs/{song['_id']}")
        assert response.status_code == 200
        assert response.json()["data"]["_id"] == song["_id"]

    def test_song_with_future_early_release_is_hidden(self, client, sample_song_data):
        """A song with future early_release_date should not be visible yet."""
        from datetime import datetime, timedelta, timezone
        
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create a collection with future dates
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        future_early = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        
        collection_data = {
            "name": "Future Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song["_id"], "earlyReleaseDate": future_early}],
            "releaseDate": future_date
        }
        collection = client.post("/collections", json=collection_data).json()["data"]
        
        # Song should NOT be visible
        response = client.get("/songs")
        assert response.status_code == 200
        songs = response.json()["data"]
        assert len(songs) == 0
        
        # Song should NOT be accessible by ID
        response = client.get(f"/songs/{song['_id']}")
        assert response.status_code == 404

    def test_owner_can_update_unpublished_song(self, client, sample_song_data):
        """Owner should be able to update their unpublished songs."""
        from datetime import datetime, timedelta, timezone
        
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create an unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        collection_data = {
            "name": "Future Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song["_id"]}],
            "releaseDate": future_date
        }
        collection = client.post("/collections", json=collection_data).json()["data"]
        
        # Owner should be able to update the song
        update_data = {"title": "Updated Title", "artist": "Updated Artist", "duration": "180"}
        response = client.put(f"/songs/{song['_id']}", json=update_data)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["title"] == "Updated Title"
        assert data["artist"] == "Updated Artist"

    def test_owner_can_delete_unpublished_song(self, client, sample_song_data):
        """Owner should be able to delete their unpublished songs."""
        from datetime import datetime, timedelta, timezone
        
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create an unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        collection_data = {
            "name": "Future Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song["_id"]}],
            "releaseDate": future_date
        }
        collection = client.post("/collections", json=collection_data).json()["data"]
        
        # Owner should be able to delete the song
        response = client.delete(f"/songs/{song['_id']}")
        assert response.status_code == 204


class TestSongLikedStatus:
    """Test suite for checking if a song is liked by the authenticated user."""

    def test_song_not_liked_returns_false(self, client, sample_song_data):
        """Get song should return isLiked=false when song is not liked."""
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Get the song - should show isLiked=false
        response = client.get(f"/songs/{song['_id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "isLiked" in data
        assert data["isLiked"] is False

    def test_song_liked_returns_true(self, client, sample_song_data):
        """Get song should return isLiked=true when song is liked."""
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create liked songs playlist first
        client.post("/likedSongs")
        
        # Like the song
        client.post(f"/likedSongs/{song['_id']}")
        
        # Get the song - should show isLiked=true
        response = client.get(f"/songs/{song['_id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "isLiked" in data
        assert data["isLiked"] is True

    def test_song_unliked_returns_false(self, client, sample_song_data):
        """Get song should return isLiked=false after unliking."""
        # Create a song
        song = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create liked songs playlist first
        client.post("/likedSongs")
        
        # Like the song
        client.post(f"/likedSongs/{song['_id']}")
        
        # Verify it's liked
        response = client.get(f"/songs/{song['_id']}")
        assert response.json()["data"]["isLiked"] is True
        
        # Unlike the song
        client.delete(f"/likedSongs/{song['_id']}")
        
        # Get the song - should show isLiked=false
        response = client.get(f"/songs/{song['_id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "isLiked" in data
        assert data["isLiked"] is False

    def test_multiple_songs_different_liked_status(self, client, sample_song_data):
        """Test that different songs can have different liked status."""
        # Create two songs
        song1 = client.post("/songs", json=sample_song_data).json()["data"]
        sample_song_data["title"] = "Another Song"
        song2 = client.post("/songs", json=sample_song_data).json()["data"]
        
        # Create liked songs playlist
        client.post("/likedSongs")
        
        # Like only the first song
        client.post(f"/likedSongs/{song1['_id']}")
        
        # Check first song - should be liked
        response1 = client.get(f"/songs/{song1['_id']}")
        assert response1.status_code == 200
        assert response1.json()["data"]["isLiked"] is True
        
        # Check second song - should not be liked
        response2 = client.get(f"/songs/{song2['_id']}")
        assert response2.status_code == 200
        assert response2.json()["data"]["isLiked"] is False

