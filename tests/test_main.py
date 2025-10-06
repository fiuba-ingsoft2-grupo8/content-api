import pytest
from bson import ObjectId
from datetime import datetime


@pytest.fixture
def sample_song_data():
    return {"title": "Test Song", "artist": "Test Artist"}


@pytest.fixture  
def sample_playlist_data():
    return {"name": "Test Playlist", "description": "A test playlist", "userId": "uu8432"}


class TestSongEndpoints:
    """Test suite for song-related API endpoints."""

    def test_create_song_success(self, client, sample_song_data):
        """Test successful creation of a new song."""
        response = client.post("/songs", json=sample_song_data)

        assert response.status_code == 201
        data = response.json()
        assert "data" in data
        assert data["data"]["title"] == sample_song_data["title"]
        assert data["data"]["artist"] == sample_song_data["artist"]
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

        response = client.post("/songs", json={"title": 123, "artist": "Test Artist"})
        assert response.status_code == 400

    def test_get_empty_song_list(self, client):
        """Should return empty song list initially."""
        response = client.get("/songs")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 0

    def test_create_song_success(self, client, sample_song_data):
        """Test successful creation of a new song."""
        response = client.post("/songs", json=sample_song_data)

        assert response.status_code == 201
        data = response.json()
        assert "data" in data
        assert data["data"]["title"] == sample_song_data["title"]
        assert data["data"]["artist"] == sample_song_data["artist"]
        assert "_id" in data["data"]
        assert ObjectId.is_valid(data["data"]["_id"])

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

        update_data = {"title": "Fortnight", "artist": "Taylor Swift ft. Post Malone"}
        response = client.put(f"/songs/{created['_id']}", json=update_data)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["title"] == "Fortnight"
        assert data["artist"] == "Taylor Swift ft. Post Malone"

    def test_delete_song(self, client, sample_song_data):
        """Should delete a song and return 404 on fetch."""
        created = client.post("/songs", json=sample_song_data).json()["data"]

        response = client.delete(f"/songs/{created['_id']}")
        assert response.status_code == 204

        check = client.get(f"/songs/{created['_id']}")
        assert check.status_code == 404

    def test_create_song_missing_title(self, client):
        """Should not create a song if title is missing."""
        response = client.post("/songs", json={"artist": "Taylor Swift"})
        assert response.status_code == 400

    def test_create_song_missing_artist(self, client):
        """Should not create a song if artist is missing."""
        response = client.post("/songs", json={"title": "Fortnight"})
        assert response.status_code == 400

    def test_get_nonexistent_song(self, client):
        """Should return 404 when song ID does not exist."""
        response = client.get("/songs/68ceb28af48aee23d3c773ea")
        assert response.status_code == 404


