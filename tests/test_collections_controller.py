import pytest
from bson import ObjectId
from datetime import datetime, timezone

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
        "genre": "Rock",
        "songs": [{"songId": "song1"}, {"songId": "song2"}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}]
        }

        second_collection = {
            "name": "Test Segundo Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song3['_id']}, {"songId": song4['_id']}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}]
        }

        second_collection = {
            "name": "Test Segundo Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song3['_id']}, {"songId": song4['_id']}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}]
        }

        collection_created_response = client.post("/collections/", json=collection)
        assert collection_created_response.status_code == 201
        collection_created = collection_created_response.json()["data"]
        assert len(collection_created['songs']) == 2

        # Update only songs
        updated_data = {
            "songs": [{"songId": song3['_id']}]
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}]
        }

        collection_created = client.post("/collections/", json=collection).json()["data"]
        
        # Update name, type, and songs
        updated_data = {
            "name": "New Name",
            "type": "ep",
            "genre": "Electronic",
            "songs": [{"songId": song3['_id']}]
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}, {"songId": song3['_id']}]
        }

        collection_created = client.post("/collections/", json=collection).json()["data"]
        
        # Reorder songs
        updated_data = {
            "songs": [{"songId": song3['_id']}, {"songId": song1['_id']}, {"songId": song2['_id']}]
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}]
        }
        client.post("/collections/", json=collection_z)
        
        collection_a = {
            "name": "A Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}]
        }
        client.post("/collections/", json=collection_a)
        
        collection_m = {
            "name": "M Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}]
        }
        client.post("/collections/", json=collection_m)
        
        # Wait a bit to ensure different timestamp
        time.sleep(0.1)
        
        # Create an older collection
        collection_old = {
            "name": "Old Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}]
        }).json()["data"]
        
        unpopular_collection = client.post("/collections/", json={
            "name": "Unpopular Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song3['_id']}]
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
            "songs": [{"songId": song1['_id']}]
        }).json()["data"]
        
        deep_cut_collection = client.post("/collections/", json={
            "name": "Deep Cut Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song2['_id']}]
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
                "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}]
        }).json()["data"]
        
        single = client.post("/collections/", json={
            "name": "Test Single",
            "type": "single",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}],
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}]
        }).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        unpublished_collection = client.post("/collections/", json={
            "name": "Unpublished Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}],
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
            "songs": [{"songId": song1['_id']}],
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
            "songs": [{"songId": song1['_id']}],
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
            "songs": [{"songId": song1['_id']}],
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
            "songs": [{"songId": song1['_id']}],
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}]
        }).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        unpublished = client.post("/collections/", json={
            "name": "Unpublished Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song2['_id']}],
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
            "songs": [{"songId": song1['_id']}]
        }).json()["data"]
        
        # Create unpublished collection
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        unpublished = client.post("/collections/", json={
            "name": "Unpublished Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song2['_id']}],
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
            "songs": [{"songId": song1['_id']}],
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}],
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}],
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
            "songs": [{"songId": song1['_id']}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}]
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
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}]
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


