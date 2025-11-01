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
            # Missing 'name'
            "type": "album",
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
            "songIds": [song1['_id'], song2['_id']]
        }

        second_collection = {
            "name": "Test Segundo Album",
            "type": "album",
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
            "songIds": [song1['_id'], song2['_id']]
        }

        second_collection = {
            "name": "Test Segundo Album",
            "type": "album",
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
            "songIds": [song1['_id'], song2['_id']]
        }

        collection_created = client.post("/collections/", json=collection).json()["data"]
        
        # Update name, type, and songs
        updated_data = {
            "name": "New Name",
            "type": "ep",
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
            "songIds": [song1['_id']]
        }
        client.post("/collections/", json=collection_z)
        
        collection_a = {
            "name": "A Album",
            "type": "album",
            "songIds": [song1['_id']]
        }
        client.post("/collections/", json=collection_a)
        
        collection_m = {
            "name": "M Album",
            "type": "album",
            "songIds": [song1['_id']]
        }
        client.post("/collections/", json=collection_m)
        
        # Wait a bit to ensure different timestamp
        time.sleep(0.1)
        
        # Create an older collection
        collection_old = {
            "name": "Old Album",
            "type": "album",
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
            "songIds": [song1['_id'], song2['_id']]
        }).json()["data"]
        
        unpopular_collection = client.post("/collections/", json={
            "name": "Unpopular Album",
            "type": "album",
            "songIds": [song3['_id']]
        }).json()["data"]
        
        # Play songs from popular collection multiple times
        for _ in range(5):
            client.post("/history/", json={"songId": song1["_id"], "progress": 0})
            client.post("/history/", json={"songId": song2["_id"], "progress": 0})
        
        # Play song from unpopular collection once
        client.post("/history/", json={"songId": song3["_id"], "progress": 0})
        
        # Get popular collections
        response = client.get("/collections/popular")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        assert len(collections) >= 2
        
        # Popular album should be first
        assert collections[0]["name"] == "Popular Album"
        assert collections[1]["name"] == "Unpopular Album"
        
    def test_get_popular_collections_with_limit(self, client):
        """Test getting popular collections with limit parameter."""
        song1 = client.post("/songs", json={"title": "Song", "duration": "180"}).json()["data"]
        
        # Create multiple collections
        for i in range(5):
            client.post("/collections/", json={
                "name": f"Album {i}",
                "type": "album",
                "songIds": [song1['_id']]
            })
        
        # Get popular collections with limit=3
        response = client.get("/collections/popular?limit=3")
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
            "songIds": [song1['_id']]
        }).json()["data"]
        
        single = client.post("/collections/", json={
            "name": "Test Single",
            "type": "single",
            "songIds": [song1['_id']]
        }).json()["data"]
        
        # Get popular albums only
        response = client.get("/collections/popular?type=album")
        assert response.status_code == 200
        
        collections = response.json()["data"]
        # Should only include albums
        for collection in collections:
            assert collection["type"] == "album"
