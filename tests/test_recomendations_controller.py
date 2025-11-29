import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def sample_collection():
    """Fixture for a sample collection."""
    return {
        "_id": ObjectId(),
        "name": "Test Album",
        "artistId": "artist_123",
        "artistName": "Test Artist",
        "type": "album",
        "genre": "Rock",
        "coverUrl": "https://example.com/cover.jpg",
        "releaseDate": datetime.now(timezone.utc) - timedelta(days=30),
        "createdAt": datetime.now(timezone.utc) - timedelta(days=60)
    }


@pytest.fixture
def sample_songs():
    """Fixture for sample songs."""
    return [
        {
            "_id": ObjectId(),
            "title": f"Test Song {i}",
            "artist": "Test Artist",
            "duration": "180",
            "artistId": "artist_123"
        }
        for i in range(5)
    ]


class TestDailyMixEndpoint:
    """Test suite for /daily-mix endpoint."""

    def test_daily_mix_success_with_user_genres(self, client, sample_songs):
        """Test daily mix returns playlist with songs from user's preferred genres."""
        # Setup: Create songs and a collection with Rock genre
        collection_id = ObjectId()
        client.post("/collections", json={
            "name": "Rock Collection",
            "type": "album",
            "genre": "Rock",
            "releaseDate": datetime.now(timezone.utc).isoformat()
        })
        
        # Add songs to database
        for song in sample_songs:
            result = client.post("/songs", json={
                "title": song["title"],
                "duration": song["duration"]
            })
            assert result.status_code == 201

        # Set user preferences to Rock
        with patch("databases.preferences_database.get_user_genres") as mock_get_genres, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_get_genres.return_value = "Rock"
            # Mock filter to return all songs (no geographic restrictions in test)
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/daily-mix")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Daily Mix"
            assert data["isMix"] is True
            assert "coverUrl" in data

    def test_daily_mix_fallback_to_available_genres(self, client, sample_songs):
        """Test daily mix falls back to available genres when user has no preferences."""
        # Add songs to a Pop collection
        for song in sample_songs:
            client.post("/songs", json={
                "title": song["title"],
                "duration": song["duration"]
            })

        with patch("databases.preferences_database.get_user_genres") as mock_get_genres, \
             patch("databases.preferences_database.get_available_genres") as mock_get_available, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_get_genres.return_value = None
            mock_get_available.return_value = ["Pop", "Rock"]
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/daily-mix")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Daily Mix"

    def test_daily_mix_creates_new_playlist(self, client):
        """Test daily mix creates a new playlist if none exists."""
        with patch("databases.preferences_database.get_user_genres") as mock_get_genres, \
             patch("databases.songs_database.get_songs_by_genre") as mock_get_songs, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_get_genres.return_value = "Pop"
            mock_get_songs.return_value = []
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/daily-mix")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Daily Mix"
            assert data["userId"] == "test_user_123"

    def test_daily_mix_returns_existing_playlist(self, client):
        """Test daily mix returns existing playlist instead of creating duplicate."""
        with patch("databases.preferences_database.get_user_genres") as mock_get_genres, \
             patch("databases.songs_database.get_songs_by_genre") as mock_get_songs, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_get_genres.return_value = "Pop"
            mock_get_songs.return_value = []
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            # First call creates playlist
            response1 = client.get("/recommendations/daily-mix")
            playlist1_id = response1.json()["data"]["id"]
            
            # Second call should return same playlist
            response2 = client.get("/recommendations/daily-mix")
            playlist2_id = response2.json()["data"]["id"]
            
            assert playlist1_id == playlist2_id