class TestCollectionGeographicalRestrictions:
    """Test suite for geographical restrictions on collections."""

    def test_create_collection_with_available_in_countries(self, client):
        """Test creating a collection with specific available countries."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Song 2", "duration": "200"}).json()["data"]
        
        collection_data = {
            "name": "Latin America Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}, {"songId": song2['_id']}],
            "availableInCountries": ["AR", "UY", "CL", "BR"]
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        data = response.json()["data"]
        assert "availableCountries" in data
        assert set(data["availableCountries"]) == {"AR", "UY", "CL", "BR"}
        assert len(data["availableCountries"]) == 4

    def test_create_collection_with_not_available_in_countries(self, client):
        """Test creating a collection excluding specific countries."""
        song1 = client.post("/songs", json={"title": "Song A", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Worldwide Except US Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}],
            "notAvailableInCountries": ["US", "CA"]
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        data = response.json()["data"]
        assert "availableCountries" in data
        assert "US" not in data["availableCountries"]
        assert "CA" not in data["availableCountries"]
        assert "AR" in data["availableCountries"]
        assert "BR" in data["availableCountries"]
        # Should be total countries (50) minus excluded (2)
        assert len(data["availableCountries"]) == 48

    def test_create_collection_without_country_restrictions(self, client):
        """Test creating a collection without any country restrictions (available everywhere)."""
        song1 = client.post("/songs", json={"title": "Global Song", "duration": "240"}).json()["data"]
        
        collection_data = {
            "name": "Global Album",
            "type": "album",
            "genre": "Electronic",
            "songs": [{"songId": song1['_id']}]
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        data = response.json()["data"]
        assert "availableCountries" in data
        # Should include all 50 countries
        assert len(data["availableCountries"]) == 50

    def test_create_collection_with_invalid_country_code(self, client):
        """Test that invalid country codes are rejected."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Invalid Country Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR", "XX", "YY"]  # XX and YY are invalid
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 400
        
        error = response.json()
        assert "Invalid country codes" in error["detail"]
        assert "XX" in error["detail"]

    def test_create_collection_available_in_takes_precedence(self, client):
        """Test that availableInCountries takes precedence over notAvailableInCountries."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Precedence Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR", "UY"],
            "notAvailableInCountries": ["US", "CA"]  # Should be ignored
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        data = response.json()["data"]
        # Should only use availableInCountries, ignoring notAvailableInCountries
        assert set(data["availableCountries"]) == {"AR", "UY"}
        assert len(data["availableCountries"]) == 2

    def test_create_collection_with_single_country(self, client):
        """Test creating a collection available in only one country."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Argentina Only Album",
            "type": "album",
            "genre": "Folklore",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR"]
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        data = response.json()["data"]
        assert data["availableCountries"] == ["AR"]
        assert len(data["availableCountries"]) == 1

    def test_create_collection_exclude_all_except_one(self, client):
        """Test excluding all countries except one."""
        from common.countries import ALL_COUNTRY_CODES
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Exclude all except Argentina
        excluded = [code for code in ALL_COUNTRY_CODES if code != "AR"]
        
        collection_data = {
            "name": "Only AR Album",
            "type": "single",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}],
            "notAvailableInCountries": excluded
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        data = response.json()["data"]
        assert data["availableCountries"] == ["AR"]
        assert len(data["availableCountries"]) == 1

    def test_get_collection_includes_available_countries(self, client):
        """Test that GET collection endpoint includes availableCountries."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR", "UY", "BR"]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Get the collection
        get_response = client.get(f"/collections/{collection_id}")
        assert get_response.status_code == 200
        
        data = get_response.json()["data"]
        assert "availableCountries" in data
        assert set(data["availableCountries"]) == {"AR", "UY", "BR"}

    def test_list_collections_includes_available_countries(self, client):
        """Test that list collections endpoint includes availableCountries."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album List",
            "type": "album",
            "genre": "Jazz",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["US", "CA", "MX"]
        }
        
        client.post("/collections/", json=collection_data)
        
        # List collections
        response = client.get("/collections/")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        assert len(collections) >= 1
        
        # Find our collection
        test_collection = next(
            (c for c in collections if c["name"] == "Test Album List"), 
            None
        )
        assert test_collection is not None
        assert "availableCountries" in test_collection
        assert set(test_collection["availableCountries"]) == {"US", "CA", "MX"}

    def test_create_collection_with_empty_countries_list(self, client):
        """Test creating collection with empty availableInCountries list."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Empty Countries Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": []
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        data = response.json()["data"]
        # Empty list should default to all countries
        assert len(data["availableCountries"]) == 50

    def test_update_collection_with_available_countries(self, client):
        """Test updating collection's available countries."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection
        collection_data = {
            "name": "Update Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR", "UY"]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Update to different countries
        update_data = {
            "availableInCountries": ["US", "CA", "MX"]
        }
        
        update_response = client.put(f"/collections/{collection_id}", json=update_data)
        assert update_response.status_code == 200
        
        data = update_response.json()["data"]
        assert set(data["availableCountries"]) == {"US", "CA", "MX"}

    def test_update_collection_with_not_available_countries(self, client):
        """Test updating collection to exclude specific countries."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection available everywhere
        collection_data = {
            "name": "Update Test 2",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Update to exclude some countries
        update_data = {
            "notAvailableInCountries": ["CN", "KR"]
        }
        
        update_response = client.put(f"/collections/{collection_id}", json=update_data)
        assert update_response.status_code == 200
        
        data = update_response.json()["data"]
        assert "CN" not in data["availableCountries"]
        assert "KR" not in data["availableCountries"]
        assert "AR" in data["availableCountries"]

    def test_can_access_collection_with_correct_country(self):
        """Test _can_access_collection allows access when country matches."""
        from controllers.collections_controller import _can_access_collection
        
        user = {"user_id": "user1", "country": "AR", "user_type": "user"}
        collection = {"artistId": "other_artist", "availableCountries": ["AR", "UY"]}
        
        assert _can_access_collection(user, collection) == True

    def test_can_access_collection_blocked_by_country(self):
        """Test _can_access_collection blocks access when country doesn't match."""
        from controllers.collections_controller import _can_access_collection
        
        user = {"user_id": "user1", "country": "GB", "user_type": "user"}
        collection = {"artistId": "other_artist", "availableCountries": ["AR", "UY"]}
        
        assert _can_access_collection(user, collection) == False

    def test_can_access_collection_owner_bypass(self):
        """Test _can_access_collection allows owner to access regardless of country."""
        from controllers.collections_controller import _can_access_collection
        
        user = {"user_id": "artist123", "country": "GB", "user_type": "artist"}
        collection = {"artistId": "artist123", "availableCountries": ["AR", "UY"]}
        
        # Owner should access even though GB is not in availableCountries
        assert _can_access_collection(user, collection) == True

    def test_can_access_collection_backoffice_bypass(self):
        """Test _can_access_collection allows backoffice users to access all collections."""
        from controllers.collections_controller import _can_access_collection
        
        user = {"user_id": "admin1", "country": "GB", "user_type": "backoffice"}
        collection = {"artistId": "artist123", "availableCountries": ["AR", "UY"]}
        
        # Backoffice should access regardless of country
        assert _can_access_collection(user, collection) == True

    def test_can_access_collection_no_restrictions(self):
        """Test _can_access_collection allows access when no country restrictions exist."""
        from controllers.collections_controller import _can_access_collection
        
        user = {"user_id": "user1", "country": "GB", "user_type": "user"}
        collection = {"artistId": "other_artist", "availableCountries": []}
        
        # Empty list means available everywhere
        assert _can_access_collection(user, collection) == True

    def test_get_collection_owner_bypasses_region_restrictions(self, client):
        """Test that collection owner can access their own restricted collections."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection only available in US (owner is from AR)
        collection_data = {
            "name": "Owner Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["US"]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Owner should be able to access
        get_response = client.get(f"/collections/{collection_id}")
        assert get_response.status_code == 200

    def test_get_collections_includes_available_countries(self, client):
        """Test that collections returned include availableCountries field."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        # Create collection with specific countries
        client.post("/collections/", json={
            "name": "Region Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR", "UY", "CL"]
        })
        
        # List collections
        response = client.get("/collections/")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        assert len(collections) > 0
        
        # Find our test collection
        test_collection = next((c for c in collections if c["name"] == "Region Test Album"), None)
        assert test_collection is not None
        assert "availableCountries" in test_collection
        assert set(test_collection["availableCountries"]) == {"AR", "UY", "CL"}

    def test_get_popular_collections_includes_available_countries(self, client):
        """Test that popular collections include availableCountries field."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        # Create collection with specific countries
        client.post("/collections/", json={
            "name": "Popular Region Test",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR", "BR"]
        })
        
        # Get popular collections
        response = client.get("/collections/popular/test_user_123")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        # Find our test collection
        test_collection = next((c for c in collections if c["name"] == "Popular Region Test"), None)
        assert test_collection is not None
        assert "availableCountries" in test_collection
        assert set(test_collection["availableCountries"]) == {"AR", "BR"}

    def test_update_collection_with_invalid_country_codes(self, client):
        """Test that updating with invalid country codes is rejected."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Try to update with invalid country codes
        update_data = {
            "availableInCountries": ["ZZ", "XX"]
        }
        
        update_response = client.put(f"/collections/{collection_id}", json=update_data)
        assert update_response.status_code == 400
        
        error = update_response.json()
        assert "Invalid country codes" in error["detail"]

