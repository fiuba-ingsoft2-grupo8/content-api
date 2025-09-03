import pytest


@pytest.fixture
def sample_song_data():
    return {"title": "Test Song", "artist": "Test Artist"}


@pytest.fixture
def sample_playlist_data():
    return {"name": "Test Playlist", "description": "A test playlist"}


class TestSongEndpoints:

    def test_create_song_success(self, client, sample_song_data):
        response = client.post("/songs", json=sample_song_data)

        assert response.status_code == 201
        data = response.json()
        assert "data" in data
        assert data["data"]["title"] == sample_song_data["title"]
        assert data["data"]["artist"] == sample_song_data["artist"]
        assert "id" in data["data"]

    def test_create_song_validation_error(self, client):
        response = client.post("/songs")
        assert response.status_code == 400
        assert response.json()["title"] == "Bad Request"
        assert response.json()["detail"] == "Invalid request body"

        response = client.post("/songs", json={"title": "Test Song"})
        assert response.status_code == 400

        response = client.post("/songs", json={"title": 123, "artist": "Test Artist"})
        assert response.status_code == 400

    def test_get_all_songs(self, client, sample_song_data):
        client.post("/songs", json=sample_song_data)
        client.post("/songs", json={"title": "Song 2", "artist": "Artist 2"})

        response = client.get("/songs")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["title"] == sample_song_data["title"]

    def test_get_song_by_id_success(self, client, sample_song_data):
        create_response = client.post("/songs", json=sample_song_data)
        song_id = create_response.json()["data"]["id"]

        response = client.get(f"/songs/{song_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == song_id
        assert data["data"]["title"] == sample_song_data["title"]

    def test_get_song_by_id_not_found(self, client):
        response = client.get("/songs/999")

        assert response.status_code == 404
        error = response.json()
        assert error["title"] == "Not Found"
        assert error["detail"] == "Song with id 999 not found"
        assert error["instance"] == "/songs/999"

    def test_update_song_success(self, client, sample_song_data):
        create_response = client.post("/songs", json=sample_song_data)
        song_id = create_response.json()["data"]["id"]

        updated_data = {"title": "Updated Song", "artist": "Updated Artist"}
        response = client.put(f"/songs/{song_id}", json=updated_data)

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["title"] == "Updated Song"
        assert data["data"]["artist"] == "Updated Artist"

    def test_update_song_not_found(self, client, sample_song_data):
        response = client.put("/songs/999", json=sample_song_data)

        assert response.status_code == 404
        error = response.json()
        assert error["title"] == "Not Found"
        assert error["detail"] == "Song with id 999 not found"
        assert error["instance"] == "/songs/999"

    def test_update_song_validation_error(self, client, sample_song_data):
        create_response = client.post("/songs", json=sample_song_data)
        song_id = create_response.json()["data"]["id"]

        response = client.put(f"/songs/{song_id}", json={"title": 123})
        assert response.status_code == 400

    def test_delete_song_success(self, client, sample_song_data):
        create_response = client.post("/songs", json=sample_song_data)
        song_id = create_response.json()["data"]["id"]

        response = client.delete(f"/songs/{song_id}")

        assert response.status_code == 204

        get_response = client.get(f"/songs/{song_id}")
        assert get_response.status_code == 404

    def test_delete_song_not_found(self, client):
        response = client.delete("/songs/999")

        assert response.status_code == 404
        error = response.json()
        assert error["title"] == "Not Found"
        assert error["detail"] == "Song with id 999 not found"
        assert error["instance"] == "/songs/999"


class TestPlaylistEndpoints:

    def test_create_playlist_success(self, client, sample_playlist_data):
        response = client.post("/playlists", json=sample_playlist_data)

        assert response.status_code == 201
        data = response.json()
        assert "data" in data
        assert data["data"]["name"] == sample_playlist_data["name"]
        assert data["data"]["description"] == sample_playlist_data["description"]
        assert data["data"]["isPublished"] == True
        assert "id" in data["data"]
        assert "publishedAt" in data["data"]

    def test_create_playlist_validation_error(self, client):
        response = client.post("/playlists")
        assert response.status_code == 400

        response = client.post("/playlists", json={"name": "Test Playlist"})
        assert response.status_code == 400

    def test_get_all_playlists(self, client, sample_playlist_data):
        client.post("/playlists", json=sample_playlist_data)
        client.post(
            "/playlists", json={"name": "Playlist 2", "description": "Description 2"}
        )

        response = client.get("/playlists")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2

    def test_get_playlist_by_id_success(self, client, sample_playlist_data):
        create_response = client.post("/playlists", json=sample_playlist_data)
        playlist_id = create_response.json()["data"]["id"]

        response = client.get(f"/playlists/{playlist_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == playlist_id
        assert data["data"]["name"] == sample_playlist_data["name"]
        assert data["data"]["songs"] == []

    def test_get_playlist_by_id_not_found(self, client):
        response = client.get("/playlists/999")

        assert response.status_code == 404
        error = response.json()
        assert error["title"] == "Not Found"
        assert error["detail"] == "Playlist with id 999 not found"
        assert error["instance"] == "/playlists/999"

    def test_delete_playlist_success(self, client, sample_playlist_data):
        create_response = client.post("/playlists", json=sample_playlist_data)
        playlist_id = create_response.json()["data"]["id"]

        response = client.delete(f"/playlists/{playlist_id}")

        assert response.status_code == 204

        get_response = client.get(f"/playlists/{playlist_id}")
        assert get_response.status_code == 404

    def test_delete_playlist_not_found(self, client):
        response = client.delete("/playlists/999")

        assert response.status_code == 404
        error = response.json()
        assert error["title"] == "Not Found"
        assert error["detail"] == "Playlist with id 999 not found"
        assert error["instance"] == "/playlists/999"

    def test_add_song_to_playlist_success(
        self, client, sample_song_data, sample_playlist_data
    ):
        song_response = client.post("/songs", json=sample_song_data)
        song_id = song_response.json()["data"]["id"]

        playlist_response = client.post("/playlists", json=sample_playlist_data)
        playlist_id = playlist_response.json()["data"]["id"]

        response = client.post(
            f"/playlists/{playlist_id}/songs", json={"songId": song_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["songs"]) == 1
        assert data["data"]["songs"][0]["id"] == song_id
        assert data["data"]["songs"][0]["title"] == sample_song_data["title"]

    def test_add_song_to_playlist_playlist_not_found(self, client, sample_song_data):
        song_response = client.post("/songs", json=sample_song_data)
        song_id = song_response.json()["data"]["id"]

        response = client.post("/playlists/999/songs", json={"songId": song_id})

        assert response.status_code == 404
        error = response.json()
        assert error["title"] == "Not Found"
        assert error["detail"] == "Playlist with id 999 not found"
        assert error["instance"] == "/playlists/999/songs"

    def test_add_song_to_playlist_song_not_found(self, client, sample_playlist_data):
        playlist_response = client.post("/playlists", json=sample_playlist_data)
        playlist_id = playlist_response.json()["data"]["id"]

        response = client.post(f"/playlists/{playlist_id}/songs", json={"songId": 999})

        assert response.status_code == 404
        error = response.json()
        assert error["title"] == "Not Found"
        assert error["detail"] == "Song with id 999 not found"
        assert error["instance"] == f"/playlists/{playlist_id}/songs"

    def test_add_duplicate_song_to_playlist(
        self, client, sample_song_data, sample_playlist_data
    ):
        song_response = client.post("/songs", json=sample_song_data)
        song_id = song_response.json()["data"]["id"]

        playlist_response = client.post("/playlists", json=sample_playlist_data)
        playlist_id = playlist_response.json()["data"]["id"]

        client.post(f"/playlists/{playlist_id}/songs", json={"songId": song_id})

        response = client.post(
            f"/playlists/{playlist_id}/songs", json={"songId": song_id}
        )

        assert response.status_code == 400
        error = response.json()
        assert error["title"] == "Bad Request"
        assert error["detail"] == "Song is already in the playlist"
        assert error["instance"] == f"/playlists/{playlist_id}/songs"

    def test_add_song_to_playlist_validation_error(self, client, sample_playlist_data):
        playlist_response = client.post("/playlists", json=sample_playlist_data)
        playlist_id = playlist_response.json()["data"]["id"]

        response = client.post(f"/playlists/{playlist_id}/songs")
        assert response.status_code == 400

        response = client.post(
            f"/playlists/{playlist_id}/songs", json={"songId": "not-a-number"}
        )
        assert response.status_code == 400


class TestErrorHandling:

    def test_validation_error_format(self, client):
        response = client.post("/songs")

        assert response.status_code == 400
        error = response.json()
        assert "type" in error
        assert "title" in error
        assert "status" in error
        assert "detail" in error
        assert "instance" in error
        assert error["type"] == "about:blank"
        assert error["title"] == "Bad Request"
        assert error["status"] == 400

    def test_404_error_format(self, client):
        response = client.get("/songs/999")

        assert response.status_code == 404
        error = response.json()
        assert error["type"] == "about:blank"
        assert error["title"] == "Not Found"
        assert error["status"] == 404
        assert "Song with id 999 not found" in error["detail"]
        assert error["instance"] == "/songs/999"


class TestIntegration:

    def test_complete_playlist_workflow(
        self, client, sample_song_data, sample_playlist_data
    ):
        song1 = client.post("/songs", json=sample_song_data).json()["data"]
        song2 = client.post(
            "/songs", json={"title": "Song 2", "artist": "Artist 2"}
        ).json()["data"]

        playlist = client.post("/playlists", json=sample_playlist_data).json()["data"]

        client.post(f"/playlists/{playlist['id']}/songs", json={"songId": song1["id"]})
        client.post(f"/playlists/{playlist['id']}/songs", json={"songId": song2["id"]})

        response = client.get(f"/playlists/{playlist['id']}")
        data = response.json()["data"]

        assert len(data["songs"]) == 2
        song_ids = {song["id"] for song in data["songs"]}
        assert song1["id"] in song_ids
        assert song2["id"] in song_ids

        assert data["songs"][0]["id"] == song2["id"]
        assert data["songs"][1]["id"] == song1["id"]

    def test_playlist_ordering_by_published_date(self, client, sample_playlist_data):
        import time

        playlist1 = client.post("/playlists", json=sample_playlist_data).json()["data"]

        playlist2_data = {"name": "Playlist 2", "description": "Description 2"}
        playlist2 = client.post("/playlists", json=playlist2_data).json()["data"]

        response = client.get("/playlists")
        playlists = response.json()["data"]

        assert len(playlists) == 2
        assert playlists[0]["id"] == playlist2["id"]
        assert playlists[1]["id"] == playlist1["id"]
