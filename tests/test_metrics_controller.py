import pytest
from bson import ObjectId

class TestMetricsEndpoints:
    
    # ============= LIKES =============
    
    def test_like_song_via_liked_songs(self, client):
        """Test liking a song via the liked songs playlist."""
        # Create liked songs playlist first
        client.post("/likedSongs/")
        
        # Create a song
        song = client.post("/songs", json={"title": "Test Song", "duration": "180"}).json()["data"]
        
        # Like the song via liked songs endpoint
        response = client.post(f"/likedSongs/{song['_id']}")
        assert response.status_code == 200
        
        # Verify the like was recorded in metrics
        metrics_response = client.get(f"/metrics/songs/{song['_id']}")
        assert metrics_response.status_code == 200
        assert metrics_response.json()["data"]["likes"] >= 1
        
    def test_unlike_song_via_liked_songs(self, client):
        """Test unliking a song via the liked songs playlist."""
        # Create liked songs playlist first
        client.post("/likedSongs/")
        
        # Create a song
        song = client.post("/songs", json={"title": "Test Song", "duration": "180"}).json()["data"]
        
        # Like the song
        client.post(f"/likedSongs/{song['_id']}")
        
        # Unlike the song
        response = client.delete(f"/likedSongs/{song['_id']}")
        assert response.status_code == 200
        
        # Verify the like was removed from metrics
        metrics_response = client.get(f"/metrics/songs/{song['_id']}")
        assert metrics_response.status_code == 200
        assert metrics_response.json()["data"]["likes"] == 0
    
    def test_check_collection_like_status_fails(self, client):
        """Test that checking like status for collections returns error."""
        # Create a collection
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        collection = client.post("/collections/", json={
            "name": "Test Album",
            "type": "album",
            "songIds": [song1["_id"]]
        }).json()["data"]
        
        # Try to check like status for collection (should fail)
        response = client.get(f"/metrics/likes/collection/{collection['id']}")
        assert response.status_code == 400
        assert "don't have direct likes" in response.json()["detail"]
        
    def test_check_like_status(self, client):
        """Test checking if a song is liked."""
        # Create liked songs playlist
        client.post("/likedSongs/")
        
        # Create a song
        song = client.post("/songs", json={"title": "Test Song", "duration": "180"}).json()["data"]
        
        # Check initial status (not liked)
        response = client.get(f"/metrics/likes/song/{song['_id']}")
        assert response.status_code == 200
        assert response.json()["liked"] is False
        
        # Like the song via liked songs
        client.post(f"/likedSongs/{song['_id']}")
        
        # Check status again (now liked)
        response = client.get(f"/metrics/likes/song/{song['_id']}")
        assert response.status_code == 200
        assert response.json()["liked"] is True
    
    # ============= SHARES =============
    
    def test_share_song(self, client):
        """Test recording a song share."""
        # Create a song
        song = client.post("/songs", json={"title": "Test Song", "duration": "180"}).json()["data"]
        
        # Share the song
        response = client.post("/metrics/shares", json={
            "targetId": song["_id"],
            "targetType": "song"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        
    def test_share_collection(self, client):
        """Test recording a collection share."""
        # Create songs and collection
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection = client.post("/collections/", json={
            "name": "Test Album",
            "type": "album",
            "songIds": [song1["_id"]]
        }).json()["data"]
        
        # Share the collection
        response = client.post("/metrics/shares", json={
            "targetId": collection["id"],
            "targetType": "collection"
        })
        
        assert response.status_code == 201
        
    def test_share_nonexistent_song(self, client):
        """Test sharing a non-existent song returns 404."""
        response = client.post("/metrics/shares", json={
            "targetId": "507f1f77bcf86cd799439011",
            "targetType": "song"
        })
        
        assert response.status_code == 404
    
    # ============= SONG METRICS =============
    
    def test_get_song_metrics(self, client):
        """Test getting metrics for a song."""
        # Create liked songs playlist
        client.post("/likedSongs/")
        
        # Create a song
        song = client.post("/songs", json={"title": "Test Song", "duration": "180"}).json()["data"]
        
        # Add some activity
        # Play the song
        client.post("/history/", json={"songId": song["_id"], "progress": 0})
        
        # Like the song via liked songs
        client.post(f"/likedSongs/{song['_id']}")
        
        # Share the song
        client.post("/metrics/shares", json={
            "targetId": song["_id"],
            "targetType": "song"
        })
        
        # Get metrics
        response = client.get(f"/metrics/songs/{song['_id']}")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "songId" in data
        assert "plays" in data
        assert "likes" in data
        assert "shares" in data
        
        # Verify counts
        assert data["plays"] >= 1
        assert data["likes"] >= 1
        assert data["shares"] >= 1
        
    def test_get_song_metrics_nonexistent(self, client):
        """Test getting metrics for non-existent song returns 404."""
        response = client.get("/metrics/songs/507f1f77bcf86cd799439011")
        assert response.status_code == 404
    
    # ============= COLLECTION METRICS =============
    
    def test_get_collection_metrics(self, client):
        """Test getting metrics for a collection."""
        # Create liked songs playlist
        client.post("/likedSongs/")
        
        # Create songs and collection
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Song 2", "duration": "200"}).json()["data"]
        song3 = client.post("/songs", json={"title": "Song 3", "duration": "150"}).json()["data"]
        
        collection = client.post("/collections/", json={
            "name": "Test Album",
            "type": "album",
            "songIds": [song1["_id"], song2["_id"], song3["_id"]]
        }).json()["data"]
        
        # Add some activity
        # Play songs from the collection
        client.post("/history/", json={"songId": song1["_id"], "progress": 0})
        client.post("/history/", json={"songId": song2["_id"], "progress": 0})
        
        # Like 2 out of 3 songs in the collection
        client.post(f"/likedSongs/{song1['_id']}")
        client.post(f"/likedSongs/{song2['_id']}")
        
        # Share the collection
        client.post("/metrics/shares", json={
            "targetId": collection["id"],
            "targetType": "collection"
        })
        
        # Get metrics
        response = client.get(f"/metrics/collections/{collection['id']}")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "collectionId" in data
        assert "totalPlays" in data
        assert "likes" in data
        assert "shares" in data
        
        # Verify counts
        assert data["totalPlays"] >= 2  # Sum of all songs' plays
        assert data["likes"] == 2  # Sum of likes from songs (2 liked out of 3)
        assert data["shares"] >= 1  # Collection shares
        
    def test_get_collection_metrics_nonexistent(self, client):
        """Test getting metrics for non-existent collection returns 404."""
        response = client.get("/metrics/collections/507f1f77bcf86cd799439011")
        assert response.status_code == 404
    
    # ============= ARTIST METRICS =============
    
    def test_get_artist_metrics(self, client):
        """Test getting overall artist metrics."""
        # Create liked songs playlist
        client.post("/likedSongs/")
        
        # Create songs and collection
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Song 2", "duration": "200"}).json()["data"]
        
        collection = client.post("/collections/", json={
            "name": "Test Album",
            "type": "album",
            "songIds": [song1["_id"], song2["_id"]]
        }).json()["data"]
        
        # Add some activity
        client.post("/history/", json={"songId": song1["_id"], "progress": 0})
        client.post("/history/", json={"songId": song2["_id"], "progress": 0})
        
        # Like song via liked songs
        client.post(f"/likedSongs/{song1['_id']}")
        
        client.post("/metrics/shares", json={
            "targetId": collection["id"],
            "targetType": "collection"
        })
        
        # Get artist metrics (using 'me' endpoint)
        response = client.get("/metrics/artists/me/overview")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "artistId" in data
        assert "monthlyListeners" in data
        assert "plays" in data
        assert "saves" in data
        assert "shares" in data
        
        # Each metric should have value, delta, and percentChange
        for metric_name in ["monthlyListeners", "plays", "saves", "shares"]:
            metric = data[metric_name]
            assert "value" in metric
            assert "delta" in metric
            assert "percentChange" in metric
            
    def test_get_artist_metrics_by_id(self, client):
        """Test getting artist metrics by artist ID."""
        # Create a song to get the artist ID
        song = client.post("/songs", json={"title": "Test Song", "duration": "180"}).json()["data"]
        artist_id = song["artistId"]
        
        # Get metrics for that artist
        response = client.get(f"/metrics/artists/{artist_id}")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["artistId"] == artist_id
        assert "monthlyListeners" in data
        assert "plays" in data
        assert "saves" in data
        assert "shares" in data
        
    def test_multiple_likes_same_user(self, client):
        """Test that the same user can toggle likes multiple times."""
        # Create liked songs playlist
        client.post("/likedSongs/")
        
        song = client.post("/songs", json={"title": "Test Song", "duration": "180"}).json()["data"]
        
        # Like
        response1 = client.post(f"/likedSongs/{song['_id']}")
        assert response1.status_code == 200
        
        # Verify like count
        metrics_response1 = client.get(f"/metrics/songs/{song['_id']}")
        assert metrics_response1.json()["data"]["likes"] == 1
        
        # Unlike
        response2 = client.delete(f"/likedSongs/{song['_id']}")
        assert response2.status_code == 200
        
        # Verify like count is 0
        metrics_response2 = client.get(f"/metrics/songs/{song['_id']}")
        assert metrics_response2.json()["data"]["likes"] == 0
        
        # Like again
        response3 = client.post(f"/likedSongs/{song['_id']}")
        assert response3.status_code == 200
        
        # Get metrics - should show only 1 like
        metrics_response3 = client.get(f"/metrics/songs/{song['_id']}")
        assert metrics_response3.json()["data"]["likes"] == 1