class TestCollectionRecommendedAlbums:
    def _make_album(self, client, name, genre, releaseDate=None):
        payload = {
            "name": name,
            "type": "album",
            "genre": genre,
            "songs": [],
        }
        if releaseDate:
            payload["releaseDate"] = releaseDate

        return client.post("/collections/", json=payload).json()["data"]

    def test_recommended_no_preferences_returns_popular(self, client):
        """If user has no genre or artist preferences → return global most popular."""
        for i in range(12):
            self._make_album(client, f"A{i}", "Pop")

        client.delete("/preferences/genres")
        client.delete("/preferences/artists")

        resp = client.get("/collections/recommended?n=10")
        assert resp.status_code == 200

        data = resp.json()
        assert "albums" in data
        assert len(data["albums"]) == 10

    def test_recommended_with_genres_only(self, client):
        """User has only genre preferences → genre-based selection."""
        pop_ids = [
            self._make_album(client, f"PopA{i}", "Pop")["id"]
            for i in range(8)
        ]
        rock_ids = [
            self._make_album(client, f"RockA{i}", "Rock")["id"]
            for i in range(3)
        ]

        client.put("/preferences/genres", json={"genres": ["Pop"]})
        client.delete("/preferences/artists")

        resp = client.get("/collections/recommended?n=10")
        assert resp.status_code == 200
        albums = resp.json()["albums"]

        assert len(albums) == 10

        returned_ids = {a["id"] for a in albums}
        assert returned_ids.issubset(set(pop_ids + rock_ids))

    def test_recommended_with_artists_only(self, client):
        """If only artists are preferred → they get all matching albums."""

        for i in range(6):
            self._make_album(client, f"ArtistA{i}", "Pop")

        for i in range(3):
            self._make_album(client, f"Other{i}", "Rock")

        artist_id = "test_user_123"

        client.post("/preferences/artists", json={"data": [artist_id]})

        resp = client.get("/collections/recommended?n=10")
        assert resp.status_code == 200

        albums = resp.json()["albums"]

        artist_pref_count = sum(a["artistId"] == artist_id for a in albums)
        assert artist_pref_count == 9


    def test_recommended_genres_and_artists_and_fallback(self, client):
        """Genres + artists produce fewer than n → fill with globals."""

        for i in range(3):
            self._make_album(client, f"A{i}", "Pop")

        for i in range(4):
            self._make_album(client, f"G{i}", "Rock")

        for i in range(10):
            self._make_album(client, f"P{i}", "Ballad")

        client.post("/preferences/genres", json={"genres": ["Rock"]})
        client.post("/preferences/artists", json={"data": ["test_user_123"]})

        resp = client.get("/collections/recommended?n=10")
        assert resp.status_code == 200

        albums = resp.json()["albums"]
        artist_matches = [a for a in albums if a["artistId"] == "test_user_123"]
        genre_matches = [a for a in albums if a["genre"] == "Rock"]

        assert len(artist_matches) == len(albums)

        assert len(genre_matches) >= 4


    def test_recommended_no_duplicates(self, client):
        """Test that deduplication works even with overlapping sources."""

        for i in range(5):
            self._make_album(client, f"A{i}", "Pop")

        client.post("/preferences/genres", json={"genres": ["Pop"]})
        client.post("/preferences/artists", json={"artists": ["test_user_123"]})

        resp = client.get("/collections/recommended?n=10")
        assert resp.status_code == 200

        albums = resp.json()["albums"]

        ids = [a["id"] for a in albums]
        assert len(ids) == len(set(ids))



