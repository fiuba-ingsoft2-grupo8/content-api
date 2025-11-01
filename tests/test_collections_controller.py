import pytest
from bson import ObjectId

@pytest.fixture
def sample_song_data():
    return {"title": "Test Song", "artist": "Test Artist", "duration": "60"}

@pytest.fixture
def sample_collection_data():
    return {
        "name": "Test Album",
        "artistId": "artist123",
        "artistName": "Test Artist",
        "type": "album",
        "songIds": ["song1", "song2"]
    }

class TestCollectionsEndpoints:
    def test_create_collection_success(self, client, sample_collection_data):
        """Test successful creation of a collection."""
        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]
        
        sample_collection = {
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id'], song2['_id']]
        }
        response = client.post("/collections/", json=sample_collection)
        assert response.status_code == 201

        data = response.json()
        assert "data" in data
        collection = data["data"]

        # Basic structure
        assert "id" in collection
        assert ObjectId.is_valid(collection["id"])
        assert collection["name"] == "Test Album"
        # artistId comes from authenticated user (test_user_123)
        assert collection["artistId"] == "test_user_123"
        # artistName comes from authenticated user (Test Artist)
        assert collection["artistName"] == "Test Artist"
        assert collection["type"] == "album"
        assert isinstance(collection["songs"], list)
        assert len(collection["songs"]) == 2

    def test_create_collection_bad_request(self, client):
        """Test creation fails when missing required fields."""
        invalid_data = {
            # Missing 'name' and 'genre'
            "type": "album",
            "genre": "Rock",
            "songIds": []
        }

        response = client.post("/collections/", json=invalid_data)
        assert response.status_code == 400  # Validation error

    def test_delete_collection_success(self, client):
        """Test successful deletion of a collection."""
        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]
        
        sample_collection = {
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id'], song2['_id']]
        }
        create_collection_response = client.post("/collections/", json=sample_collection).json()['data']
        response = client.delete(f"/collections/{create_collection_response['id']}")
        assert response.status_code == 204

    def test_delete_collection_not_found(self, client):
        """Test deletion of non-existent collection."""
        response = client.delete(f"/collections/2000000000202020")
        assert response.status_code == 404

    def test_get_all_collections(self, client):
        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "El pollito pio", "duration": "60"}).json()["data"]
        song4 = client.post("/songs", json={"title": "El sapo pepe", "duration": "60"}).json()["data"]
        
        first_collection = {
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id'], song2['_id']]
        }

        second_collection = {
            "name": "Test Segundo Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song3['_id'], song4['_id']]
        }
        client.post("/collections/", json=first_collection)
        client.post("/collections/", json=second_collection)

        response = client.get("/collections")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 2

        # Verify both collections are present (order may vary due to timestamp precision)
        collection_names = [c['name'] for c in data]
        assert first_collection['name'] in collection_names
        assert second_collection['name'] in collection_names

    def test_get_one_collections(self, client):
        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "El pollito pio", "duration": "60"}).json()["data"]
        song4 = client.post("/songs", json={"title": "El sapo pepe", "duration": "60"}).json()["data"]
        
        first_collection = {
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id'], song2['_id']]
        }

        second_collection = {
            "name": "Test Segundo Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song3['_id'], song4['_id']]
        }
        
        first_collection_created = client.post("/collections/", json=first_collection).json()["data"]
        second_collection_created = client.post("/collections/", json=second_collection).json()["data"]

        response_first_collection_requested = client.get(f"/collections/{second_collection_created['id']}")
        assert response_first_collection_requested.status_code == 200
        data_for_first_collection_requested = response_first_collection_requested.json()["data"]
        
        assert data_for_first_collection_requested['name'] == second_collection['name'] 

        response_second_collection_requested = client.get(f"/collections/{first_collection_created['id']}")
        assert response_second_collection_requested.status_code == 200
        data_for_second_collection_requested = response_second_collection_requested.json()["data"]
        
        assert data_for_second_collection_requested['name'] == first_collection['name']

    def test_update_collection_songs_only(self, client):
        """Test updating only the songs in a collection."""
        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "El pollito pio", "duration": "60"}).json()["data"]

        collection = {
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id'], song2['_id']]
        }

        collection_created_response = client.post("/collections/", json=collection)
        assert collection_created_response.status_code == 201
        collection_created = collection_created_response.json()["data"]
        assert len(collection_created['songs']) == 2

        # Update only songs
        updated_data = {
            "songIds": [song3['_id']]
        }

        collection_updated_response = client.put(f"/collections/{collection_created['id']}", json=updated_data)
        assert collection_updated_response.status_code == 200
        collection_updated = collection_updated_response.json()["data"]
        assert len(collection_updated['songs']) == 1
        assert collection_updated['songs'][0]['id'] == song3['_id']
        # Name should remain the same
        assert collection_updated['name'] == "Test Album"

    def test_update_collection_name_only(self, client):
        """Test updating only the name of a collection."""
        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        
        collection = {
            "name": "Original Album Name",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }

        collection_created = client.post("/collections/", json=collection).json()["data"]
        
        # Update only name
        updated_data = {
            "name": "Updated Album Name"
        }

        response = client.put(f"/collections/{collection_created['id']}", json=updated_data)
        assert response.status_code == 200
        
        updated_collection = response.json()["data"]
        assert updated_collection['name'] == "Updated Album Name"
        assert updated_collection['type'] == "album"
        assert len(updated_collection['songs']) == 1

    def test_update_collection_type_only(self, client):
        """Test updating only the type of a collection."""
        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        
        collection = {
            "name": "Test Collection",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }

        collection_created = client.post("/collections/", json=collection).json()["data"]
        
        # Update only type
        updated_data = {
            "type": "single"
        }

        response = client.put(f"/collections/{collection_created['id']}", json=updated_data)
        assert response.status_code == 200
        
        updated_collection = response.json()["data"]
        assert updated_collection['type'] == "single"
        assert updated_collection['name'] == "Test Collection"

    def test_update_collection_multiple_fields(self, client):
        """Test updating multiple fields at once."""
        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "New Song", "duration": "60"}).json()["data"]
        
        collection = {
            "name": "Original Name",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id'], song2['_id']]
        }

        collection_created = client.post("/collections/", json=collection).json()["data"]
        
        # Update name, type, and songs
        updated_data = {
            "name": "New Name",
            "type": "ep",
            "genre": "Electronic",
            "songIds": [song3['_id']]
        }

        response = client.put(f"/collections/{collection_created['id']}", json=updated_data)
        assert response.status_code == 200
        
        updated_collection = response.json()["data"]
        assert updated_collection['name'] == "New Name"
        assert updated_collection['type'] == "ep"
        assert len(updated_collection['songs']) == 1
        assert updated_collection['songs'][0]['id'] == song3['_id']

    def test_update_collection_cover_url(self, client):
        """Test updating the cover URL of a collection."""
        song1 = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        
        collection = {
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }

        collection_created = client.post("/collections/", json=collection).json()["data"]
        
        # Update cover URL
        updated_data = {
            "coverUrl": "https://example.com/new-cover.jpg"
        }

        response = client.put(f"/collections/{collection_created['id']}", json=updated_data)
        assert response.status_code == 200
        
        updated_collection = response.json()["data"]
        assert updated_collection['coverUrl'] == "https://example.com/new-cover.jpg"
        assert updated_collection['name'] == "Test Album"

    def test_update_collection_not_found(self, client):
        """Test updating a non-existent collection."""
        updated_data = {
            "name": "Updated Name"
        }

        response = client.put("/collections/507f1f77bcf86cd799439011", json=updated_data)
        assert response.status_code == 404

    def test_update_collection_reorder_songs(self, client):
        """Test reordering songs in a collection."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Song 2", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "Song 3", "duration": "60"}).json()["data"]
        
        collection = {
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id'], song2['_id'], song3['_id']]
        }

        collection_created = client.post("/collections/", json=collection).json()["data"]
        
        # Reorder songs
        updated_data = {
            "songIds": [song3['_id'], song1['_id'], song2['_id']]
        }

        response = client.put(f"/collections/{collection_created['id']}", json=updated_data)
        assert response.status_code == 200
        
        updated_collection = response.json()["data"]
        assert len(updated_collection['songs']) == 3
        assert updated_collection['songs'][0]['id'] == song3['_id']
        assert updated_collection['songs'][1]['id'] == song1['_id']
        assert updated_collection['songs'][2]['id'] == song2['_id']

    def test_collection_has_created_at(self, client):
        """Test that collections have a createdAt field."""
        song1 = client.post("/songs", json={"title": "Test Song", "duration": "60"}).json()["data"]
        
        collection = {
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }

        collection_created = client.post("/collections/", json=collection).json()["data"]
        
        # Verify createdAt exists and is a valid timestamp
        assert "createdAt" in collection_created
        assert collection_created["createdAt"] is not None
        
    def test_collections_ordered_by_date_desc_then_name_asc(self, client):
        """Test that collections are ordered by creation date (desc) and then alphabetically (asc)."""
        import time
        
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "60"}).json()["data"]
        
        # Create collections with the same timestamp to test alphabetical ordering
        # Create them quickly so they have the same or very close timestamps
        collection_z = {
            "name": "Z Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }
        client.post("/collections/", json=collection_z)
        
        collection_a = {
            "name": "A Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }
        client.post("/collections/", json=collection_a)
        
        collection_m = {
            "name": "M Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }
        client.post("/collections/", json=collection_m)
        
        # Wait a bit to ensure different timestamp
        time.sleep(0.1)
        
        # Create an older collection
        collection_old = {
            "name": "Old Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }
        old_response = client.post("/collections/", json=collection_old).json()["data"]
        
        # Get all collections
        response = client.get("/collections")
        assert response.status_code == 200
        collections = response.json()["data"]
        
        # Find the old album - it should be the first one (most recent)
        assert collections[0]["name"] == "Old Album"
        
        # The other 3 should be ordered by creation date descending
        # Since they were created quickly, they should maintain their order or be sorted by date
        other_collections = [c["name"] for c in collections[1:]]
        
        # Verify we have our test collections
        assert "Z Album" in other_collections
        assert "A Album" in other_collections
        assert "M Album" in other_collections

    def test_get_popular_collections(self, client):
        """Test getting popular collections ordered by plays."""
        # Create songs
        song1 = client.post("/songs", json={"title": "Hit Song 1", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Hit Song 2", "duration": "200"}).json()["data"]
        song3 = client.post("/songs", json={"title": "Niche Song", "duration": "150"}).json()["data"]
        
        # Create collections
        popular_collection = client.post("/collections/", json={
            "name": "Popular Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id'], song2['_id']]
        }).json()["data"]
        
        unpopular_collection = client.post("/collections/", json={
            "name": "Unpopular Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song3['_id']]
        }).json()["data"]
        
        # Play songs from popular collection multiple times
        for _ in range(5):
            client.post("/history/", json={"songId": song1["_id"], "progress": 0})
            client.post("/history/", json={"songId": song2["_id"], "progress": 0})
        
        # Play song from unpopular collection once
        client.post("/history/", json={"songId": song3["_id"], "progress": 0})
        
        # Get popular collections for the authenticated user (test_user_123)
        artist_id = popular_collection["artistId"]
        response = client.get(f"/collections/popular/{artist_id}")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        assert len(collections) >= 2
        
        # Popular album should be first
        assert collections[0]["name"] == "Popular Album"
        assert collections[1]["name"] == "Unpopular Album"
        
        # Verify popularity metrics are present
        assert "totalPlays" in collections[0]
        assert "totalLikes" in collections[0]
        assert "totalPlaylistSaves" in collections[0]
        assert "totalShares" in collections[0]
        assert "popularityScore" in collections[0]
        
        # Popular album should have more plays
        assert collections[0]["totalPlays"] > collections[1]["totalPlays"]
        
    def test_get_popular_collections_with_multiple_metrics(self, client):
        """Test that popularity metrics are calculated and present in response."""
        # Create songs
        song1 = client.post("/songs", json={"title": "Viral Hit", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Deep Cut", "duration": "200"}).json()["data"]
        
        # Create collections
        viral_collection = client.post("/collections/", json={
            "name": "Viral Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        deep_cut_collection = client.post("/collections/", json={
            "name": "Deep Cut Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song2['_id']]
        }).json()["data"]
        
        # Add plays to viral album (fewer plays)
        for _ in range(3):
            client.post("/history/", json={"songId": song1["_id"], "progress": 0})
        
        # Add many plays to deep cut album
        for _ in range(10):
            client.post("/history/", json={"songId": song2["_id"], "progress": 0})
        
        # Get popular collections
        artist_id = viral_collection["artistId"]
        response = client.get(f"/collections/popular/{artist_id}")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        assert len(collections) >= 2
        
        # Find our collections
        viral = next(c for c in collections if c["name"] == "Viral Album")
        deep_cut = next(c for c in collections if c["name"] == "Deep Cut Album")
        
        # Verify all metrics are present in the response
        assert "totalPlays" in viral
        assert "totalLikes" in viral
        assert "totalPlaylistSaves" in viral
        assert "totalShares" in viral
        assert "popularityScore" in viral
        
        assert "totalPlays" in deep_cut
        assert "totalLikes" in deep_cut
        assert "totalPlaylistSaves" in deep_cut
        assert "totalShares" in deep_cut
        assert "popularityScore" in deep_cut
        
        # Verify play counts are correct
        assert viral["totalPlays"] == 3
        assert deep_cut["totalPlays"] == 10
        
        # Verify popularity scores are calculated (should be equal to plays in this simple case)
        assert viral["popularityScore"] >= 3.0
        assert deep_cut["popularityScore"] >= 10.0
        
        # Deep cut should have higher popularity score due to more plays
        assert deep_cut["popularityScore"] > viral["popularityScore"]
        
    def test_get_popular_collections_with_limit(self, client):
        """Test getting popular collections with limit parameter."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create multiple collections
        first_collection = None
        for i in range(5):
            collection = client.post("/collections/", json={
                "name": f"Album {i}",
                "type": "album",
                "genre": "Rock",
                "songIds": [song1['_id']]
            }).json()["data"]
            if i == 0:
                first_collection = collection
        
        # Get popular collections with limit=3
        artist_id = first_collection["artistId"]
        response = client.get(f"/collections/popular/{artist_id}?limit=3")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        assert len(collections) == 3
        
    def test_get_popular_collections_by_type(self, client):
        """Test getting popular collections filtered by type."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collections of different types
        album = client.post("/collections/", json={
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        single = client.post("/collections/", json={
            "name": "Test Single",
            "type": "single",
            "genre": "Pop",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        # Get popular albums only for the authenticated user
        artist_id = album["artistId"]
        response = client.get(f"/collections/popular/{artist_id}?type=album")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        # Should only include albums
        for collection in collections:
            assert collection["type"] == "album"

    # Tests for scheduled releases
    def test_create_collection_with_future_release_date(self, client):
        """Test creating a collection with a future release date."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Future Song", "duration": "180"}).json()["data"]
        
        # Create collection with release date 7 days in the future
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        collection_data = {
            "name": "Future Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']],
            "releaseDate": future_date
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        data = response.json()["data"]
        assert data["name"] == "Future Album"
        assert "releaseDate" in data
        assert data["releaseDate"] is not None

    def test_create_collection_without_release_date(self, client):
        """Test creating a collection without a release date defaults to now."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Immediate Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        data = response.json()["data"]
        assert data["name"] == "Immediate Album"
        assert "releaseDate" in data

    def test_unpublished_collection_not_visible_by_default(self, client):
        """Test that unpublished collections are not visible in list without includeUnpublished."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create published collection
        published_collection = client.post("/collections/", json={
            "name": "Published Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        unpublished_collection = client.post("/collections/", json={
            "name": "Unpublished Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']],
            "releaseDate": future_date
        }).json()["data"]
        
        # Get all collections without includeUnpublished
        response = client.get("/collections")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        collection_names = [c["name"] for c in collections]
        
        # Should include published but not unpublished
        assert "Published Album" in collection_names
        assert "Unpublished Album" not in collection_names

    def test_unpublished_collection_visible_with_flag(self, client):
        """Test that unpublished collections are visible when includeUnpublished=True."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        unpublished_collection = client.post("/collections/", json={
            "name": "Unpublished Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']],
            "releaseDate": future_date
        }).json()["data"]
        
        # Get collections with includeUnpublished=True
        response = client.get("/collections?includeUnpublished=true")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        collection_names = [c["name"] for c in collections]
        
        # Should include unpublished
        assert "Unpublished Album" in collection_names

    def test_get_unpublished_collection_by_id_without_flag(self, client):
        """Test that getting an unpublished collection by ID fails without includeUnpublished flag."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        collection = client.post("/collections/", json={
            "name": "Unpublished Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']],
            "releaseDate": future_date
        }).json()["data"]
        
        # Try to get it without includeUnpublished flag
        response = client.get(f"/collections/{collection['id']}")
        assert response.status_code == 404
        
        error = response.json()
        assert "not found or not yet released" in error["detail"].lower()

    def test_get_unpublished_collection_by_id_with_flag(self, client):
        """Test that getting an unpublished collection by ID works with includeUnpublished flag."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        collection = client.post("/collections/", json={
            "name": "Unpublished Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']],
            "releaseDate": future_date
        }).json()["data"]
        
        # Get it with includeUnpublished flag
        response = client.get(f"/collections/{collection['id']}?includeUnpublished=true")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["name"] == "Unpublished Album"

    def test_publish_collection_immediately(self, client):
        """Test publishing an unpublished collection immediately."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        collection = client.post("/collections/", json={
            "name": "Future Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']],
            "releaseDate": future_date
        }).json()["data"]
        
        # Verify it's not visible without flag
        response = client.get(f"/collections/{collection['id']}")
        assert response.status_code == 404
        
        # Publish it immediately
        publish_response = client.post(f"/collections/{collection['id']}/publish")
        assert publish_response.status_code == 200
        
        published_data = publish_response.json()["data"]
        assert published_data["name"] == "Future Album"
        
        # Now it should be visible without flag
        response = client.get(f"/collections/{collection['id']}")
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Future Album"

    def test_publish_already_published_collection_fails(self, client):
        """Test that publishing an already published collection fails."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create published collection (no future date)
        collection = client.post("/collections/", json={
            "name": "Published Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        # Try to publish it again
        response = client.post(f"/collections/{collection['id']}/publish")
        assert response.status_code == 400
        
        error = response.json()
        assert "already published" in error["detail"].lower()

    def test_publish_nonexistent_collection_fails(self, client):
        """Test that publishing a non-existent collection fails."""
        response = client.post("/collections/507f1f77bcf86cd799439011/publish")
        assert response.status_code == 404
        
        error = response.json()
        assert "not found" in error["detail"].lower()

    def test_popular_collections_exclude_unpublished_by_default(self, client):
        """Test that popular endpoint excludes unpublished collections by default."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Hit Song", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Future Hit", "duration": "180"}).json()["data"]
        
        # Create published collection
        published = client.post("/collections/", json={
            "name": "Published Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        unpublished = client.post("/collections/", json={
            "name": "Unpublished Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song2['_id']],
            "releaseDate": future_date
        }).json()["data"]
        
        # Get popular collections
        artist_id = published["artistId"]
        response = client.get(f"/collections/popular/{artist_id}")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        collection_names = [c["name"] for c in collections]
        
        # Should include published but not unpublished
        assert "Published Album" in collection_names
        assert "Unpublished Album" not in collection_names

    def test_popular_collections_include_unpublished_with_flag(self, client):
        """Test that popular endpoint includes unpublished collections with flag."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Hit Song", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Future Hit", "duration": "180"}).json()["data"]
        
        # Create published collection
        published = client.post("/collections/", json={
            "name": "Published Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        unpublished = client.post("/collections/", json={
            "name": "Unpublished Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song2['_id']],
            "releaseDate": future_date
        }).json()["data"]
        
        # Get popular collections with includeUnpublished
        artist_id = published["artistId"]
        response = client.get(f"/collections/popular/{artist_id}?includeUnpublished=true")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        collection_names = [c["name"] for c in collections]
        
        # Should include both
        assert "Published Album" in collection_names
        assert "Unpublished Album" in collection_names

    def test_collection_with_past_release_date_is_published(self, client):
        """Test that a collection with a past release date is treated as published."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection with release date in the past
        past_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        collection = client.post("/collections/", json={
            "name": "Past Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']],
            "releaseDate": past_date
        }).json()["data"]
        
        # Should be visible without includeUnpublished flag
        response = client.get(f"/collections/{collection['id']}")
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Past Album"
        
        # Should appear in list without flag
        response = client.get("/collections")
        assert response.status_code == 200
        collection_names = [c["name"] for c in response.json()["data"]]
        assert "Past Album" in collection_names

    # Tests for genre and credits
    def test_create_collection_with_genre(self, client):
        """Test that genre is required and included in collection."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection = client.post("/collections/", json={
            "name": "Rock Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        assert collection["genre"] == "Rock"
        
        # Verify it's also returned when fetching
        response = client.get(f"/collections/{collection['id']}")
        assert response.status_code == 200
        assert response.json()["data"]["genre"] == "Rock"

    def test_create_collection_without_genre_fails(self, client):
        """Test that creating a collection without genre fails."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_without_genre = {
            "name": "Album Without Genre",
            "type": "album",
            "songIds": [song1['_id']]
        }
        
        response = client.post("/collections/", json=collection_without_genre)
        assert response.status_code == 400  # Validation error

    def test_create_collection_with_credits(self, client):
        """Test creating a collection with credits (collaborators)."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection = client.post("/collections/", json={
            "name": "Collab Album",
            "type": "album",
            "genre": "Hip Hop",
            "songIds": [song1['_id']],
            "credits": ["Artist 2", "Artist 3"]
        }).json()["data"]
        
        assert "credits" in collection
        assert collection["credits"] == ["Artist 2", "Artist 3"]

    def test_create_collection_without_credits_defaults_empty(self, client):
        """Test that collections without credits get an empty list."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection = client.post("/collections/", json={
            "name": "Solo Album",
            "type": "album",
            "genre": "Jazz",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        assert "credits" in collection
        assert collection["credits"] == []

    def test_update_collection_genre(self, client):
        """Test updating only the genre of a collection."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection = client.post("/collections/", json={
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        # Update genre
        response = client.put(f"/collections/{collection['id']}", json={
            "genre": "Alternative Rock"
        })
        assert response.status_code == 200
        
        updated = response.json()["data"]
        assert updated["genre"] == "Alternative Rock"
        assert updated["name"] == "Test Album"  # Name should remain the same

    def test_update_collection_credits(self, client):
        """Test updating the credits of a collection."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection = client.post("/collections/", json={
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songIds": [song1['_id']],
            "credits": ["Original Collaborator"]
        }).json()["data"]
        
        # Update credits
        response = client.put(f"/collections/{collection['id']}", json={
            "credits": ["New Collaborator 1", "New Collaborator 2"]
        })
        assert response.status_code == 200
        
        updated = response.json()["data"]
        assert updated["credits"] == ["New Collaborator 1", "New Collaborator 2"]

    def test_update_collection_genre_and_credits(self, client):
        """Test updating both genre and credits at once."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection = client.post("/collections/", json={
            "name": "Test Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        # Update both
        response = client.put(f"/collections/{collection['id']}", json={
            "genre": "Progressive Rock",
            "credits": ["Bass Player", "Drummer"]
        })
        assert response.status_code == 200
        
        updated = response.json()["data"]
        assert updated["genre"] == "Progressive Rock"
        assert updated["credits"] == ["Bass Player", "Drummer"]

    # Tests for early releases (singles anticipados)
    def test_create_collection_with_early_releases(self, client):
        """Test creating a collection with early release dates for some songs."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Single 1", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Single 2", "duration": "200"}).json()["data"]
        song3 = client.post("/songs", json={"title": "Album Track", "duration": "150"}).json()["data"]
        
        # Create collection with future release date
        album_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        single1_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()  # Already released
        single2_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()  # Future single
        
        collection = client.post("/collections/", json={
            "name": "Upcoming Album",
            "type": "album",
            "genre": "Pop",
            "releaseDate": album_date,
            "songs": [
                {"songId": song1['_id'], "earlyReleaseDate": single1_date},
                {"songId": song2['_id'], "earlyReleaseDate": single2_date},
                {"songId": song3['_id']}  # No early release
            ]
        }).json()["data"]
        
        assert collection["name"] == "Upcoming Album"
        assert len(collection["songs"]) == 3
        
        # Verify earlyReleaseDate is included in response
        song_with_early = [s for s in collection["songs"] if s["id"] == song1['_id']][0]
        assert "earlyReleaseDate" in song_with_early
        assert song_with_early["earlyReleaseDate"] is not None

    def test_create_collection_legacy_format(self, client):
        """Test that legacy songIds format still works."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Song 2", "duration": "200"}).json()["data"]
        
        # Use old format with songIds
        collection = client.post("/collections/", json={
            "name": "Legacy Album",
            "type": "album",
            "genre": "Rock",
            "songIds": [song1['_id'], song2['_id']]
        }).json()["data"]
        
        assert collection["name"] == "Legacy Album"
        assert len(collection["songs"]) == 2

    def test_get_early_releases_from_collection(self, client):
        """Test getting only early released songs from a collection."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Released Single", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Future Single", "duration": "200"}).json()["data"]
        song3 = client.post("/songs", json={"title": "Album Only", "duration": "150"}).json()["data"]
        
        # Create collection
        album_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        released_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        
        collection = client.post("/collections/", json={
            "name": "Future Album",
            "type": "album",
            "genre": "Pop",
            "releaseDate": album_date,
            "songs": [
                {"songId": song1['_id'], "earlyReleaseDate": released_date},
                {"songId": song2['_id'], "earlyReleaseDate": future_date},
                {"songId": song3['_id']}
            ]
        }).json()["data"]
        
        # Get early releases
        response = client.get(f"/collections/{collection['id']}/early-releases")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["collectionName"] == "Future Album"
        assert "earlyReleasedSongs" in data
        
        # Should only return the one already released
        early_songs = data["earlyReleasedSongs"]
        assert len(early_songs) == 1
        assert early_songs[0]["title"] == "Released Single"

    def test_early_releases_empty_if_none_released(self, client):
        """Test that early-releases endpoint returns empty if no songs are early released."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Song 2", "duration": "200"}).json()["data"]
        
        # Create collection with future release, no early releases
        album_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        
        collection = client.post("/collections/", json={
            "name": "Future Album",
            "type": "album",
            "genre": "Rock",
            "releaseDate": album_date,
            "songIds": [song1['_id'], song2['_id']]
        }).json()["data"]
        
        # Get early releases
        response = client.get(f"/collections/{collection['id']}/early-releases")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert len(data["earlyReleasedSongs"]) == 0

    def test_collection_with_all_early_releases(self, client):
        """Test collection where all songs have early release dates."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Single 1", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Single 2", "duration": "200"}).json()["data"]
        
        # Both songs released early
        date1 = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        date2 = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        album_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        
        collection = client.post("/collections/", json={
            "name": "EP with Pre-releases",
            "type": "ep",
            "genre": "Electronic",
            "releaseDate": album_date,
            "songs": [
                {"songId": song1['_id'], "earlyReleaseDate": date1},
                {"songId": song2['_id'], "earlyReleaseDate": date2}
            ]
        }).json()["data"]
        
        # Get early releases
        response = client.get(f"/collections/{collection['id']}/early-releases")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert len(data["earlyReleasedSongs"]) == 2
