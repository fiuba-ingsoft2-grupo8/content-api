import pytest


class TestHealthEndpoint:
    """Test suite for health check endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Setup for each test."""
        self.client = client
    
    def test_health_check_returns_200(self):
        """Test that health check endpoint returns 200."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
    
    def test_health_check_no_authentication_required(self):
        """Test that health check doesn't require authentication."""
        # Should work without any authorization header
        response = self.client.get("/health")
        
        assert response.status_code == 200

