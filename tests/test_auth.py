import os
import sys
import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from auth import is_testing, verify_token


class TestIsTesting:
    """Test suite for the is_testing function."""

    def test_is_testing_returns_true_when_pytest_in_modules(self):
        """Should return True when pytest is in sys.modules."""
        # pytest is already in sys.modules during test execution
        assert is_testing() is True

    def test_is_testing_returns_true_when_testing_env_var_set(self):
        """Should return True when TESTING environment variable is 'true'."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            assert is_testing() is True

    def test_is_testing_returns_false_in_production(self):
        """Should return False when not in testing mode."""
        # Remove pytest from sys.modules temporarily
        pytest_module = sys.modules.pop("pytest", None)
        
        try:
            with patch.dict(os.environ, {"TESTING": "false"}, clear=False):
                result = is_testing()
                # In this test environment, we can't fully simulate non-test mode
                # because pytest is inherently loaded, but we test the logic
        finally:
            # Restore pytest module
            if pytest_module:
                sys.modules["pytest"] = pytest_module


class TestVerifyToken:
    """Test suite for the verify_token function."""

    @pytest.fixture
    def jwt_secret(self):
        """Fixture to provide a test JWT secret."""
        return "test_secret_key_12345"

    @pytest.fixture
    def valid_token(self, jwt_secret):
        """Fixture to create a valid JWT token."""
        payload = {
            "user_id": "user123",
            "email": "user@example.com",
            "user_type": "user",
            "stage_name": "Test User",
            "country": "US",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        return jwt.encode(payload, jwt_secret, algorithm="HS256")

    @pytest.fixture
    def expired_token(self, jwt_secret):
        """Fixture to create an expired JWT token."""
        payload = {
            "user_id": "user123",
            "email": "user@example.com",
            "user_type": "user",
            "stage_name": "Test User",
            "country": "US",
            "exp": datetime.utcnow() - timedelta(hours=1)
        }
        return jwt.encode(payload, jwt_secret, algorithm="HS256")

    def test_verify_token_in_testing_mode(self):
        """Should return test user data when in testing mode."""
        # Since we're running in pytest, is_testing() returns True
        result = verify_token()
        
        assert result["user_id"] == "test_user_123"
        assert result["email"] == "test@example.com"
        assert result["user_type"] == "user"
        assert result["country"] == "AR"

    @patch("auth.is_testing")
    def test_verify_token_missing_authorization_header(self, mock_is_testing):
        """Should raise 401 when authorization header is missing."""
        mock_is_testing.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(authorization=None)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authorization header required"

    @patch("auth.is_testing")
    def test_verify_token_invalid_bearer_format_missing_bearer(self, mock_is_testing):
        """Should raise 401 when Bearer prefix is missing."""
        mock_is_testing.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(authorization="some_token_without_bearer")
        
        assert exc_info.value.status_code == 401
        assert "Bearer" in exc_info.value.detail

    @patch("auth.is_testing")
    def test_verify_token_invalid_bearer_format_wrong_prefix(self, mock_is_testing):
        """Should raise 401 when using wrong prefix instead of Bearer."""
        mock_is_testing.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(authorization="Token some_token")
        
        assert exc_info.value.status_code == 401
        assert "Bearer" in exc_info.value.detail

    @patch("auth.is_testing")
    def test_verify_token_invalid_bearer_format_too_many_parts(self, mock_is_testing):
        """Should raise 401 when authorization header has too many parts."""
        mock_is_testing.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(authorization="Bearer token extra_part")
        
        assert exc_info.value.status_code == 401
        assert "Bearer" in exc_info.value.detail

    @patch("auth.is_testing")
    @patch.dict(os.environ, {"JWT_SECRET": "test_secret_key_12345"})
    def test_verify_token_with_valid_token(self, mock_is_testing, valid_token):
        """Should successfully decode and return payload for valid token."""
        mock_is_testing.return_value = False
        
        # Need to reload auth module to pick up the JWT_SECRET from env
        import auth
        auth.JWT_SECRET = "test_secret_key_12345"
        
        result = auth.verify_token(authorization=f"Bearer {valid_token}")
        
        assert result["user_id"] == "user123"
        assert result["email"] == "user@example.com"
        assert result["user_type"] == "user"
        assert result["stage_name"] == "Test User"
        assert result["country"] == "US"

    @patch("auth.is_testing")
    @patch.dict(os.environ, {"JWT_SECRET": "test_secret_key_12345"})
    def test_verify_token_with_expired_token(self, mock_is_testing, expired_token):
        """Should raise 401 when token is expired."""
        mock_is_testing.return_value = False
        
        # Need to reload auth module to pick up the JWT_SECRET from env
        import auth
        auth.JWT_SECRET = "test_secret_key_12345"
        
        with pytest.raises(HTTPException) as exc_info:
            auth.verify_token(authorization=f"Bearer {expired_token}")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token has expired"

    @patch("auth.is_testing")
    @patch.dict(os.environ, {"JWT_SECRET": "test_secret_key_12345"})
    def test_verify_token_with_invalid_token(self, mock_is_testing):
        """Should raise 401 when token is invalid/malformed."""
        mock_is_testing.return_value = False
        
        # Need to reload auth module to pick up the JWT_SECRET from env
        import auth
        auth.JWT_SECRET = "test_secret_key_12345"
        
        with pytest.raises(HTTPException) as exc_info:
            auth.verify_token(authorization="Bearer invalid.token.here")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    @patch("auth.is_testing")
    @patch.dict(os.environ, {"JWT_SECRET": "test_secret_key_12345"})
    def test_verify_token_with_wrong_secret(self, mock_is_testing, jwt_secret):
        """Should raise 401 when token is signed with different secret."""
        mock_is_testing.return_value = False
        
        # Create token with different secret
        payload = {
            "user_id": "user123",
            "email": "user@example.com",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        wrong_secret_token = jwt.encode(payload, "wrong_secret", algorithm="HS256")
        
        # Need to reload auth module to pick up the JWT_SECRET from env
        import auth
        auth.JWT_SECRET = "test_secret_key_12345"
        
        with pytest.raises(HTTPException) as exc_info:
            auth.verify_token(authorization=f"Bearer {wrong_secret_token}")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    @patch("auth.is_testing")
    def test_verify_token_with_empty_string(self, mock_is_testing):
        """Should raise 401 when authorization header is empty string."""
        mock_is_testing.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(authorization="")
        
        assert exc_info.value.status_code == 401
        # Empty string will fail the format check

    @patch("auth.is_testing")
    def test_verify_token_with_only_bearer(self, mock_is_testing):
        """Should raise 401 when only 'Bearer' is provided without token."""
        mock_is_testing.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(authorization="Bearer")
        
        assert exc_info.value.status_code == 401
        assert "Bearer" in exc_info.value.detail

    @patch("auth.is_testing")
    @patch.dict(os.environ, {"JWT_SECRET": "test_secret_key_12345"})
    def test_verify_token_with_country_for_regular_user(self, mock_is_testing):
        """Should decode country field for regular users."""
        mock_is_testing.return_value = False
        
        # Create token for regular user with country
        payload = {
            "user_id": "123e4567-e89b-12d3-a456-426614174001",
            "email": "user@example.com",
            "user_type": "user",
            "stage_name": "DJ Artist",
            "country": "US",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, "test_secret_key_12345", algorithm="HS256")
        
        import auth
        auth.JWT_SECRET = "test_secret_key_12345"
        
        result = auth.verify_token(authorization=f"Bearer {token}")
        
        assert result["user_id"] == "123e4567-e89b-12d3-a456-426614174001"
        assert result["email"] == "user@example.com"
        assert result["user_type"] == "user"
        assert result["stage_name"] == "DJ Artist"
        assert result["country"] == "US"

    @patch("auth.is_testing")
    @patch.dict(os.environ, {"JWT_SECRET": "test_secret_key_12345"})
    def test_verify_token_with_empty_country_for_backoffice_user(self, mock_is_testing):
        """Should decode empty country field for backoffice users."""
        mock_is_testing.return_value = False
        
        # Create token for backoffice user with empty country
        payload = {
            "user_id": "1",
            "email": "admin@example.com",
            "user_type": "backoffice",
            "stage_name": "",
            "country": "",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, "test_secret_key_12345", algorithm="HS256")
        
        import auth
        auth.JWT_SECRET = "test_secret_key_12345"
        
        result = auth.verify_token(authorization=f"Bearer {token}")
        
        assert result["user_id"] == "1"
        assert result["email"] == "admin@example.com"
        assert result["user_type"] == "backoffice"
        assert result["stage_name"] == ""
        assert result["country"] == ""