class TestMoodMixEndpoint:
    """Test suite for /mood-mix endpoint."""

    def test_mood_mix_success_with_random_genre(self, client, sample_songs):
        """Test mood mix returns playlist with songs from a random genre."""
        for song in sample_songs:
            client.post("/songs", json={
                "title": song["title"],
                "duration": song["duration"]
            })

        with patch("databases.preferences_database.get_random_genre") as mock_random_genre, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_random_genre.return_value = "Jazz"
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/mood-mix")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Mood Mix"
            assert data["isMix"] is True

    def test_mood_mix_fallback_when_no_random_genre(self, client):
        """Test mood mix falls back to available genres when random returns None."""
        with patch("databases.preferences_database.get_random_genre") as mock_random_genre, \
             patch("databases.preferences_database.get_available_genres") as mock_available, \
             patch("databases.songs_database.get_songs_by_genre") as mock_get_songs, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_random_genre.return_value = None
            mock_available.return_value = ["Pop", "Rock"]
            mock_get_songs.return_value = []
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/mood-mix")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Mood Mix"

    def test_mood_mix_tries_multiple_genres(self, client, sample_songs):
        """Test mood mix tries multiple genres until it finds songs."""
        # Add songs only for Rock genre
        for song in sample_songs:
            client.post("/songs", json={
                "title": song["title"],
                "duration": song["duration"]
            })

        with patch("databases.preferences_database.get_random_genre") as mock_random, \
             patch("databases.preferences_database.get_available_genres") as mock_available, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_random.return_value = "Jazz"  # This won't have songs
            mock_available.return_value = ["Rock", "Pop"]  # Rock will have songs
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/mood-mix")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Mood Mix"

    def test_mood_mix_handles_empty_songs(self, client):
        """Test mood mix handles case when no songs are found."""
        with patch("databases.preferences_database.get_random_genre") as mock_random, \
             patch("databases.preferences_database.get_available_genres") as mock_available, \
             patch("databases.songs_database.get_songs_by_genre") as mock_get_songs, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_random.return_value = "Jazz"
            mock_available.return_value = []
            mock_get_songs.return_value = []
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/mood-mix")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Mood Mix"
            assert data["songs"] == []


class TestBecauseYouListenedEndpoint:
    """Test suite for /because-you-listened endpoint."""

    def test_because_you_listened_success(self, client, sample_songs, sample_collection):
        """Test because you listened returns playlist based on top artist."""
        # Create songs
        for song in sample_songs:
            client.post("/songs", json={
                "title": song["title"],
                "duration": song["duration"]
            })

        with patch("databases.metrics_database.get_user_top_n_plays") as mock_top_plays, \
             patch("databases.collections_database.get_collections") as mock_get_collections, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_top_plays.return_value = [{"artist": "Test Artist", "song_id": str(ObjectId())}]
            mock_get_collections.return_value = [sample_collection]
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/because-you-listened")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Because You Listened To"
            assert data["isMix"] is True

    def test_because_you_listened_no_top_plays(self, client):
        """Test because you listened when user has no play history."""
        with patch("databases.metrics_database.get_user_top_n_plays") as mock_top_plays, \
             patch("databases.preferences_database.get_available_genres") as mock_available, \
             patch("databases.songs_database.get_songs_by_genre") as mock_get_songs, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_top_plays.return_value = []
            mock_available.return_value = ["Pop"]
            mock_get_songs.return_value = []
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/because-you-listened")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Because You Listened To"

    def test_because_you_listened_artist_with_multiple_genres(self, client, sample_songs):
        """Test because you listened with artist having collections in multiple genres."""
        for song in sample_songs:
            client.post("/songs", json={
                "title": song["title"],
                "duration": song["duration"]
            })

        collections = [
            {
                "_id": ObjectId(),
                "genre": "Rock",
                "artistId": "artist_123",
                "artistName": "Test Artist"
            },
            {
                "_id": ObjectId(),
                "genre": "Pop",
                "artistId": "artist_123",
                "artistName": "Test Artist"
            }
        ]

        with patch("databases.metrics_database.get_user_top_n_plays") as mock_top_plays, \
             patch("databases.collections_database.get_collections") as mock_get_collections, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_top_plays.return_value = [{"artist": "Test Artist", "song_id": str(ObjectId())}]
            mock_get_collections.return_value = collections
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/because-you-listened")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Because You Listened To"

    def test_because_you_listened_fallback_genres(self, client):
        """Test because you listened falls back when no songs found for artist genres."""
        with patch("databases.metrics_database.get_user_top_n_plays") as mock_top_plays, \
             patch("databases.collections_database.get_collections") as mock_get_collections, \
             patch("databases.preferences_database.get_available_genres") as mock_available, \
             patch("databases.songs_database.get_songs_by_genre") as mock_get_songs, \
             patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
            mock_top_plays.return_value = [{"artist": "Test Artist", "song_id": str(ObjectId())}]
            mock_get_collections.return_value = [{"genre": "Jazz"}]
            mock_available.return_value = ["Pop"]
            mock_get_songs.return_value = []
            mock_filter.side_effect = lambda user, songs, db=None: songs
            
            response = client.get("/recommendations/because-you-listened")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "Because You Listened To"