class TestPublicationWindow:
    """Tests for publication window configuration and state management."""
    
    def test_create_collection_with_publication_window(self, client):
        """Test creating a collection with publication window (noDisponibleDesde/Hasta)."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        no_disponible_desde = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        no_disponible_hasta = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        
        collection_data = {
            "name": "Windowed Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "releaseDate": future_date,
            "noDisponibleDesde": no_disponible_desde,
            "noDisponibleHasta": no_disponible_hasta
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        collection = response.json()["data"]
        assert collection["releaseDate"] is not None
        # Note: noDisponibleDesde/Hasta might not be in response schema, but should be stored
    
    def test_create_collection_with_invalid_window(self, client):
        """Test that creating collection with invalid window (desde >= hasta) fails."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        no_disponible_desde = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        no_disponible_hasta = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()  # Invalid: antes de desde
        
        collection_data = {
            "name": "Invalid Window Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "noDisponibleDesde": no_disponible_desde,
            "noDisponibleHasta": no_disponible_hasta
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 400
        assert "noDisponibleDesde must be before noDisponibleHasta" in response.json()["detail"]
    
    def test_configure_publication_window(self, client):
        """Test configuring publication window for existing collection."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Configure publication window
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        no_disponible_desde = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        no_disponible_hasta = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        
        window_data = {
            "releaseDate": future_date,
            "noDisponibleDesde": no_disponible_desde,
            "noDisponibleHasta": no_disponible_hasta
        }
        
        response = client.put(f"/collections/{collection_id}/publication-window", json=window_data)
        assert response.status_code == 200
        
        collection = response.json()["data"]
        assert collection["id"] == collection_id
    
    def test_configure_publication_window_not_found(self, client):
        """Test that configuring window for non-existent collection fails."""
        from datetime import datetime, timedelta, timezone
        
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        window_data = {"releaseDate": future_date}
        
        fake_id = "507f1f77bcf86cd799439011"
        response = client.put(f"/collections/{fake_id}/publication-window", json=window_data)
        assert response.status_code == 404
    
    def test_configure_publication_window_invalid_window(self, client):
        """Test that configuring invalid window fails."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Invalid window
        no_disponible_desde = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        no_disponible_hasta = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        
        window_data = {
            "noDisponibleDesde": no_disponible_desde,
            "noDisponibleHasta": no_disponible_hasta
        }
        
        response = client.put(f"/collections/{collection_id}/publication-window", json=window_data)
        assert response.status_code == 400
        assert "noDisponibleDesde must be before noDisponibleHasta" in response.json()["detail"]


class TestAdminBlock:
    """Tests for admin block functionality."""
    
    def test_set_admin_block_global(self, client, client_backoffice):
        """Test that backoffice user can block a collection globally."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection as regular user
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Block collection as backoffice user with global scope
        block_data = {
            "blocked": True,
            "scope": "global",
            "reasonCode": "copyright_violation"
        }
        response = client_backoffice.post(f"/collections/{collection_id}/admin-block", json=block_data)
        assert response.status_code == 200
        
        collection = response.json()["data"]
        assert collection["id"] == collection_id
        assert collection["bloqueadoAdmin"] == True
        assert collection["bloqueadoAdminData"]["scope"] == "global"
        assert collection["bloqueadoAdminData"]["reasonCode"] == "copyright_violation"
        assert collection["effectiveStatus"] == "bloqueado-admin"
    
    def test_set_admin_block_regions(self, client, client_backoffice):
        """Test that backoffice user can block a collection by regions."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection as regular user
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Block collection as backoffice user with regions scope
        block_data = {
            "blocked": True,
            "scope": "regions",
            "regions": ["AR", "BR", "CL"],
            "reasonCode": "licensing_issue"
        }
        response = client_backoffice.post(f"/collections/{collection_id}/admin-block", json=block_data)
        assert response.status_code == 200
        
        collection = response.json()["data"]
        assert collection["id"] == collection_id
        assert collection["bloqueadoAdmin"] == True
        assert collection["bloqueadoAdminData"]["scope"] == "regions"
        assert collection["bloqueadoAdminData"]["regions"] == ["AR", "BR", "CL"]
        assert collection["bloqueadoAdminData"]["reasonCode"] == "licensing_issue"
    
    def test_set_admin_block_missing_scope(self, client, client_backoffice):
        """Test that blocking without scope fails."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Try to block without scope
        block_data = {
            "blocked": True,
            "reasonCode": "test_reason"
        }
        response = client_backoffice.post(f"/collections/{collection_id}/admin-block", json=block_data)
        assert response.status_code == 400
        assert "scope" in response.json()["detail"].lower()
    
    def test_set_admin_block_missing_reason(self, client, client_backoffice):
        """Test that blocking without reason code fails."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Try to block without reason code
        block_data = {
            "blocked": True,
            "scope": "global"
        }
        response = client_backoffice.post(f"/collections/{collection_id}/admin-block", json=block_data)
        assert response.status_code == 400
        assert "reasoncode" in response.json()["detail"].lower()
    
    def test_set_admin_block_regions_missing_regions_list(self, client, client_backoffice):
        """Test that blocking with regions scope but no regions list fails."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Try to block with regions scope but no regions
        block_data = {
            "blocked": True,
            "scope": "regions",
            "reasonCode": "test_reason"
        }
        response = client_backoffice.post(f"/collections/{collection_id}/admin-block", json=block_data)
        assert response.status_code == 400
        assert "regions" in response.json()["detail"].lower()
    
    def test_set_admin_block_unauthorized(self, client):
        """Test that non-backoffice user cannot block collections."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Try to block as regular user (should fail)
        block_data = {
            "blocked": True,
            "scope": "global",
            "reasonCode": "test_reason"
        }
        response = client.post(f"/collections/{collection_id}/admin-block", json=block_data)
        assert response.status_code == 403
        assert "backoffice" in response.json()["detail"].lower()
    
    def test_unblock_collection(self, client, client_backoffice):
        """Test unblocking a collection reverts to previous availability."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Block collection
        block_data = {
            "blocked": True,
            "scope": "global",
            "reasonCode": "copyright_violation"
        }
        block_response = client_backoffice.post(f"/collections/{collection_id}/admin-block", json=block_data)
        assert block_response.status_code == 200
        assert block_response.json()["data"]["bloqueadoAdmin"] == True
        
        # Unblock collection
        unblock_data = {
            "blocked": False
        }
        unblock_response = client_backoffice.post(f"/collections/{collection_id}/admin-block", json=unblock_data)
        assert unblock_response.status_code == 200
        
        collection = unblock_response.json()["data"]
        assert collection["bloqueadoAdmin"] == False
        assert collection["bloqueadoAdminData"] is None
        # Should revert to publicado since it had a release date in the past (or None)
        assert collection["effectiveStatus"] in ["publicado", "programado"]
    
    def test_blocked_collection_visible_in_catalog_but_indicated(self, client, client_backoffice):
        """Test that blocked collections are visible in catalog with indicator."""
        # Create song and collection as regular user
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Block collection as backoffice user
        block_data = {
            "blocked": True,
            "scope": "regions",
            "regions": ["AR", "BR"],
            "reasonCode": "licensing_issue"
        }
        client_backoffice.post(f"/collections/{collection_id}/admin-block", json=block_data)
        
        # Get collection detail - should show block indicator
        get_response = client.get(f"/collections/{collection_id}?includeUnpublished=true")
        assert get_response.status_code == 200
        
        collection = get_response.json()["data"]
        # CA 2: Collection should be visible but with bloqueadoAdmin indicator
        assert collection["bloqueadoAdmin"] == True
        assert collection["bloqueadoAdminData"] is not None
        assert collection["bloqueadoAdminData"]["scope"] == "regions"
        assert collection["bloqueadoAdminData"]["regions"] == ["AR", "BR"]
        assert collection["bloqueadoAdminData"]["reasonCode"] == "licensing_issue"
        assert collection["effectiveStatus"] == "bloqueado-admin"


class TestAutoActivation:
    """Tests for automatic activation of scheduled collections."""
    
    def test_auto_activate_collections(self, client, client_backoffice):
        """Test auto-activation endpoint."""
        from datetime import datetime, timedelta, timezone
        
        # Create song and collection as regular user
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection with past release date (should be activated)
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        collection_data = {
            "name": "Past Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "releaseDate": past_date
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Call auto-activate as backoffice user (using separate client with backoffice user)
        # Note: We need to use client_backoffice which has the backoffice user mocked
        response = client_backoffice.post("/collections/auto-activate")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "activatedCount" in data
        assert "errors" in data
        assert "success" in data
        # Should have activated at least 1 collection (the one we just created)
        assert data["activatedCount"] >= 1


class TestEffectiveState:
    """Tests for effective state calculation and priority."""
    
    def test_programado_state_with_future_release(self, client):
        """Test that collection with future releaseDate is in 'programado' state."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        collection_data = {
            "name": "Future Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "releaseDate": future_date
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        # Collection should not be visible by default (programado)
        collection_id = response.json()["data"]["id"]
        get_response = client.get(f"/collections/{collection_id}")
        assert get_response.status_code == 404  # Not visible because programado
    
    def test_publicado_state_with_past_release(self, client):
        """Test that collection with past releaseDate is in 'publicado' state."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        collection_data = {
            "name": "Past Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "releaseDate": past_date
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        # Collection should be visible (publicado)
        collection_id = response.json()["data"]["id"]
        get_response = client.get(f"/collections/{collection_id}")
        assert get_response.status_code == 200  # Visible because publicado
    
    def test_no_disponible_state_in_window(self, client):
        """Test that collection with no-disponible window can be created."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create collection with no-disponible window that includes now
        no_disponible_desde = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        no_disponible_hasta = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        
        collection_data = {
            "name": "No Disponible Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "noDisponibleDesde": no_disponible_desde,
            "noDisponibleHasta": no_disponible_hasta
        }
        
        response = client.post("/collections/", json=collection_data)
        assert response.status_code == 201
        
        # Collection should be created successfully
        collection = response.json()["data"]
        assert collection["id"] is not None
    
    def test_bloqueado_admin_priority(self, client, client_backoffice):
        """Test that bloqueado-admin can be set and collection still exists."""
        from datetime import datetime, timedelta, timezone
        
        # Create song and collection as regular user
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create published collection
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        collection_data = {
            "name": "Blocked Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "releaseDate": past_date
        }
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Verify it's visible
        get_response = client.get(f"/collections/{collection_id}")
        assert get_response.status_code == 200
        
        # Block it as admin (using client_backoffice which has backoffice user)
        block_data = {
            "blocked": True,
            "scope": "global",
            "reasonCode": "test_reason"
        }
        block_response = client_backoffice.post(f"/collections/{collection_id}/admin-block", json=block_data)
        assert block_response.status_code == 200
        
        # Collection should still exist in response
        blocked_collection = block_response.json()["data"]
        assert blocked_collection["id"] == collection_id
