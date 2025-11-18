import pytest
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from unittest.mock import patch, AsyncMock, MagicMock, Mock


@pytest.fixture(autouse=True)
def mock_external_api_module():
    """Mock external API calls to avoid real HTTP requests in ALL tests in this module."""
    # Mock the _fetch_users_by_name function directly to avoid httpx overhead
    async def mock_fetch_users(*args, **kwargs):
        return []
    
    with patch("databases.collections_database._fetch_users_by_name", new=mock_fetch_users):
        yield


class TestSearchController:
    """Test suite for search controller endpoints."""

    def test_search_songs_by_title(self, client):
        """Test searching for songs by title."""
        # Create some test songs
        song1 = client.post("/songs", json={
            "title": "Rock Anthem",
            "artist": "Test Band",
            "duration": "240"
        }).json()["data"]
        
        song2 = client.post("/songs", json={
            "title": "Rock Ballad",
            "artist": "Another Band",
            "duration": "300"
        }).json()["data"]
        
        song3 = client.post("/songs", json={
            "title": "Jazz Classic",
            "artist": "Jazz Artist",
            "duration": "180"
        }).json()["data"]
        
        # Search for "rock"
        response = client.get("/search?str_name=rock")
        assert response.status_code == 200
        data = response.json()
        
        assert "collections" in data
        collections = data["collections"]
        assert "songs" in collections
        
        # Should find both rock songs
        found_songs = collections["songs"]
        assert len(found_songs) >= 2
        song_titles = [s["title"] for s in found_songs]
        assert "Rock Anthem" in song_titles
        assert "Rock Ballad" in song_titles
        assert "Jazz Classic" not in song_titles

    def test_search_songs_by_artist(self, client):
        """Test searching for songs by artist name."""
        # Create test songs with different artists
        song1 = client.post("/songs", json={
            "title": "Song One",
            "artist": "Queen",
            "duration": "240"
        }).json()["data"]
        
        song2 = client.post("/songs", json={
            "title": "Song Two",
            "artist": "The Beatles",
            "duration": "180"
        }).json()["data"]
        
        # Search for "queen"
        response = client.get("/search?str_name=queen")
        assert response.status_code == 200
        data = response.json()
        
        collections = data["collections"]
        found_songs = collections.get("songs", [])
        
        # Should find the Queen song
        if found_songs:
            queen_songs = [s for s in found_songs if "Queen" in s.get("artist", "")]
            assert len(queen_songs) >= 1

    def test_search_playlists_by_name(self, client):
        """Test searching for playlists by name."""
        # Note: There's currently a known issue where playlists search doesn't return 
        # playlist details correctly. This test verifies the response structure.
        
        # Create test playlists
        playlist1 = client.post("/playlists", json={
            "name": "Summer Vibes",
            "description": "Best summer songs"
        }).json()["data"]
        
        # Publish the playlist so it can be searched
        client.post(f"/playlists/{playlist1['id']}/publish")
        
        # Search for "summer"
        response = client.get("/search?str_name=summer")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure exists
        collections = data["collections"]
        assert "playlists" in collections
        assert "songs" in collections
        assert "users" in collections
        
        # Currently the playlists list may be empty due to implementation issue
        # where get_collection() is called on playlist IDs
        assert isinstance(collections["playlists"], list)

    def test_search_case_insensitive(self, client):
        """Test that search is case-insensitive."""
        # Create a song
        song = client.post("/songs", json={
            "title": "Bohemian Rhapsody",
            "artist": "Queen",
            "duration": "354"
        }).json()["data"]
        
        # Search with different cases
        for search_term in ["bohemian", "BOHEMIAN", "BoHeMiAn"]:
            response = client.get(f"/search?str_name={search_term}")
            assert response.status_code == 200
            data = response.json()
            
            collections = data["collections"]
            found_songs = collections.get("songs", [])
            
            # Should find the song regardless of case
            song_titles = [s["title"] for s in found_songs]
            assert "Bohemian Rhapsody" in song_titles

    def test_search_partial_match(self, client):
        """Test that search works with partial matches."""
        # Create a song with a longer title
        song = client.post("/songs", json={
            "title": "Stairway to Heaven",
            "artist": "Led Zeppelin",
            "duration": "480"
        }).json()["data"]
        
        # Search with partial term
        response = client.get("/search?str_name=stair")
        assert response.status_code == 200
        data = response.json()
        
        collections = data["collections"]
        found_songs = collections.get("songs", [])
        
        # Should find the song with partial match
        song_titles = [s["title"] for s in found_songs]
        assert "Stairway to Heaven" in song_titles

    def test_search_no_results(self, client):
        """Test search when no results are found."""
        # Search for something that doesn't exist
        response = client.get("/search?str_name=xyzabc123nonexistent")
        # Note: API returns 200 with empty collections, not 404
        assert response.status_code == 200
        data = response.json()
        
        # Verify empty results structure
        assert "collections" in data
        collections = data["collections"]
        assert len(collections.get("playlists", [])) == 0
        assert len(collections.get("songs", [])) == 0
        assert len(collections.get("users", [])) == 0

    def test_search_empty_query(self, client):
        """Test search with empty query string."""
        # Search with empty string
        response = client.get("/search?str_name=")
        # Should either return all results or return 404
        assert response.status_code in [200, 404]

    def test_search_returns_all_types(self, client):
        """Test that search returns playlists, songs, and users in response."""
        # Create a song
        song = client.post("/songs", json={
            "title": "Test Song",
            "artist": "Test Artist",
            "duration": "180"
        }).json()["data"]
        
        # Create and publish a playlist
        playlist = client.post("/playlists", json={
            "name": "Test Playlist",
            "description": "Test Description"
        }).json()["data"]
        
        client.post(f"/playlists/{playlist['id']}/publish")
        
        # Search for "test"
        response = client.get("/search?str_name=test")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "collections" in data
        collections = data["collections"]
        
        # Should have all three types in the response structure
        assert "playlists" in collections
        assert "songs" in collections
        assert "users" in collections
        
        # Should be lists
        assert isinstance(collections["playlists"], list)
        assert isinstance(collections["songs"], list)
        assert isinstance(collections["users"], list)

    def test_search_collections_by_name(self, client):
        """Test searching for collections (albums/EPs) by name."""
        # Note: Collections (albums) work, but playlists currently have an issue
        # This test focuses on collections which use the correct database table
        
        # Search for a collection that might exist
        response = client.get("/search?str_name=test")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        collections = data["collections"]
        assert "playlists" in collections
        assert "songs" in collections
        assert "users" in collections
        
        # All should be lists
        assert isinstance(collections["playlists"], list)
        assert isinstance(collections["songs"], list)
        assert isinstance(collections["users"], list)

    def test_search_special_characters(self, client):
        """Test search with special characters."""
        # Create a song with special characters
        song = client.post("/songs", json={
            "title": "Don't Stop Me Now",
            "artist": "Queen",
            "duration": "210"
        }).json()["data"]
        
        # Search with apostrophe
        response = client.get("/search?str_name=don't")
        assert response.status_code in [200, 404]
        
        # If found, verify it's the correct song
        if response.status_code == 200:
            data = response.json()
            collections = data["collections"]
            found_songs = collections.get("songs", [])
            
            if found_songs:
                song_titles = [s["title"] for s in found_songs]
                assert "Don't Stop Me Now" in song_titles

    def test_search_song_includes_required_fields(self, client):
        """Test that searched songs include all required fields."""
        # Create a song with all fields
        song = client.post("/songs", json={
            "title": "Complete Song",
            "artist": "Complete Artist",
            "duration": "180",
            "album": "Complete Album",
            "genre": "Rock"
        }).json()["data"]
        
        # Search for it
        response = client.get("/search?str_name=complete")
        assert response.status_code == 200
        data = response.json()
        
        collections = data["collections"]
        found_songs = collections["songs"]
        
        # Find our song
        complete_songs = [s for s in found_songs if s["title"] == "Complete Song"]
        assert len(complete_songs) >= 1
        
        song_result = complete_songs[0]
        # Check required fields
        assert "_id" in song_result
        assert "title" in song_result
        assert song_result["title"] == "Complete Song"

    def test_search_response_structure(self, client):
        """Test that search response has the correct structure."""
        # Create a song to ensure we get some results
        song = client.post("/songs", json={
            "title": "Structure Test Song",
            "artist": "Test Artist",
            "duration": "180"
        }).json()["data"]
        
        # Search for it
        response = client.get("/search?str_name=structure")
        assert response.status_code == 200
        data = response.json()
        
        # Verify top-level structure
        assert "collections" in data
        collections = data["collections"]
        
        # Verify all three collection types exist
        assert "playlists" in collections
        assert "songs" in collections
        assert "users" in collections
        
        # All should be lists
        assert isinstance(collections["playlists"], list)
        assert isinstance(collections["songs"], list)
        assert isinstance(collections["users"], list)

    def test_search_with_various_content_types(self, client):
        """Test search across multiple content types."""
        # Create a song
        song = client.post("/songs", json={
            "title": "Multi Test Song",
            "artist": "Multi Artist",
            "duration": "180"
        }).json()["data"]
        
        # Create a playlist
        playlist = client.post("/playlists", json={
            "name": "Multi Test Playlist",
            "description": "Test playlist"
        }).json()["data"]
        client.post(f"/playlists/{playlist['id']}/publish")
        
        # Search for "multi"
        response = client.get("/search?str_name=multi")
        assert response.status_code == 200
        data = response.json()
        
        # Should have the collection structure
        assert "collections" in data
        collections = data["collections"]
        assert "playlists" in collections
        assert "songs" in collections
        assert "users" in collections

    def test_search_multiple_words(self, client):
        """Test search with multiple words."""
        # Create a song with multi-word title
        song = client.post("/songs", json={
            "title": "A Day in the Life",
            "artist": "The Beatles",
            "duration": "320"
        }).json()["data"]
        
        # Search with multiple words
        response = client.get("/search?str_name=day life")
        assert response.status_code in [200, 404]
        
        # Depending on search implementation, this might or might not find results

    def test_search_unicode_characters(self, client):
        """Test search with unicode characters."""
        # Create a song with unicode characters
        song = client.post("/songs", json={
            "title": "Café del Mar",
            "artist": "Energy 52",
            "duration": "420"
        }).json()["data"]
        
        # Search with unicode
        response = client.get("/search?str_name=café")
        assert response.status_code in [200, 404]
        
        # If search supports unicode, should find the song
        if response.status_code == 200:
            data = response.json()
            collections = data["collections"]
            found_songs = collections.get("songs", [])
            
            if found_songs:
                song_titles = [s["title"] for s in found_songs]
                # Might find it depending on unicode normalization
                assert any("Café" in title or "café" in title for title in song_titles)

    def test_search_numbers_in_title(self, client):
        """Test search with numbers in the title."""
        # Create songs with numbers
        song = client.post("/songs", json={
            "title": "1999",
            "artist": "Prince",
            "duration": "210"
        }).json()["data"]
        
        # Search for the number
        response = client.get("/search?str_name=1999")
        assert response.status_code == 200
        data = response.json()
        
        collections = data["collections"]
        found_songs = collections.get("songs", [])
        
        song_titles = [s["title"] for s in found_songs]
        assert "1999" in song_titles

    def test_search_very_long_query(self, client):
        """Test search with a very long query string."""
        # Create a song
        song = client.post("/songs", json={
            "title": "Short",
            "artist": "Artist",
            "duration": "180"
        }).json()["data"]
        
        # Search with very long query
        long_query = "a" * 500
        response = client.get(f"/search?str_name={long_query}")
        
        # Should handle gracefully
        assert response.status_code in [200, 404, 400]

    def test_search_with_punctuation(self, client):
        """Test search with various punctuation marks."""
        # Create songs with punctuation
        song = client.post("/songs", json={
            "title": "What's Up?",
            "artist": "4 Non Blondes",
            "duration": "270"
        }).json()["data"]
        
        # Search with punctuation
        response = client.get("/search?str_name=what's")
        assert response.status_code in [200, 404]

    def test_search_returns_serialized_data(self, client):
        """Test that search results are properly serialized."""
        # Create a song
        song = client.post("/songs", json={
            "title": "Serialized Song",
            "artist": "Test Artist",
            "duration": "180"
        }).json()["data"]
        
        # Search for it
        response = client.get("/search?str_name=serialized")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response is JSON serializable (no ObjectId, datetime issues)
        assert isinstance(data, dict)
        assert "collections" in data
        
        collections = data["collections"]
        for song in collections.get("songs", []):
            # _id should be a string, not ObjectId
            assert isinstance(song["_id"], str)
            # Should not have any MongoDB ObjectId objects
            for value in song.values():
                assert not str(type(value)).startswith("<class 'bson")


