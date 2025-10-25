import pytest

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
        "coverUrl": "cover.png",
        "songIds": ["song1", "song2"]
    }

class TestCollectionsEndpoints:
    def test_create_collection_success(self, client, sample_collection_data):
        """Test successful creation of a collection."""
        song1 = client.post("/songs", json={"title": "Fortnight", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        
        sample_collection = {
            "name": "Test Album",
            "artistId": "artist123",
            "artistName": "Test Artist",
            "type": "album",
            "coverUrl": "cover.png",
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
        assert collection["name"] == sample_collection_data["name"]
        assert collection["artistId"] == sample_collection_data["artistId"]
        assert collection["artistName"] == sample_collection_data["artistName"]
        assert collection["type"] == sample_collection_data["type"]
        assert collection["coverUrl"] == sample_collection_data["coverUrl"]
        assert isinstance(collection["songs"], list)

    def test_create_collection_bad_request(self, client):
        """Test creation fails when missing required fields."""
        invalid_data = {
            # Missing 'name' and 'artistId'
            "artistName": "No Name",
            "type": "album",
            "coverUrl": "https://example.com/missing.jpg",
            "songIds": []
        }

        response = client.post("/collections/", json=invalid_data)
        assert response.status_code == 400

    def test_delete_collection_success(self, client):
        """Test successful deletion of a collection."""
        song1 = client.post("/songs", json={"title": "Fortnight", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        
        sample_collection = {
            "name": "Test Album",
            "artistId": "artist123",
            "artistName": "Test Artist",
            "type": "album",
            "coverUrl": "cover.png",
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
        song1 = client.post("/songs", json={"title": "Fortnight", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "El pollito pio", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song4 = client.post("/songs", json={"title": "El sapo pepe", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        
        first_collection = {
            "name": "Test Album",
            "artistId": "artist123",
            "artistName": "Test Artist",
            "type": "album",
            "coverUrl": "cover.png",
            "songIds": [song1['_id'], song2['_id']]
        }

        second_collection = {
            "name": "Test Segundo Album",
            "artistId": "artist123",
            "artistName": "Test Artist",
            "type": "album",
            "coverUrl": "cover.png",
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
        song1 = client.post("/songs", json={"title": "Fortnight", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "El pollito pio", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song4 = client.post("/songs", json={"title": "El sapo pepe", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        
        first_collection = {
            "name": "Test Album",
            "artistId": "artist123",
            "artistName": "Test Artist",
            "type": "album",
            "coverUrl": "cover.png",
            "songIds": [song1['_id'], song2['_id']]
        }

        second_collection = {
            "name": "Test Segundo Album",
            "artistId": "artist123",
            "artistName": "Test Artist",
            "type": "album",
            "coverUrl": "cover.png",
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

    def test_modify_collection(self, client):
        song1 = client.post("/songs", json={"title": "Fortnight", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "artist": "Taylor Swift", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "El pollito pio", "artist": "Taylor Swift", "duration": "60"}).json()["data"]

        collection = {
            "name": "Test Album",
            "artistId": "artist123",
            "artistName": "Test Artist",
            "type": "album",
            "coverUrl": "cover.png",
            "songIds": [song1['_id'], song2['_id']]
        }

        collection_created_response = client.post("/collections/", json=collection)
        assert collection_created_response.status_code == 201
        collection_created = collection_created_response.json()["data"]
        assert len(collection_created['songs']) == 2

        updated_songs = {
            "songIds": [song3['_id']]
        }

        collection_updated_response = client.post(f"/collections/{collection_created['id']}/modify", json=updated_songs)
        assert collection_updated_response.status_code == 200
        collection_updated = collection_updated_response.json()["data"]
        assert len(collection_updated['songs']) == 1
