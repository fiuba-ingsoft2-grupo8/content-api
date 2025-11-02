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