class TestPlaylistEndpoints:
    """Test suite for playlist-related API endpoints."""

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
        # publishedAt should be a valid date string
        assert datetime.fromisoformat(playlist["publishedAt"])

    def test_get_playlists_ordered_by_published_date(self, client):
        """Should return playlists ordered by publishedAt (desc)."""
        # Create two playlists
        playlist1 = client.post("/playlists", json={
            "name": "Folklore",
            "description": "Primera playlist!!!" * 10,
            "isPublished": True,
            "publishedAt": datetime.utcnow().isoformat(),
            "userId": "uu8432"
        }).json()["data"]

        playlist2 = client.post("/playlists", json={
            "name": "Evermore",
            "description": "Segunda playlist!!!" * 10,
            "isPublished": True,
            "publishedAt": datetime.utcnow().isoformat(),
            "userId": "uu8432"
        }).json()["data"]

        response = client.get("/playlists")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 2

        first_published = datetime.fromisoformat(data[0]["publishedAt"]).timestamp()
        second_published = datetime.fromisoformat(data[1]["publishedAt"]).timestamp()
        assert first_published > second_published

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

        response = client.get(f"/playlists/{playlist['id']}?userId=uu8432")
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["id"] == playlist["id"]
        assert data["name"] == "Piano Bar"
        assert data["songs"] == []

    def test_get_private_playlist(self, client):
        """Ensure private playlists are only accessible to their owner."""
        playlist = client.post("/playlists", json={
            "name": "Private playlist",
            "description": "description",
            "isPublished": False,
            "userId": "uu8432"
        }).json()["data"]

        response_owner = client.get(f"/playlists/{playlist['id']}?userId=uu8432")
        assert response_owner.status_code == 200
        data_owner = response_owner.json()["data"]
        assert data_owner["id"] == playlist["id"]
        assert data_owner["name"] == "Private playlist"

        response_other = client.get(f"/playlists/{playlist['id']}?userId=other8432")
        assert response_other.status_code == 404

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

        response = client.post(f"/playlists/{playlist['id']}/songs", json={"songId": song["_id"], "userId": "uu8432"})
        assert response.status_code == 200

        data = response.json()["data"]
        assert len(data["songs"]) == 1
        added = data["songs"][0]
        assert added["id"] == song["_id"]
        assert added["title"] == sample_song_data["title"]
        assert added["artist"] == sample_song_data["artist"]
        assert datetime.fromisoformat(added["addedAt"])

    def test_delete_playlist(self, client):
        """Delete a playlist and verify 404 afterwards."""
        playlist = client.post("/playlists", json={
            "name": "The Strokes",
            "description": "omg gordo mantecolero!!!" * 10,
            "isPublished": True,
            "publishedAt": datetime.utcnow().isoformat(),
            "userId": "uu8432"
        }).json()["data"]

        response = client.request(
            "DELETE",
            f"/playlists/{playlist['id']}",
            json={"userId": "uu8432"}
        )

        assert response.status_code == 204

        check = client.get(f"/playlists/{playlist['id']}?userId=uu8432")
        assert check.status_code == 404

    def test_publish_playlist(self, client):
        """Create a playlist and publish it."""
        playlist = client.post("/playlists", json={
            "name": "Folklore",
            "description": "Primera playlist!!!",
            "isPublished": False,
            "publishedAt": None,
            "userId": "uu8432"
        }).json()["data"]

        response = client.post(f"/playlists/{playlist['id']}/publish", json={"userId": "uu8432"})
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

        song1 = client.post("/songs", json={"title": "Fortnight", "artist": "Taylor Swift"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "artist": "Taylor Swift"}).json()["data"]

        client.post(f"/playlists/{playlist['id']}/songs", json={"songId": song1["_id"], "userId": "uu8432"})
        client.post(f"/playlists/{playlist['id']}/songs", json={"songId": song2["_id"], "userId": "uu8432"})

        check = client.get(f"/playlists/{playlist['id']}?userId=uu8432")
        assert check.status_code == 200
        response = client.request(
            "DELETE",
            f"/playlists/{playlist['id']}",
            json={"userId": "uu8432"}
        )
        
        assert response.status_code == 204

        check_again = client.get(f"/playlists/{playlist['id']}?userId=uu8432")
        assert check_again.status_code == 404

    def test_create_liked_songs_playlist(self, client):
        """Create a 'Liked Songs' playlist for a user."""
        response = client.post("/playlists/likedSongs", json={"userId": "uu8432"})

        assert response.status_code == 201

        data = response.json()["data"]

        assert data["name"] == "Liked Songs"
        assert data["description"] == ""
        assert data["isPublished"] is True
        assert data["userId"] == "uu8432"
        assert isinstance(data["publishedAt"], str)
        assert data["songs"] == []

        playlist_id = data["id"]
        get_response = client.get(f"/playlists/{playlist_id}?userId=uu8432")
        assert get_response.status_code == 200
        fetched = get_response.json()["data"]
        assert fetched["name"] == "Liked Songs"
        assert fetched["userId"] == "uu8432"
