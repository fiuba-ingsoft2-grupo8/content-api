import pytest
import io


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
                    "id": "test-id-1",
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
                {"id": f"test-id-{i}", "url": f"https://example.com/image{i}.jpg", "isPrimary": i == 0}
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
                {"id": "test-id-1", "url": "https://example.com/image1.jpg", "isPrimary": True},
                {"id": "test-id-2", "url": "https://example.com/image2.jpg", "isPrimary": True}
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
                {"id": "test-id-1", "url": "https://example.com/image1.jpg", "isPrimary": True}
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
                {"id": f"test-id-{i}", "url": f"https://example.com/image{i}.jpg", "isPrimary": i == 0}
                for i in range(5)
            ]
        }
        
        response = self.client.put("/about", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["carouselImages"]) == 5


class TestCarouselImageUpload:
    """Test suite for carousel image upload endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self, client, mock_db):
        """Setup for each test."""
        self.client = client
        self.db = mock_db
        
        # Clear the artist_about collection before each test
        self.db.artist_about.delete_many({})
    
    def create_test_image(self):
        """Helper to create a test image file."""
        # Create a simple test image (1x1 pixel PNG)
        image_bytes = io.BytesIO(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        return ("test_image.png", image_bytes, "image/png")
    
    def test_upload_first_carousel_image_success(self):
        """Test uploading the first carousel image (should be marked as primary)."""
        # Create about page first
        self.client.post("/about")
        
        # Upload first image
        image_file = self.create_test_image()
        response = self.client.post(
            "/about/carousel",
            files={"file": image_file}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["imageNumber"] == 1
        assert data["data"]["isPrimary"] is True
        assert data["data"]["totalImages"] == 1
        assert "imageUrl" in data["data"]
        assert "imageId" in data["data"]
        assert len(data["data"]["imageId"]) > 0  # UUID should not be empty
    
    def test_upload_second_carousel_image_not_primary(self):
        """Test that second image is not marked as primary."""
        # Create about page and add first image
        self.client.post("/about")
        self.client.post("/about/carousel", files={"file": self.create_test_image()})
        
        # Upload second image
        response = self.client.post(
            "/about/carousel",
            files={"file": self.create_test_image()}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["data"]["imageNumber"] == 2
        assert data["data"]["isPrimary"] is False
        assert data["data"]["totalImages"] == 2
    
    def test_upload_carousel_image_without_about_page(self):
        """Test that upload fails if about page doesn't exist."""
        response = self.client.post(
            "/about/carousel",
            files={"file": self.create_test_image()}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_upload_carousel_image_max_five(self):
        """Test that uploading more than 5 images fails."""
        # Create about page
        self.client.post("/about")
        
        # Upload 5 images
        for i in range(5):
            response = self.client.post(
                "/about/carousel",
                files={"file": self.create_test_image()}
            )
            assert response.status_code == 201
        
        # Try to upload 6th image
        response = self.client.post(
            "/about/carousel",
            files={"file": self.create_test_image()}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "maximum" in data["detail"].lower() or "5" in data["detail"]
    
    def test_upload_carousel_image_updates_about_page(self):
        """Test that uploading image updates the about page with the carousel."""
        # Create about page
        self.client.post("/about")
        
        # Upload image
        self.client.post(
            "/about/carousel",
            files={"file": self.create_test_image()}
        )
        
        # Get about page and verify carousel was updated
        response = self.client.get("/about/test_user_123")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["carouselImages"]) == 1
        assert data["data"]["carouselImages"][0]["isPrimary"] is True
    
    def test_upload_multiple_carousel_images_correct_numbering(self):
        """Test that multiple uploads have correct numbering."""
        # Create about page
        self.client.post("/about")
        
        # Upload 3 images
        for expected_num in range(1, 4):
            response = self.client.post(
                "/about/carousel",
                files={"file": self.create_test_image()}
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["data"]["imageNumber"] == expected_num
            assert data["data"]["totalImages"] == expected_num


class TestSetPrimaryCarouselImage:
    """Test suite for setting primary carousel image endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self, client, mock_db):
        """Setup for each test."""
        self.client = client
        self.db = mock_db
        
        # Clear the artist_about collection before each test
        self.db.artist_about.delete_many({})
    
    def create_test_image(self):
        """Helper to create a test image file."""
        image_bytes = io.BytesIO(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        return ("test_image.png", image_bytes, "image/png")
    
    def test_set_primary_image_success(self):
        """Test successfully setting a new primary image."""
        # Create about page
        self.client.post("/about")
        
        # Upload 3 images
        image_ids = []
        for i in range(3):
            response = self.client.post(
                "/about/carousel",
                files={"file": self.create_test_image()}
            )
            image_ids.append(response.json()["data"]["imageId"])
        
        # Set the third image as primary
        response = self.client.put(f"/about/carousel/primary/{image_ids[2]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify only the third image is primary
        carousel = data["data"]["carouselImages"]
        assert len(carousel) == 3
        assert carousel[0]["isPrimary"] is False
        assert carousel[1]["isPrimary"] is False
        assert carousel[2]["isPrimary"] is True
        assert carousel[2]["id"] == image_ids[2]
    
    def test_set_primary_image_without_about_page(self):
        """Test that setting primary fails if about page doesn't exist."""
        response = self.client.put("/about/carousel/primary/fake-id-123")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_set_primary_image_with_invalid_id(self):
        """Test that setting primary fails with invalid image ID."""
        # Create about page and upload an image
        self.client.post("/about")
        self.client.post("/about/carousel", files={"file": self.create_test_image()})
        
        # Try to set a non-existent image as primary
        response = self.client.put("/about/carousel/primary/invalid-id-999")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_set_primary_image_with_no_carousel(self):
        """Test that setting primary fails when carousel is empty."""
        # Create about page without images
        self.client.post("/about")
        
        response = self.client.put("/about/carousel/primary/any-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "no carousel images" in data["detail"].lower() or "not found" in data["detail"].lower()
    
    def test_set_primary_only_one_primary_at_time(self):
        """Test that only one image can be primary at a time."""
        # Create about page
        self.client.post("/about")
        
        # Upload 2 images
        response1 = self.client.post("/about/carousel", files={"file": self.create_test_image()})
        image_id_1 = response1.json()["data"]["imageId"]
        
        response2 = self.client.post("/about/carousel", files={"file": self.create_test_image()})
        image_id_2 = response2.json()["data"]["imageId"]
        
        # First image should be primary initially
        about = self.client.get("/about/test_user_123").json()
        assert about["data"]["carouselImages"][0]["isPrimary"] is True
        assert about["data"]["carouselImages"][1]["isPrimary"] is False
        
        # Set second image as primary
        self.client.put(f"/about/carousel/primary/{image_id_2}")
        
        # Verify first is no longer primary
        about = self.client.get("/about/test_user_123").json()
        assert about["data"]["carouselImages"][0]["isPrimary"] is False
        assert about["data"]["carouselImages"][1]["isPrimary"] is True
        
        # Set first image as primary again
        self.client.put(f"/about/carousel/primary/{image_id_1}")
        
        # Verify second is no longer primary
        about = self.client.get("/about/test_user_123").json()
        assert about["data"]["carouselImages"][0]["isPrimary"] is True
        assert about["data"]["carouselImages"][1]["isPrimary"] is False


class TestDeleteCarouselImage:
    """Test suite for deleting carousel images endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self, client, mock_db):
        """Setup for each test."""
        self.client = client
        self.db = mock_db
        
        # Clear the artist_about collection before each test
        self.db.artist_about.delete_many({})
    
    def create_test_image(self):
        """Helper to create a test image file."""
        image_bytes = io.BytesIO(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        return ("test_image.png", image_bytes, "image/png")
    
    def test_delete_carousel_image_success(self):
        """Test successfully deleting a carousel image."""
        # Create about page
        self.client.post("/about")
        
        # Upload 3 images
        image_ids = []
        for i in range(3):
            response = self.client.post(
                "/about/carousel",
                files={"file": self.create_test_image()}
            )
            image_ids.append(response.json()["data"]["imageId"])
        
        # Delete the second image
        response = self.client.delete(f"/about/carousel/{image_ids[1]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deletedImageId"] == image_ids[1]
        assert data["data"]["remainingImages"] == 2
        
        # Verify the image was deleted
        about = self.client.get("/about/test_user_123").json()
        carousel = about["data"]["carouselImages"]
        assert len(carousel) == 2
        assert image_ids[1] not in [img["id"] for img in carousel]
    
    def test_delete_primary_image_sets_new_primary(self):
        """Test that deleting primary image sets the first remaining as primary."""
        # Create about page
        self.client.post("/about")
        
        # Upload 3 images (first one is primary)
        image_ids = []
        for i in range(3):
            response = self.client.post(
                "/about/carousel",
                files={"file": self.create_test_image()}
            )
            image_ids.append(response.json()["data"]["imageId"])
        
        # Verify first is primary
        about = self.client.get("/about/test_user_123").json()
        assert about["data"]["carouselImages"][0]["isPrimary"] is True
        
        # Delete the first (primary) image
        response = self.client.delete(f"/about/carousel/{image_ids[0]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["newPrimarySet"] is True
        
        # Verify the new first image is now primary
        about = self.client.get("/about/test_user_123").json()
        carousel = about["data"]["carouselImages"]
        assert len(carousel) == 2
        assert carousel[0]["isPrimary"] is True
        assert carousel[0]["id"] == image_ids[1]  # Originally second image
    
    def test_delete_non_primary_image_keeps_primary(self):
        """Test that deleting non-primary image doesn't affect primary."""
        # Create about page
        self.client.post("/about")
        
        # Upload 3 images
        image_ids = []
        for i in range(3):
            response = self.client.post(
                "/about/carousel",
                files={"file": self.create_test_image()}
            )
            image_ids.append(response.json()["data"]["imageId"])
        
        # Delete a non-primary image
        response = self.client.delete(f"/about/carousel/{image_ids[2]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["newPrimarySet"] is False
        
        # Verify first image is still primary
        about = self.client.get("/about/test_user_123").json()
        carousel = about["data"]["carouselImages"]
        assert len(carousel) == 2
        assert carousel[0]["isPrimary"] is True
        assert carousel[0]["id"] == image_ids[0]
    
    def test_delete_last_image_empties_carousel(self):
        """Test that deleting the last image results in empty carousel."""
        # Create about page
        self.client.post("/about")
        
        # Upload 1 image
        response = self.client.post(
            "/about/carousel",
            files={"file": self.create_test_image()}
        )
        image_id = response.json()["data"]["imageId"]
        
        # Delete the only image
        response = self.client.delete(f"/about/carousel/{image_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["remainingImages"] == 0
        assert data["data"]["newPrimarySet"] is False  # No images left to set as primary
        
        # Verify carousel is empty
        about = self.client.get("/about/test_user_123").json()
        assert about["data"]["carouselImages"] == []
    
    def test_delete_image_without_about_page(self):
        """Test that deleting fails if about page doesn't exist."""
        response = self.client.delete("/about/carousel/fake-id-123")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_delete_image_with_invalid_id(self):
        """Test that deleting fails with invalid image ID."""
        # Create about page and upload an image
        self.client.post("/about")
        self.client.post("/about/carousel", files={"file": self.create_test_image()})
        
        # Try to delete a non-existent image
        response = self.client.delete("/about/carousel/invalid-id-999")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_delete_image_from_empty_carousel(self):
        """Test that deleting fails when carousel is empty."""
        # Create about page without images
        self.client.post("/about")
        
        response = self.client.delete("/about/carousel/any-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "no carousel images" in data["detail"].lower() or "not found" in data["detail"].lower()
    
    def test_delete_multiple_images_in_sequence(self):
        """Test deleting multiple images one by one."""
        # Create about page
        self.client.post("/about")
        
        # Upload 5 images
        image_ids = []
        for i in range(5):
            response = self.client.post(
                "/about/carousel",
                files={"file": self.create_test_image()}
            )
            image_ids.append(response.json()["data"]["imageId"])
        
        # Delete 3 images
        for i in [1, 3, 4]:
            response = self.client.delete(f"/about/carousel/{image_ids[i]}")
            assert response.status_code == 200
        
        # Verify only 2 images remain
        about = self.client.get("/about/test_user_123").json()
        carousel = about["data"]["carouselImages"]
        assert len(carousel) == 2
        remaining_ids = [img["id"] for img in carousel]
        assert image_ids[0] in remaining_ids
        assert image_ids[2] in remaining_ids


class TestArtistAppearsIn:
    """Test suite for artist appears-in endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self, client, mock_db):
        """Setup for each test."""
        from datetime import datetime, timezone
        from bson import ObjectId
        
        self.client = client
        self.db = mock_db
        
        # Clear collections
        self.db.artist_about.delete_many({})
        self.db.collections.delete_many({})
        self.db.playlists.delete_many({})
        self.db.songs.delete_many({})
        self.db.playlist_songs.delete_many({})
        
        # Create artist about page
        self.db.artist_about.insert_one({
            "artist_id": "test_user_123",
            "artist": "Test Artist",
            "bio": None,
            "social_media": None,
            "carousel_images": [],
            "artist_pick": None
        })
        
        # Create some songs by the artist
        self.song1_id = ObjectId()
        self.song2_id = ObjectId()
        self.song3_id = ObjectId()
        
        self.db.songs.insert_many([
            {
                "_id": self.song1_id,
                "title": "Song 1",
                "artist": "Test Artist",
                "artistId": "test_user_123",
                "duration": "180"
            },
            {
                "_id": self.song2_id,
                "title": "Song 2",
                "artist": "Test Artist",
                "artistId": "test_user_123",
                "duration": "200"
            },
            {
                "_id": self.song3_id,
                "title": "Song 3",
                "artist": "Other Artist",
                "artistId": "other_user_456",
                "duration": "220"
            }
        ])
        
        # Create collections (albums, EPs, singles)
        now = datetime.now(timezone.utc)
        
        # Album where artist is main artist
        self.collection1_id = ObjectId()
        self.db.collections.insert_one({
            "_id": self.collection1_id,
            "name": "Test Album",
            "artistId": "test_user_123",
            "artistName": "Test Artist",
            "type": "album",
            "genre": "Rock",
            "coverUrl": "https://example.com/album.jpg",
            "releaseDate": datetime(2023, 6, 15, tzinfo=timezone.utc),
            "credits": [],
            "availableCountries": []
        })
        
        # Single where artist is in credits
        self.collection2_id = ObjectId()
        self.db.collections.insert_one({
            "_id": self.collection2_id,
            "name": "Featured Single",
            "artistId": "other_user_456",
            "artistName": "Other Artist",
            "type": "single",
            "genre": "Pop",
            "coverUrl": "https://example.com/single.jpg",
            "releaseDate": datetime(2024, 1, 10, tzinfo=timezone.utc),
            "credits": ["Test Artist", "Another Artist"],
            "availableCountries": []
        })
        
        # EP where artist is main artist
        self.collection3_id = ObjectId()
        self.db.collections.insert_one({
            "_id": self.collection3_id,
            "name": "Test EP",
            "artistId": "test_user_123",
            "artistName": "Test Artist",
            "type": "ep",
            "genre": "Electronic",
            "coverUrl": "https://example.com/ep.jpg",
            "releaseDate": datetime(2024, 3, 20, tzinfo=timezone.utc),
            "credits": [],
            "availableCountries": []
        })
        
        # Unpublished album (shouldn't appear)
        self.collection4_id = ObjectId()
        self.db.collections.insert_one({
            "_id": self.collection4_id,
            "name": "Future Album",
            "artistId": "test_user_123",
            "artistName": "Test Artist",
            "type": "album",
            "genre": "Rock",
            "coverUrl": "https://example.com/future.jpg",
            "releaseDate": datetime(2025, 12, 31, tzinfo=timezone.utc),
            "credits": [],
            "availableCountries": []
        })
        
        # Create public playlists containing artist's songs
        self.playlist1_id = ObjectId()
        self.db.playlists.insert_one({
            "_id": self.playlist1_id,
            "name": "Rock Playlist",
            "description": "Rock music",
            "is_published": True,
            "published_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "userId": "other_user_789",
            "coverUrl": "https://example.com/playlist1.jpg",
            "isLikedSongs": False,
            "isMix": False
        })
        
        # Add artist's songs to playlist
        self.db.playlist_songs.insert_many([
            {
                "_id": ObjectId(),
                "playlist_id": self.playlist1_id,
                "song_id": self.song1_id,
                "added_at": datetime.now(timezone.utc),
                "order": 1
            },
            {
                "_id": ObjectId(),
                "playlist_id": self.playlist1_id,
                "song_id": self.song2_id,
                "added_at": datetime.now(timezone.utc),
                "order": 2
            }
        ])
        
        # Private playlist (shouldn't appear)
        self.playlist2_id = ObjectId()
        self.db.playlists.insert_one({
            "_id": self.playlist2_id,
            "name": "Private Playlist",
            "description": "Private",
            "is_published": False,
            "published_at": datetime(2024, 2, 1, tzinfo=timezone.utc),
            "userId": "other_user_789",
            "coverUrl": "https://example.com/playlist2.jpg",
            "isLikedSongs": False,
            "isMix": False
        })
        
        self.db.playlist_songs.insert_one({
            "_id": ObjectId(),
            "playlist_id": self.playlist2_id,
            "song_id": self.song1_id,
            "added_at": datetime.now(timezone.utc),
            "order": 1
        })
        
        # Mix playlist (shouldn't appear)
        self.playlist3_id = ObjectId()
        self.db.playlists.insert_one({
            "_id": self.playlist3_id,
            "name": "Daily Mix",
            "description": "Auto mix",
            "is_published": True,
            "published_at": datetime(2024, 2, 15, tzinfo=timezone.utc),
            "userId": "test_user_123",
            "coverUrl": "https://example.com/mix.jpg",
            "isLikedSongs": False,
            "isMix": True
        })
        
        self.db.playlist_songs.insert_one({
            "_id": ObjectId(),
            "playlist_id": self.playlist3_id,
            "song_id": self.song1_id,
            "added_at": datetime.now(timezone.utc),
            "order": 1
        })
    
    def test_get_artist_appears_in_success(self):
        """Test successful retrieval of artist appearances."""
        response = self.client.get("/about/appears-in/test_user_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "collections" in data["data"]
        assert "playlists" in data["data"]
        
        # Should have 3 collections (not the unpublished one)
        collections = data["data"]["collections"]
        assert len(collections) == 3
        
        # Verify collections are sorted by release date descending
        collection_names = [c["name"] for c in collections]
        assert "Test EP" == collections[0]["name"]  # Most recent
        assert "Featured Single" == collections[1]["name"]
        assert "Test Album" == collections[2]["name"]  # Oldest
        
        # Should have 1 public playlist (not private or mix)
        playlists = data["data"]["playlists"]
        assert len(playlists) == 1
        assert playlists[0]["name"] == "Rock Playlist"
        assert playlists[0]["type"] == "playlist"
    
    def test_get_artist_appears_in_with_limit(self):
        """Test limit parameter works correctly."""
        response = self.client.get("/about/appears-in/test_user_123?limit=4")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should respect the limit (max 4 items total)
        total_items = len(data["data"]["collections"]) + len(data["data"]["playlists"])
        assert total_items <= 4
    
    def test_get_artist_appears_in_no_about_page(self):
        """Test error when artist has no about page."""
        response = self.client.get("/about/appears-in/nonexistent_user")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_get_artist_appears_in_collection_fields(self):
        """Test that collection items have all required fields."""
        response = self.client.get("/about/appears-in/test_user_123")
        
        assert response.status_code == 200
        data = response.json()
        
        collections = data["data"]["collections"]
        assert len(collections) > 0
        
        # Check first collection has all fields
        collection = collections[0]
        assert "id" in collection
        assert "name" in collection
        assert "artistName" in collection
        assert "coverUrl" in collection
        assert "type" in collection
        assert "year" in collection
        assert collection["type"] in ["album", "ep", "single"]
        assert isinstance(collection["year"], int)
    
    def test_get_artist_appears_in_playlist_fields(self):
        """Test that playlist items have all required fields."""
        response = self.client.get("/about/appears-in/test_user_123")
        
        assert response.status_code == 200
        data = response.json()
        
        playlists = data["data"]["playlists"]
        assert len(playlists) > 0
        
        # Check first playlist has all fields
        playlist = playlists[0]
        assert "id" in playlist
        assert "name" in playlist
        assert "coverUrl" in playlist
        assert "type" in playlist
        assert "year" in playlist
        assert playlist["type"] == "playlist"
        assert isinstance(playlist["year"], int)
    
    def test_get_artist_appears_in_only_published_collections(self):
        """Test that only published collections are returned."""
        response = self.client.get("/about/appears-in/test_user_123")
        
        assert response.status_code == 200
        data = response.json()
        
        collections = data["data"]["collections"]
        collection_names = [c["name"] for c in collections]
        
        # Should not include unpublished "Future Album"
        assert "Future Album" not in collection_names
    
    def test_get_artist_appears_in_only_public_playlists(self):
        """Test that only public playlists are returned."""
        response = self.client.get("/about/appears-in/test_user_123")
        
        assert response.status_code == 200
        data = response.json()
        
        playlists = data["data"]["playlists"]
        playlist_names = [p["name"] for p in playlists]
        
        # Should not include private or mix playlists
        assert "Private Playlist" not in playlist_names
        assert "Daily Mix" not in playlist_names
    
    def test_get_artist_appears_in_includes_credits(self):
        """Test that collections where artist is in credits are included."""
        response = self.client.get("/about/appears-in/test_user_123")
        
        assert response.status_code == 200
        data = response.json()
        
        collections = data["data"]["collections"]
        collection_names = [c["name"] for c in collections]
        
        # Should include "Featured Single" where artist is in credits
        assert "Featured Single" in collection_names