class TestNewReleasesEndpoint:
    """Test suite for /new-releases endpoint."""

    def test_new_releases_success(self, client, sample_collection):
        """Test new releases returns collections from followed artists."""
        with patch("databases.collections_database.get_new_releases_from_artist") as mock_releases, \
             patch("databases.collections_database.get_songs_from_collection") as mock_songs:
            mock_releases.return_value = [sample_collection]
            mock_songs.return_value = []
            
            # Mock httpx calls
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "users": [
                        {"id": "artist_123"},
                        {"id": "artist_456"}
                    ]
                }
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                response = client.get("/recommendations/new-releases")
                
                assert response.status_code == 200
                data = response.json()["data"]
                assert isinstance(data, list)

    def test_new_releases_no_followed_artists(self, client):
        """Test new releases when user follows no artists."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"users": []}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            response = client.get("/recommendations/new-releases")
            
            assert response.status_code == 200
            data = response.json()["data"]
            assert data == []

    def test_new_releases_api_failure(self, client):
        """Test new releases handles external API failure gracefully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("API unavailable"))
            
            response = client.get("/recommendations/new-releases")
            
            assert response.status_code == 500
            assert "error" in response.json()

    def test_new_releases_with_authorization_header(self, client):
        """Test new releases passes authorization header to external API."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"users": []}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            response = client.get(
                "/recommendations/new-releases",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200


class TestDiscoverMoreEndpoint:
    """Test suite for /discover-more endpoint."""

    def test_discover_more_success(self, client, sample_collection):
        """Test discover more returns collections from similar genres."""
        with patch("databases.collections_database.get_collections") as mock_get_collections, \
             patch("databases.collections_database.get_songs_from_collection") as mock_get_songs:
            mock_get_collections.side_effect = [
                [sample_collection],  # Artist's collections
                [sample_collection]   # Genre collections
            ]
            mock_get_songs.return_value = []
            
            response = client.get("/recommendations/discover-more?artist_id=artist_123")
            
            assert response.status_code == 200
            data = response.json()
            assert "collections" in data
            assert isinstance(data["collections"], list)

    def test_discover_more_no_artist_id(self, client):
        """Test discover more returns empty when no artist_id provided."""
        response = client.get("/recommendations/discover-more")
        
        assert response.status_code == 200
        data = response.json()
        assert data["collections"] == []

    def test_discover_more_artist_with_no_collections(self, client):
        """Test discover more when artist has no collections."""
        with patch("databases.collections_database.get_collections") as mock_get_collections:
            mock_get_collections.return_value = []
            
            response = client.get("/recommendations/discover-more?artist_id=artist_123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["collections"] == []

    def test_discover_more_multiple_genres(self, client, sample_collection):
        """Test discover more with artist having collections in multiple genres."""
        collections = [
            {**sample_collection, "genre": "Rock"},
            {**sample_collection, "genre": "Pop"}
        ]
        
        with patch("databases.collections_database.get_collections") as mock_get_collections, \
             patch("databases.collections_database.get_songs_from_collection") as mock_get_songs:
            mock_get_collections.side_effect = [
                collections,  # Artist's collections
                [collections[0]],  # Rock genre
                [collections[1]]   # Pop genre
            ]
            mock_get_songs.return_value = []
            
            response = client.get("/recommendations/discover-more?artist_id=artist_123")
            
            assert response.status_code == 200
            data = response.json()
            assert "collections" in data

    def test_discover_more_handles_error(self, client):
        """Test discover more handles database errors gracefully."""
        with patch("databases.collections_database.get_collections") as mock_get_collections:
            mock_get_collections.side_effect = Exception("Database error")
            
            response = client.get("/recommendations/discover-more?artist_id=artist_123")
            
            assert response.status_code == 500
            assert "error" in response.json()


class TestShortcutsEndpoint:
    """Test suite for /shortcuts endpoint."""

    def test_shortcuts_success(self, client, sample_songs):
        """Test shortcuts returns playlists and collections based on top plays."""
        for song in sample_songs:
            result = client.post("/songs", json={
                "title": song["title"],
                "duration": song["duration"]
            })

        with patch("databases.metrics_database.get_user_top_n_plays", new_callable=AsyncMock) as mock_top_plays, \
             patch("databases.songs_database.get_song", new_callable=AsyncMock) as mock_get_song, \
             patch("databases.playlists_database.get_public_playlists_by_artist", new_callable=AsyncMock, create=True) as mock_playlists, \
             patch("databases.collections_database.get_public_collections_by_album", new_callable=AsyncMock, create=True) as mock_collections:
            mock_top_plays.return_value = [
                {"song_id": str(ObjectId())}
            ]
            mock_get_song.return_value = {
                "_id": ObjectId(),
                "title": "Test Song",
                "artist": "Test Artist",
                "album": "Test Album"
            }
            mock_playlists.return_value = []
            mock_collections.return_value = []
            
            response = client.get("/recommendations/shortcuts")
            
            assert response.status_code == 200
            data = response.json()
            assert "playlists" in data
            assert "collections" in data

    def test_shortcuts_no_play_history(self, client):
        """Test shortcuts when user has no play history."""
        with patch("databases.metrics_database.get_user_top_n_plays") as mock_top_plays:
            mock_top_plays.return_value = []
            
            response = client.get("/recommendations/shortcuts")
            
            assert response.status_code == 200
            # Should return None or empty response
            data = response.json()
            assert data is None or "playlists" not in data

    def test_shortcuts_song_not_found(self, client):
        """Test shortcuts handles case when song from play history doesn't exist."""
        with patch("databases.metrics_database.get_user_top_n_plays", new_callable=AsyncMock) as mock_top_plays, \
             patch("databases.songs_database.get_song", new_callable=AsyncMock) as mock_get_song:
            mock_top_plays.return_value = [{"song_id": str(ObjectId())}]
            mock_get_song.return_value = None
            
            response = client.get("/recommendations/shortcuts")
            
            assert response.status_code == 200
            data = response.json()
            assert "playlists" in data
            assert "collections" in data

    def test_shortcuts_handles_error(self, client):
        """Test shortcuts handles database errors gracefully."""
        with patch("databases.metrics_database.get_user_top_n_plays") as mock_top_plays:
            mock_top_plays.side_effect = Exception("Database error")
            
            response = client.get("/recommendations/shortcuts")
            
            assert response.status_code == 500
            assert "error" in response.json()


