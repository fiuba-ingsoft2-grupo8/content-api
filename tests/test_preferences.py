import pytest
import sys
import os


class TestPreferencesEndpoints:
    """Test suite for user genre and artist preferences."""

    def test_set_genre_preferences(self, client):
        """Set a user's genre preferences."""
        user_id = "uu8432"
        response = client.post(
            "/preferences/genres",
            json={"data": ["rock", "jazz", "pop"]}
        )

        assert response.status_code == 200
        body = response.json()
        assert "genres" in body
        assert body["genres"] == ["rock", "jazz", "pop"]

    def test_get_genre_preferences(self, client):
        """Retrieve a user's genre preferences."""
        user_id = "test_user_123"

        client.post(
            "/preferences/genres",
            json={"data": ["lofi", "hip hop"]}
        )

        response = client.get("/preferences/genres")

        assert response.status_code == 200
        body = response.json()
        assert "genres" in body
        assert body["genres"] == ["lofi", "hip hop"]

    def test_set_artist_preferences(self, client):
        """Set a user's artist preferences."""
        user_id = "test_user_123"

        response = client.post(
            "/preferences/artists",
            json={"data": ["Radiohead", "Boygenius"]},
            headers={"Authorization": f"Bearer {user_id}"}
        )

        assert response.status_code == 200
        body = response.json()
        assert "artists" in body
        assert body["artists"] == ["Radiohead", "Boygenius"]

    def test_get_artist_preferences(self, client):
        """Retrieve a user's artist preferences."""
        user_id = "uu8432"

        client.post(
            "/preferences/artists",
            json={"data": ["Divididos", "Pacifica"]},
            headers={"Authorization": f"Bearer {user_id}"}
        )

        response = client.get(
            "/preferences/artists",
            headers={"Authorization": f"Bearer {user_id}"}
        )

        assert response.status_code == 200
        body = response.json()
        assert "artists" in body
        assert body["artists"] == ["Divididos", "Pacifica"]

    def test_preferences_return_empty_when_not_set(self, client):
        """Users with no preferences should get empty lists."""
        user_id = "new_user_123"

        response_g = client.get(
            "/preferences/genres",
            headers={"Authorization": f"Bearer {user_id}"}
        )
        response_a = client.get(
            "/preferences/artists",
            headers={"Authorization": f"Bearer {user_id}"}
        )

        assert response_g.status_code == 200
        assert response_g.json() == {"genres": []}

        assert response_a.status_code == 200
        assert response_a.json() == {"artists": []}