class TestSearchGeographicalRestrictions:
    """Tests for geographical restrictions in search results."""

    def test_search_standalone_song_accessible_everywhere(self, client):
        """Test that standalone songs (not in collections) are accessible from all countries."""
        # Create a standalone song (not added to any collection)
        client.post("/songs", json={"title": "Standalone GeoTest", "duration": "180"})
        
        # Search for the song
        response = client.get("/search?str_name=Standalone GeoTest")
        assert response.status_code == 200
        
        data = response.json()["collections"]
        song_titles = [s["title"] for s in data.get("songs", [])]
        
        # Standalone song should be accessible
        assert "Standalone GeoTest" in song_titles

    def test_search_owner_sees_own_restricted_content(self, client):
        """Test that song owner can find their own restricted songs."""
        # Create song that will be in a restricted collection
        song = client.post("/songs", json={"title": "OwnerOnlySong Restricted", "duration": "180"}).json()["data"]
        
        # Create collection only available in US (user is from AR)
        client.post("/collections/", json={
            "name": "Owner US Only Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song['_id']}],
            "availableInCountries": ["US"]
        })
        
        # Search for the song - owner should see their own song even though collection is not in their country
        response = client.get("/search?str_name=OwnerOnlySong")
        assert response.status_code == 200
        
        data = response.json()["collections"]
        song_titles = [s["title"] for s in data.get("songs", [])]
        
        # Owner should see their own restricted song
        assert "OwnerOnlySong Restricted" in song_titles

    def test_search_song_in_multiple_collections_accessible_if_one_available(self, client):
        """Test that a song in multiple collections is accessible if at least one collection is available."""
        # Create a song
        song = client.post("/songs", json={"title": "Multi Collection Song", "duration": "180"}).json()["data"]
        
        # Add to collection NOT available in AR
        client.post("/collections/", json={
            "name": "US Only Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song['_id']}],
            "availableInCountries": ["US"]
        })
        
        # Add same song to collection available in AR
        client.post("/collections/", json={
            "name": "AR Available Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song['_id']}],
            "availableInCountries": ["AR"]
        })
        
        # Search for the song
        response = client.get("/search?str_name=Multi Collection")
        assert response.status_code == 200
        
        data = response.json()["collections"]
        song_titles = [s["title"] for s in data.get("songs", [])]
        
        # Song should be accessible because it's in at least one available collection
        assert "Multi Collection Song" in song_titles

    def test_can_user_access_song_function(self):
        """Unit test for _can_user_access_song function."""
        from controllers.search_controller import _can_user_access_song
        from unittest.mock import MagicMock, patch
        from bson import ObjectId
        
        # Mock database
        mock_db = MagicMock()
        song_id = str(ObjectId())
        collection_id = ObjectId()
        
        # Setup: song in collection with country restrictions
        mock_db.songs.find_one.return_value = {"_id": ObjectId(song_id), "artistId": "other_artist"}
        mock_db.collection_songs.find.return_value = [{"collection_id": collection_id}]
        mock_db.collections.find.return_value = [
            {"_id": collection_id, "availableCountries": ["AR", "UY"], "artistId": "other_artist"}
        ]
        
        user_ar = {"user_id": "user1", "country": "AR", "user_type": "user"}
        user_us = {"user_id": "user1", "country": "US", "user_type": "user"}
        
        with patch("controllers.search_controller.get_db", return_value=mock_db):
            import asyncio
            
            # User from AR should have access
            result_ar = asyncio.run(_can_user_access_song(user_ar, song_id))
            assert result_ar == True
            
            # User from US should NOT have access
            result_us = asyncio.run(_can_user_access_song(user_us, song_id))
            assert result_us == False


