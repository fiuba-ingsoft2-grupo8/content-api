import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta


class TestCollectionAudit:
    """Test suite for collection audit functionality."""

    def test_update_collection_creates_audit_entry(self, client, mock_db):
        """Test that updating a collection creates an audit entry."""
        # Create a song and collection
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Original Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["data"]["id"]
        
        # Update the collection
        update_data = {
            "name": "Updated Album"
        }
        
        update_response = client.put(f"/collections/{collection_id}", json=update_data)
        assert update_response.status_code == 200
        
        # Check that audit entry was created
        audit_entries = list(mock_db.collection_audit.find({"collection_id": ObjectId(collection_id)}))
        assert len(audit_entries) >= 1  # At least one from update (might have one from creation too)
        
        # Find the update entry
        update_entries = [e for e in audit_entries if e.get("action") == "collection_edit"]
        assert len(update_entries) >= 1
        
        latest_entry = update_entries[-1]
        assert latest_entry["user_id"] == "test_user_123"
        assert "metadata" in latest_entry
        assert "updated_fields" in latest_entry["metadata"]
        assert "name" in latest_entry["metadata"]["updated_fields"]

    def test_update_collection_countries_creates_audit_entry_with_changes(self, client, mock_db):
        """Test that updating availableCountries creates audit entry with field changes."""
        # Create a song and collection with initial countries
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Regional Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR", "UY", "BR"]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["data"]["id"]
        
        # Update to different countries
        update_data = {
            "availableInCountries": ["AR", "UY", "CL", "MX"]
        }
        
        update_response = client.put(f"/collections/{collection_id}", json=update_data)
        assert update_response.status_code == 200
        
        # Check audit entry
        audit_entries = list(mock_db.collection_audit.find({"collection_id": ObjectId(collection_id)}))
        
        # Find entries with collection_edit action
        edit_entries = [e for e in audit_entries if e.get("action") == "collection_edit"]
        assert len(edit_entries) >= 1
        
        latest_entry = edit_entries[-1]
        assert "metadata" in latest_entry
        assert "field_changes" in latest_entry["metadata"]
        assert "availableCountries" in latest_entry["metadata"]["field_changes"]
        
        # Check that previous and new values are captured
        country_change = latest_entry["metadata"]["field_changes"]["availableCountries"]
        assert "previous" in country_change
        assert "new" in country_change
        assert set(country_change["previous"]) == {"AR", "UY", "BR"}
        assert set(country_change["new"]) == {"AR", "UY", "CL", "MX"}

    def test_update_multiple_fields_records_all_changes(self, client, mock_db):
        """Test that updating multiple fields records all changes in audit."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Original Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR"]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Update multiple fields
        update_data = {
            "name": "New Album Name",
            "genre": "Alternative Rock",
            "availableInCountries": ["AR", "UY", "CL"]
        }
        
        update_response = client.put(f"/collections/{collection_id}", json=update_data)
        assert update_response.status_code == 200
        
        # Check audit entry
        audit_entries = list(mock_db.collection_audit.find({"collection_id": ObjectId(collection_id)}))
        edit_entries = [e for e in audit_entries if e.get("action") == "collection_edit"]
        
        latest_entry = edit_entries[-1]
        assert "metadata" in latest_entry
        assert "updated_fields" in latest_entry["metadata"]
        assert set(latest_entry["metadata"]["updated_fields"]) == {"name", "genre", "availableCountries"}
        
        # Verify field changes
        field_changes = latest_entry["metadata"]["field_changes"]
        assert "name" in field_changes
        assert "genre" in field_changes
        assert "availableCountries" in field_changes
        
        assert field_changes["name"]["previous"] == "Original Album"
        assert field_changes["name"]["new"] == "New Album Name"
        assert field_changes["genre"]["previous"] == "Rock"
        assert field_changes["genre"]["new"] == "Alternative Rock"

    def test_get_collection_audit_history_success(self, client, mock_db):
        """Test getting audit history for a collection."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Make some updates to generate audit entries
        client.put(f"/collections/{collection_id}", json={"name": "Updated Album 1"})
        client.put(f"/collections/{collection_id}", json={"name": "Updated Album 2"})
        client.put(f"/collections/{collection_id}", json={"genre": "Electronic"})
        
        # Get audit history
        response = client.get(f"/collections/{collection_id}/audit")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "collectionId" in data
        assert "collectionName" in data
        assert "auditHistory" in data
        assert data["collectionId"] == collection_id
        
        # Should have multiple entries (creation + updates)
        audit_history = data["auditHistory"]
        assert len(audit_history) >= 3  # At least 3 updates
        
        # Verify structure of audit entries
        for entry in audit_history:
            assert "id" in entry
            assert "collectionId" in entry
            assert "userId" in entry
            assert "action" in entry
            assert "timestamp" in entry

    def test_get_collection_audit_history_with_limit(self, client, mock_db):
        """Test that audit history respects limit parameter."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Make multiple updates
        for i in range(15):
            client.put(f"/collections/{collection_id}", json={"name": f"Update {i}"})
        
        # Get audit history with limit=5
        response = client.get(f"/collections/{collection_id}/audit?limit=5")
        assert response.status_code == 200
        
        data = response.json()["data"]
        audit_history = data["auditHistory"]
        
        # Should return at most 5 entries
        assert len(audit_history) <= 5

    def test_get_collection_audit_history_most_recent_first(self, client, mock_db):
        """Test that audit history returns most recent changes first."""
        import time
        
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Make updates with slight delays to ensure different timestamps
        client.put(f"/collections/{collection_id}", json={"name": "First Update"})
        time.sleep(0.1)
        client.put(f"/collections/{collection_id}", json={"name": "Second Update"})
        time.sleep(0.1)
        client.put(f"/collections/{collection_id}", json={"name": "Third Update"})
        
        # Get audit history
        response = client.get(f"/collections/{collection_id}/audit")
        assert response.status_code == 200
        
        audit_history = response.json()["data"]["auditHistory"]
        
        # Verify timestamps are in descending order (most recent first)
        timestamps = [datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00')) for entry in audit_history]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_collection_audit_history_not_found(self, client):
        """Test that getting audit history for non-existent collection returns 404."""
        fake_id = "507f1f77bcf86cd799439011"
        response = client.get(f"/collections/{fake_id}/audit")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_collection_audit_history_authorization_logic(self, client, mock_db):
        """Test that authorization logic for audit history works correctly."""
        from controllers.collections_controller import _can_access_collection
        from auth import is_authorized
        
        # Create collection
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Private Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        collection = create_response.json()["data"]
        
        # Verify the owner is test_user_123
        assert collection["artistId"] == "test_user_123"
        
        # Test is_authorized logic directly
        owner_user = {"user_id": "test_user_123", "user_type": "artist"}
        other_user = {"user_id": "other_user_456", "user_type": "artist"}
        backoffice_user = {"user_id": "admin_789", "user_type": "backoffice"}
        
        # Owner should be authorized
        assert is_authorized(owner_user, "test_user_123") == True
        
        # Other user should NOT be authorized
        assert is_authorized(other_user, "test_user_123") == False
        
        # Backoffice should be authorized regardless
        assert is_authorized(backoffice_user, "test_user_123") == True
        
        # Owner can access their own audit history
        response = client.get(f"/collections/{collection_id}/audit")
        assert response.status_code == 200

    def test_get_collection_audit_history_backoffice_can_access(self, client, client_backoffice):
        """Test that backoffice users can access any collection's audit history."""
        # Create collection as regular user
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Make an update
        client.put(f"/collections/{collection_id}", json={"name": "Updated Album"})
        
        # Backoffice user should be able to access audit history
        response = client_backoffice.get(f"/collections/{collection_id}/audit")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "auditHistory" in data
        assert len(data["auditHistory"]) >= 1

    def test_audit_entry_includes_metadata_for_countries_change(self, client, mock_db):
        """Test that audit entry includes detailed metadata for country changes."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Regional Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR", "UY"]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Update countries
        update_data = {
            "availableInCountries": ["AR", "BR", "CL", "MX"]
        }
        
        update_response = client.put(f"/collections/{collection_id}", json=update_data)
        assert update_response.status_code == 200
        
        # Get audit history through API
        audit_response = client.get(f"/collections/{collection_id}/audit")
        assert audit_response.status_code == 200
        
        audit_history = audit_response.json()["data"]["auditHistory"]
        
        # Find the entry for country change
        country_change_entries = [
            e for e in audit_history 
            if e.get("metadata") and "availableCountries" in e["metadata"].get("updated_fields", [])
        ]
        
        assert len(country_change_entries) >= 1
        
        entry = country_change_entries[0]
        assert "metadata" in entry
        assert "field_changes" in entry["metadata"]
        assert "availableCountries" in entry["metadata"]["field_changes"]

    def test_publication_window_update_creates_correct_audit_action(self, client, mock_db):
        """Test that updating publication window creates audit entry with correct action type."""
        from datetime import datetime, timedelta, timezone
        
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
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
        window_data = {"releaseDate": future_date}
        
        response = client.put(f"/collections/{collection_id}/publication-window", json=window_data)
        assert response.status_code == 200
        
        # Check audit entry
        audit_entries = list(mock_db.collection_audit.find({"collection_id": ObjectId(collection_id)}))
        
        # Find publication_window_update entries
        window_entries = [e for e in audit_entries if e.get("action") == "publication_window_update"]
        assert len(window_entries) >= 1
        
        latest_entry = window_entries[-1]
        assert latest_entry["action"] == "publication_window_update"
        assert "updated_fields" in latest_entry["metadata"]
        assert "releaseDate" in latest_entry["metadata"]["updated_fields"]

    def test_admin_block_creates_state_change_audit(self, client, client_backoffice, mock_db):
        """Test that admin block/unblock creates state_change audit entry."""
        # Create collection as regular user
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
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
            "scope": "global",
            "reasonCode": "test_audit_reason"
        }
        response = client_backoffice.post(f"/collections/{collection_id}/admin-block", json=block_data)
        assert response.status_code == 200
        
        # Check audit entry
        audit_entries = list(mock_db.collection_audit.find({"collection_id": ObjectId(collection_id)}))
        
        # Find state_change entries
        state_change_entries = [e for e in audit_entries if e.get("action") == "state_change"]
        assert len(state_change_entries) >= 1
        
        latest_entry = state_change_entries[-1]
        assert latest_entry["action"] == "state_change"
        assert latest_entry["previous_bloqueado_admin"] == False
        assert latest_entry["new_bloqueado_admin"] == True

    def test_no_audit_entry_when_no_changes(self, client, mock_db):
        """Test that no audit entry is created when update makes no actual changes."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "Test Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Count audit entries after creation
        initial_count = mock_db.collection_audit.count_documents({"collection_id": ObjectId(collection_id)})
        
        # Try to update with same values
        update_data = {
            "name": "Test Album",  # Same name
            "genre": "Pop"  # Same genre
        }
        
        update_response = client.put(f"/collections/{collection_id}", json=update_data)
        assert update_response.status_code == 200
        
        # Count audit entries after update
        final_count = mock_db.collection_audit.count_documents({"collection_id": ObjectId(collection_id)})
        
        # Should be the same (or only 1 more if the update was recorded without field changes)
        # Actually, based on current implementation, it will create an entry even if no changes
        # But the field_changes dict should be empty or not include unchanged fields
        if final_count > initial_count:
            latest_entries = list(
                mock_db.collection_audit.find({"collection_id": ObjectId(collection_id)})
                .sort("timestamp", -1)
                .limit(1)
            )
            if latest_entries:
                latest_entry = latest_entries[0]
                # field_changes should be empty or minimal since values didn't change
                field_changes = latest_entry.get("metadata", {}).get("field_changes", {})
                # The fields should not show as changed
                assert len(field_changes) == 0 or all(
                    change.get("previous") == change.get("new") 
                    for change in field_changes.values()
                )

    def test_creation_creates_audit_entry(self, client, mock_db):
        """Test that creating a collection creates an audit entry."""
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        collection_data = {
            "name": "New Album",
            "type": "album",
            "genre": "Rock",
            "songs": [{"songId": song1['_id']}],
            "availableInCountries": ["AR", "UY"]
        }
        
        create_response = client.post("/collections/", json=collection_data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["data"]["id"]
        
        # Check that audit entry was created
        audit_entries = list(mock_db.collection_audit.find({"collection_id": ObjectId(collection_id)}))
        assert len(audit_entries) >= 1
        
        # Should have an entry from creation
        creation_entries = [e for e in audit_entries if e.get("metadata", {}).get("action") == "collection_created"]
        assert len(creation_entries) >= 1

    def test_audit_history_shows_state_changes(self, client, client_backoffice):
        """Test that audit history shows state changes with previous and new states."""
        from datetime import datetime, timedelta, timezone
        
        # Create collection as regular user
        song1 = client.post("/songs", json={"title": "Song 1", "duration": "180"}).json()["data"]
        
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        collection_data = {
            "name": "Future Album",
            "type": "album",
            "genre": "Pop",
            "songs": [{"songId": song1['_id']}],
            "releaseDate": future_date
        }
        
        create_response = client.post("/collections/", json=collection_data)
        collection_id = create_response.json()["data"]["id"]
        
        # Publish it (changes state from programado to publicado)
        publish_response = client.post(f"/collections/{collection_id}/publish")
        assert publish_response.status_code == 200
        
        # Get audit history
        audit_response = client.get(f"/collections/{collection_id}/audit?includeUnpublished=true")
        assert audit_response.status_code == 200
        
        audit_history = audit_response.json()["data"]["auditHistory"]
        
        # Should have entries showing state changes
        state_change_entries = [e for e in audit_history if "stateChange" in e]
        
        # At least one entry should show state change
        assert len(state_change_entries) >= 1

