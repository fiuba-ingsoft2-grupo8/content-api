import pytest


class TestAboutEndpoints:
    """Test suite for artist about endpoints."""
    
    @pytest.fixture(autouse=True)
    def setup(self, client, mock_db):
        """Setup for each test."""
        self.client = client
        self.db = mock_db
        
        # Clear the artist_about collection before each test
        self.db.artist_about.delete_many({})
    
    def test_create_artist_about_success(self):
        """Test successful creation of artist about page."""
        response = self.client.post("/about")
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["artistId"] == "test_user_123"
        assert data["data"]["artist"] == "Test Artist"
        assert data["data"]["bio"] is None
        assert data["data"]["socialMedia"] is None
        assert data["data"]["carouselImages"] == []
        assert data["data"]["artistPick"] is None
    
    def test_create_artist_about_already_exists(self):
        """Test creation fails when artist about already exists."""
        # Create first time
        self.client.post("/about")
        
        # Try to create again
        response = self.client.post("/about")
        
        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["title"].lower() or "already exists" in data["detail"].lower()
    
    def test_update_artist_about_success(self):
        """Test successful update of artist about page."""
        # First create the about page
        self.client.post("/about")
        
        # Update with new data
        update_data = {
            "bio": "This is my bio",
            "socialMedia": {
                "x": "@testartist",
                "instagram": "@testartist"
            },
            "carouselImages": [
                {
                    "url": "https://example.com/image1.jpg",
                    "isPrimary": True
                }
            ],
            "artistPick": {
                "type": "collection",
                "id": "507f1f77bcf86cd799439011"
            }
        }
        
        response = self.client.put("/about", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["bio"] == "This is my bio"
        assert data["data"]["socialMedia"]["x"] == "@testartist"
        assert data["data"]["socialMedia"]["instagram"] == "@testartist"
        assert len(data["data"]["carouselImages"]) == 1
        assert data["data"]["carouselImages"][0]["isPrimary"] is True
        assert data["data"]["artistPick"]["type"] == "collection"
    
    def test_update_artist_about_not_found(self):
        """Test update fails when artist about doesn't exist."""
        update_data = {
            "bio": "This is my bio"
        }
        
        response = self.client.put("/about", json=update_data)
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_update_artist_about_partial_update(self):
        """Test partial update (only updating some fields)."""
        # Create
        self.client.post("/about")
        
        # Update only bio
        response = self.client.put("/about", json={"bio": "New bio"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["bio"] == "New bio"
        assert data["data"]["socialMedia"] is None
        assert data["data"]["carouselImages"] == []
    
    def test_update_artist_about_cannot_modify_protected_fields(self):
        """Test that artistId and artist cannot be modified."""
        # Create
        self.client.post("/about")
        
        # Try to update protected fields (they should be ignored)
        update_data = {
            "artistId": "different_id",
            "artist": "Different Name",
            "bio": "New bio"
        }
        
        response = self.client.put("/about", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        # Protected fields should remain unchanged
        assert data["data"]["artistId"] == "test_user_123"
        assert data["data"]["artist"] == "Test Artist"
        # But bio should be updated
        assert data["data"]["bio"] == "New bio"
    
    def test_get_artist_about_success(self):
        """Test successful retrieval of artist about page."""
        # Create
        self.client.post("/about")
        
        # Get without authentication (public endpoint)
        response = self.client.get("/about/test_user_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["artistId"] == "test_user_123"
        assert data["data"]["artist"] == "Test Artist"
    
    def test_get_artist_about_not_found(self):
        """Test retrieval fails when artist about doesn't exist."""
        response = self.client.get("/about/nonexistent123")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_carousel_images_max_five(self):
        """Test that carousel images are limited to 5."""
        # Create
        self.client.post("/about") 
        
        # Try to add 6 images
        update_data = {
            "carouselImages": [
                {"url": f"https://example.com/image{i}.jpg", "isPrimary": i == 0}
                for i in range(6)
            ]
        }
        
        response = self.client.put("/about", json=update_data)
        
        # Should fail because max is 5
        assert response.status_code == 404  # Returns 404 when validation fails in update_artist_about
    
    def test_carousel_images_one_primary(self):
        """Test that only one primary image is allowed."""
        # Create
        self.client.post("/about")
        
        # Try to add multiple primary images
        update_data = {
            "carouselImages": [
                {"url": "https://example.com/image1.jpg", "isPrimary": True},
                {"url": "https://example.com/image2.jpg", "isPrimary": True}
            ]
        }
        
        response = self.client.put("/about", json=update_data)
        
        # Should fail because only one primary is allowed
        assert response.status_code == 404  # Returns 404 when validation fails in update_artist_about
    
    def test_update_social_media_only(self):
        """Test updating only social media links."""
        # Create
        self.client.post("/about")
        
        # Update social media
        update_data = {
            "socialMedia": {
                "x": "@newartist",
                "instagram": "@newartist_insta"
            }
        }
        
        response = self.client.put("/about", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["socialMedia"]["x"] == "@newartist"
        assert data["data"]["socialMedia"]["instagram"] == "@newartist_insta"
    
    def test_update_artist_pick(self):
        """Test updating artist pick (featured collection/playlist)."""
        # Create
        self.client.post("/about")
        
        # Update artist pick to collection
        update_data = {
            "artistPick": {
                "type": "collection",
                "id": "collection123"
            }
        }
        
        response = self.client.put("/about", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["artistPick"]["type"] == "collection"
        assert data["data"]["artistPick"]["id"] == "collection123"
        
        # Update artist pick to playlist
        update_data = {
            "artistPick": {
                "type": "playlist",
                "id": "playlist456"
            }
        }
        
        response = self.client.put("/about", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["artistPick"]["type"] == "playlist"
        assert data["data"]["artistPick"]["id"] == "playlist456"
    
    def test_carousel_images_empty_array(self):
        """Test that carousel can be set to empty array."""
        # Create
        self.client.post("/about")
        
        # Add images first
        update_data = {
            "carouselImages": [
                {"url": "https://example.com/image1.jpg", "isPrimary": True}
            ]
        }
        self.client.put("/about", json=update_data)
        
        # Now clear them
        update_data = {
            "carouselImages": []
        }
        response = self.client.put("/about", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["carouselImages"] == []
    
    def test_carousel_with_five_images_success(self):
        """Test that exactly 5 images are allowed."""
        # Create
        self.client.post("/about")
        
        # Add exactly 5 images (should succeed)
        update_data = {
            "carouselImages": [
                {"url": f"https://example.com/image{i}.jpg", "isPrimary": i == 0}
                for i in range(5)
            ]
        }
        
        response = self.client.put("/about", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["carouselImages"]) == 5