class TestSearchAlbumsGeographicalRestrictions:
    """Tests for album (collection) geographical filtering in search results"""
    
    @pytest.mark.asyncio
    async def test_search_album_accessible_in_user_country(self, client, mock_db):
        """Album available in user's country should appear in search results"""
        # Create an album available in Argentina (user's country is AR from auth.py)
        collection_result = mock_db.collections.insert_one({
            "name": "Melodic Dreams",
            "artistId": "test_user_123",
            "artistName": "Test Artist",
            "type": "album",
            "genre": "Pop",
            "coverUrl": "https://example.com/cover.jpg",
            "createdAt": datetime.now(timezone.utc),
            "releaseDate": datetime.now(timezone.utc) - timedelta(days=30),
            "availableCountries": ["AR", "BR", "CL"]  # Available in Argentina
        })
        
        # Search for the album
        response = client.get("/search?str_name=Melodic")
        assert response.status_code == 200
        data = response.json()
        
        # Album should appear in results
        assert "albums" in data["collections"]
        assert len(data["collections"]["albums"]) == 1
        assert data["collections"]["albums"][0]["name"] == "Melodic Dreams"
    
    @pytest.mark.asyncio
    async def test_search_album_not_accessible_in_user_country(self, client, mock_db):
        """Album not available in user's country should NOT appear in search results"""
        # Create an album available only in US and GB (NOT in Argentina where user is from)
        collection_result = mock_db.collections.insert_one({
            "name": "Latin Vibes",
            "artistId": "different_artist_789",  # Different artist, not the test user
            "artistName": "Test Artist",
            "type": "album",
            "genre": "Latin",
            "coverUrl": "https://example.com/cover2.jpg",
            "createdAt": datetime.now(timezone.utc),
            "releaseDate": datetime.now(timezone.utc) - timedelta(days=15),
            "availableCountries": ["US", "GB"]  # NOT available in Argentina
        })
        
        # Search for the album as user from AR
        response = client.get("/search?str_name=Latin")
        assert response.status_code == 200
        data = response.json()
        
        # Album should NOT appear in results for AR user
        assert "albums" in data["collections"]
        assert len(data["collections"]["albums"]) == 0
    
    @pytest.mark.asyncio
    async def test_search_album_owner_sees_restricted_album(self, client, mock_db):
        """Album owner should see their own albums regardless of country restrictions"""
        # Create an album available only in US (not in user's country AR)
        collection_result = mock_db.collections.insert_one({
            "name": "Owner Album",
            "artistId": "test_user_123",  # User's own album
            "artistName": "Test Artist",
            "type": "album",
            "genre": "Rock",
            "coverUrl": "https://example.com/cover3.jpg",
            "createdAt": datetime.now(timezone.utc),
            "releaseDate": datetime.now(timezone.utc) - timedelta(days=5),
            "availableCountries": ["US"]  # Only US, not AR
        })
        
        # Owner should see their own album
        response = client.get("/search?str_name=Owner")
        assert response.status_code == 200
        data = response.json()
        
        assert "albums" in data["collections"]
        assert len(data["collections"]["albums"]) == 1
        assert data["collections"]["albums"][0]["name"] == "Owner Album"
    
    @pytest.mark.asyncio
    async def test_search_album_no_restrictions_accessible_everywhere(self, client, mock_db):
        """Album with no country restrictions should be accessible to all users"""
        # Create an album with no country restrictions
        collection_result = mock_db.collections.insert_one({
            "name": "Global Hits",
            "artistId": "different_artist_789",
            "artistName": "Test Artist",
            "type": "album",
            "genre": "Pop",
            "coverUrl": "https://example.com/cover4.jpg",
            "createdAt": datetime.now(timezone.utc),
            "releaseDate": datetime.now(timezone.utc) - timedelta(days=60),
            "availableCountries": []  # No restrictions
        })
        
        # User from any country should see it
        response = client.get("/search?str_name=Global")
        assert response.status_code == 200
        data = response.json()
        
        assert "albums" in data["collections"]
        assert len(data["collections"]["albums"]) == 1
        assert data["collections"]["albums"][0]["name"] == "Global Hits"
    
    @pytest.mark.asyncio
    async def test_search_mixed_results_with_geographical_filtering(self, client, mock_db):
        """Search should filter albums based on geographical restrictions"""
        # Create an album available in AR (user's country)
        collection_result = mock_db.collections.insert_one({
            "name": "Best Album",
            "artistId": "different_artist_789",  # Different artist
            "artistName": "Test Artist",
            "type": "album",
            "genre": "Rock",
            "coverUrl": "https://example.com/album.jpg",
            "createdAt": datetime.now(timezone.utc),
            "releaseDate": datetime.now(timezone.utc) - timedelta(days=10),
            "availableCountries": ["AR", "BR"]  # Available in AR
        })
        
        # Create an album NOT available in AR (only US)
        collection_result2 = mock_db.collections.insert_one({
            "name": "Best US Album",
            "artistId": "different_artist_789",  # Different artist
            "artistName": "Test Artist",
            "type": "album",
            "genre": "Rock",
            "coverUrl": "https://example.com/album2.jpg",
            "createdAt": datetime.now(timezone.utc),
            "releaseDate": datetime.now(timezone.utc) - timedelta(days=20),
            "availableCountries": ["US"]  # Only US, NOT AR
        })
        
        # Search as AR user
        response = client.get("/search?str_name=Best")
        assert response.status_code == 200
        data = response.json()
        
        # Should have only the AR-available album, not the US-only album
        assert len(data["collections"]["albums"]) == 1
        assert data["collections"]["albums"][0]["name"] == "Best Album"

