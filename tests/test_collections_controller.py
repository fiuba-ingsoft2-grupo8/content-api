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

        first_returned_collection = data[0]
        second_returned_collection = data[1]

        assert first_returned_collection['name'] == second_collection['name']
        assert second_returned_collection['name'] == first_collection['name']

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