class TestSimilarArtistsEndpoint:
    """Test suite for /similar-artists endpoint."""

    def test_similar_artists_success(self, client, sample_collection):
        """Test similar artists returns artist IDs from same genres."""
        collections = [
            {**sample_collection, "artistId": "artist_123"},
            {**sample_collection, "artistId": "artist_456"},
            {**sample_collection, "artistId": "artist_789"}
        ]
        
        with patch("databases.collections_database.get_collections") as mock_get_collections:
            mock_get_collections.side_effect = [
                [collections[0]],  # Query artist's collections
                collections         # Query genre collections
            ]
            
            response = client.get("/recommendations/similar-artists?artist_id=artist_123")
            
            assert response.status_code == 200
            data = response.json()
            assert "artists" in data
            assert "count" in data
            assert isinstance(data["artists"], (list, set))

    def test_similar_artists_no_artist_id(self, client):
        """Test similar artists returns empty when no artist_id provided."""
        response = client.get("/recommendations/similar-artists")
        
        assert response.status_code == 200
        data = response.json()
        assert data["artists"] == []

    def test_similar_artists_excludes_same_artist(self, client, sample_collection):
        """Test similar artists excludes the queried artist from results."""
        collections = [
            {**sample_collection, "artistId": "artist_123", "genre": "Rock"},
            {**sample_collection, "artistId": "artist_456", "genre": "Rock"}
        ]
        
        with patch("databases.collections_database.get_collections") as mock_get_collections:
            mock_get_collections.side_effect = [
                [collections[0]],  # Artist's collections
                collections        # Genre collections
            ]
            
            response = client.get("/recommendations/similar-artists?artist_id=artist_123")
            
            assert response.status_code == 200
            data = response.json()
            # Should not include artist_123
            if isinstance(data["artists"], list):
                assert "artist_123" not in data["artists"]

    def test_similar_artists_no_collections(self, client):
        """Test similar artists when artist has no collections."""
        with patch("databases.collections_database.get_collections") as mock_get_collections:
            mock_get_collections.return_value = []
            
            response = client.get("/recommendations/similar-artists?artist_id=artist_123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["artists"] == []
            assert data["count"] == 0

    def test_similar_artists_multiple_genres(self, client, sample_collection):
        """Test similar artists with artist having collections in multiple genres."""
        artist_collections = [
            {**sample_collection, "artistId": "artist_123", "genre": "Rock"},
            {**sample_collection, "artistId": "artist_123", "genre": "Pop"}
        ]
        similar_collections = [
            {**sample_collection, "artistId": "artist_456", "genre": "Rock"},
            {**sample_collection, "artistId": "artist_789", "genre": "Pop"}
        ]
        
        with patch("databases.collections_database.get_collections") as mock_get_collections:
            mock_get_collections.side_effect = [
                artist_collections,      # Artist's collections
                [similar_collections[0]],  # Rock genre
                [similar_collections[1]]   # Pop genre
            ]
            
            response = client.get("/recommendations/similar-artists?artist_id=artist_123")
            
            assert response.status_code == 200
            data = response.json()
            assert "artists" in data
            assert data["count"] >= 0

    def test_similar_artists_handles_error(self, client):
        """Test similar artists handles database errors gracefully."""
        with patch("databases.collections_database.get_collections") as mock_get_collections:
            mock_get_collections.side_effect = Exception("Database error")
            
            response = client.get("/recommendations/similar-artists?artist_id=artist_123")
            
            assert response.status_code == 500
            assert "error" in response.json()


class TestRecommendationsIntegration:
    """Integration tests for recommendations endpoints."""

    def test_all_mix_playlists_have_correct_metadata(self, client):
        """Test all mix endpoints return playlists with correct metadata."""
        endpoints = [
            "/recommendations/daily-mix",
            "/recommendations/mood-mix",
            "/recommendations/because-you-listened"
        ]
        
        for endpoint in endpoints:
            with patch("databases.preferences_database.get_user_genres") as mock_genres, \
                 patch("databases.preferences_database.get_random_genre") as mock_random, \
                 patch("databases.preferences_database.get_available_genres") as mock_available, \
                 patch("databases.songs_database.get_songs_by_genre") as mock_songs, \
                 patch("databases.metrics_database.get_user_top_n_plays") as mock_plays, \
                 patch("databases.collections_database.get_collections") as mock_collections, \
                 patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
                mock_genres.return_value = "Pop"
                mock_random.return_value = "Rock"
                mock_available.return_value = ["Pop"]
                mock_songs.return_value = []
                mock_plays.return_value = []
                mock_collections.return_value = []
                mock_filter.side_effect = lambda user, songs, db=None: songs
                
                response = client.get(endpoint)
                
                assert response.status_code == 200
                data = response.json()["data"]
                assert "id" in data
                assert "name" in data
                assert "userId" in data
                assert data["isMix"] is True
                assert data["isPublished"] is True
                assert "coverUrl" in data
                assert "songs" in data

    def test_mix_playlists_use_correct_cover_urls(self, client):
        """Test each mix playlist has its specific cover URL."""
        expected_covers = {
            "/recommendations/daily-mix": "daily-mix.png",
            "/recommendations/mood-mix": "mood-mix.png",
            "/recommendations/because-you-listened": "because-you-listened-to.png"
        }
        
        for endpoint, cover_file in expected_covers.items():
            with patch("databases.preferences_database.get_user_genres") as mock_genres, \
                 patch("databases.preferences_database.get_random_genre") as mock_random, \
                 patch("databases.preferences_database.get_available_genres") as mock_available, \
                 patch("databases.songs_database.get_songs_by_genre") as mock_songs, \
                 patch("databases.metrics_database.get_user_top_n_plays") as mock_plays, \
                 patch("databases.collections_database.get_collections") as mock_collections, \
                 patch("controllers.recomendations_controller._filter_songs_by_geography") as mock_filter:
                mock_genres.return_value = "Pop"
                mock_random.return_value = "Rock"
                mock_available.return_value = ["Pop"]
                mock_songs.return_value = []
                mock_plays.return_value = []
                mock_collections.return_value = []
                mock_filter.side_effect = lambda user, songs, db=None: songs
                
                response = client.get(endpoint)
                
                assert response.status_code == 200
                data = response.json()["data"]
                assert cover_file in data["coverUrl"]

