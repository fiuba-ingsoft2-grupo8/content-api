import pytest


class TestHistoryEndpoints:
    """Test suite for user listening history."""

    def test_add_to_history(self, client):
        """Add a song to a user's listening history."""

        song = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]
        response = client.post("/history", json={
            "songId": song["_id"],
            "userId": "uu8432"
        })
        assert response.status_code == 201

    def test_get_history(self, client):
        """Fetch a user's listening history."""
        
        song = client.post("/songs", json={"title": "Fortnight", "duration": "60"}).json()["data"]
        client.post("/history", json={
            "songId": song["_id"],
            "userId": "uu8432"
        })
        response = client.get("/history?userId=uu8432")
        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        assert len(data) > 0
        entry = data[0]
        assert entry["song"]["_id"] == song["_id"]
        assert entry["playedAt"] is not None

    def test_filter_history(self, client):
        song1 = client.post("/songs", json={"title": "Willow", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Lover", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "Stick Season", "duration": "60"}).json()["data"]

        user_id = "uu8432"
        for s in [song1, song2, song3]:
            client.post("/history", json={"songId": s["_id"], "userId": user_id})

        resp = client.get(f"/history?userId={user_id}&search=Willow")
        data = resp.json()["data"]

        assert all("Willow" in d["song"]["title"] for d in data)
        assert resp.status_code == 200

    def test_filter_history_no_matches(self, client):
        song1 = client.post("/songs", json={"title": "False Confidence", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "New Perspective", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "Stick Season", "duration": "60"}).json()["data"]

        user_id = "uu8432"
        for s in [song1, song2, song3]:
            client.post("/history", json={"songId": s["_id"], "userId": user_id})

        resp = client.get(f"/history?userId={user_id}&search=NonExistentSong")
        data = resp.json()["data"]

        assert len(data) == 0  # No matches should be found
        assert resp.status_code == 200

    def test_filter_history_case_insensitive(self, client):
        song1 = client.post("/songs", json={"title": "Willow", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Lover", "duration": "60"}).json()["data"]
        song3 = client.post("/songs", json={"title": "Stick Season", "duration": "60"}).json()["data"]

        user_id = "uu8432"
        for s in [song1, song2, song3]:
            client.post("/history", json={"songId": s["_id"], "userId": user_id})

        resp = client.get(f"/history?userId={user_id}&search=wIlLoW")
        data = resp.json()["data"]

        assert all("Willow" in d["song"]["title"] for d in data)
        assert resp.status_code == 200    

    def test_add_to_history_invalid_song(self, client):
        """Adding a song that doesn't exist should fail."""
        response = client.post("/history", json={
            "songId": "999999999999999999999999", 
            "userId": "uu8432"
        })
        assert response.status_code == 404

    def test_duplicate_song_addition(self, client):
        """Adding the same song twice should update timestamp, not duplicate."""
        song = client.post("/songs", json={"title": "Lover", "duration": "60"}).json()["data"]

        client.post("/history", json={"songId": song["_id"], "userId": "uu8432"})
        client.post("/history", json={"songId": song["_id"], "userId": "uu8432"})

        response = client.get("/history", params={"userId": "uu8432"})
        assert response.status_code == 200

        data = response.json()["data"]
        lover_entries = [d for d in data if d["song"]["_id"] == song["_id"]]
        assert len(lover_entries) == 1
        assert lover_entries[0]["progress"] == 0

    def test_update_progress(self, client):
        song = client.post("/songs", json={"title": "Willow", "duration": "60"}).json()["data"]
        client.post("/history", json={"songId": song["_id"], "userId": "uu8432"})

        response = client.put("/history", json={"songId": song["_id"], "userId": "uu8432", "progress": 120})
        assert response.status_code == 200

    def test_clear_history(self, client):
        """Clear all listening history for a user."""
        song1 = client.post("/songs", json={"title": "Willow", "duration": "60"}).json()["data"]
        song2 = client.post("/songs", json={"title": "Red", "duration": "60"}).json()["data"]
        client.post("/history", json={"songId": song1["_id"], "userId": "uu8432"})
        client.post("/history", json={"songId": song2["_id"], "userId": "uu8432"})

        response = client.get("/history?userId=uu8432")
        data = response.json()["data"]
        assert len(data) == 2

        delete_response = client.request("DELETE", "/history?userId=uu8432")
        assert delete_response.status_code == 200

        response_after = client.get("/history?userId=uu8432")
        data_after = response_after.json()["data"]
        assert data_after == []

    def test_get_history_state_default(self, client):
        """Get history state for a user who has never paused - should default to not paused."""
        response = client.get("/history/state")
        assert response.status_code == 200
        data = response.json()
        assert "isPaused" in data
        assert data["isPaused"] is False

    def test_toggle_history_state_first_time(self, client):
        """First time toggling should pause history (create new state record)."""
        response = client.post("/history/state/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["isPaused"] is True
        assert "paused" in data["message"].lower()

    def test_toggle_history_state_pause_and_resume(self, client):
        """Toggle history state multiple times - should alternate between paused and resumed."""
        # First toggle: pause
        response1 = client.post("/history/state/toggle")
        assert response1.status_code == 200
        assert response1.json()["isPaused"] is True

        # Check state is paused
        state_response = client.get("/history/state")
        assert state_response.json()["isPaused"] is True

        # Second toggle: resume
        response2 = client.post("/history/state/toggle")
        assert response2.status_code == 200
        assert response2.json()["isPaused"] is False
        assert "resumed" in response2.json()["message"].lower()

        # Check state is not paused
        state_response2 = client.get("/history/state")
        assert state_response2.json()["isPaused"] is False

        # Third toggle: pause again
        response3 = client.post("/history/state/toggle")
        assert response3.status_code == 200
        assert response3.json()["isPaused"] is True

    def test_add_to_history_when_paused(self, client):
        """Adding a song to history when paused should not record it."""
        song = client.post("/songs", json={"title": "Paused Song", "duration": "60"}).json()["data"]
        
        # Pause history
        client.post("/history/state/toggle")
        
        # Verify it's paused
        state = client.get("/history/state").json()
        assert state["isPaused"] is True
        
        # Try to add song to history
        response = client.post("/history", json={"songId": song["_id"], "userId": "uu8432"})
        assert response.status_code == 200
        assert "paused" in response.json()["message"].lower()
        
        # Verify history is still empty
        history = client.get("/history?userId=uu8432")
        assert len(history.json()["data"]) == 0

    def test_add_to_history_when_not_paused(self, client):
        """Adding a song to history when not paused should record it normally."""
        song = client.post("/songs", json={"title": "Normal Song", "duration": "60"}).json()["data"]
        
        # Ensure history is not paused (default state)
        state = client.get("/history/state").json()
        assert state["isPaused"] is False
        
        # Add song to history
        response = client.post("/history", json={"songId": song["_id"], "userId": "uu8432"})
        assert response.status_code == 201
        
        # Verify song was added
        history = client.get("/history?userId=uu8432")
        data = history.json()["data"]
        assert len(data) == 1
        assert data[0]["song"]["_id"] == song["_id"]

    def test_add_to_history_after_resume(self, client):
        """Adding a song after pausing and then resuming should work."""
        song = client.post("/songs", json={"title": "Resume Test", "duration": "60"}).json()["data"]
        
        # Pause history
        client.post("/history/state/toggle")
        assert client.get("/history/state").json()["isPaused"] is True
        
        # Resume history
        client.post("/history/state/toggle")
        assert client.get("/history/state").json()["isPaused"] is False
        
        # Add song to history
        response = client.post("/history", json={"songId": song["_id"], "userId": "uu8432"})
        assert response.status_code == 201
        
        # Verify song was added
        history = client.get("/history?userId=uu8432")
        data = history.json()["data"]
        assert len(data) == 1
        assert data[0]["song"]["_id"] == song["_id"]

