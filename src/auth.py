import os
import sys
import jwt
from fastapi import HTTPException, Header
from typing import Optional

JWT_SECRET = os.getenv("JWT_SECRET")

def is_testing():
    """Check if we're currently running tests."""
    return "pytest" in sys.modules or os.getenv("TESTING") == "true"

def is_authorized(user: dict, resource_owner_id: str) -> bool:
    """
    Check if user is authorized to perform an action on a resource.
    Returns True if:
    - User is a backoffice user (user_type == "backoffice"), OR
    - User is the owner of the resource (user_id == resource_owner_id)
    """
    return user.get("user_type") == "backoffice" or user.get("user_id") == resource_owner_id

def verify_token(authorization: Optional[str] = Header(None)):
    """
    Dependency to verify JWT token
    """
    # Skip authentication during testing
    # Check if there's a TEST_USER environment variable set (for testing with different users)
    if is_testing():
        test_user = os.getenv("TEST_USER")
        if test_user:
            # Parse test user from environment (format: user_id:user_type:stage_name:country)
            parts = test_user.split(":")
            return {
                "user_id": parts[0] if len(parts) > 0 else "test_user_123",
                "email": "test@example.com",
                "user_type": parts[1] if len(parts) > 1 else "user",
                "stage_name": parts[2] if len(parts) > 2 else "Test Artist",
                "country": parts[3] if len(parts) > 3 else "AR"
            }
        # Default test user
        return {
            "user_id": "test_user_123",
            "email": "test@example.com",
            "user_type": "user",
            "stage_name": "Test Artist",
            "country": "AR"
        }
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    # Check Bearer format
    parts = authorization.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(
            status_code=401, 
            detail="Authorization header must be in format: Bearer <token>"
        )
    
    token = parts[1]
    
    try:
        # Verify token
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")