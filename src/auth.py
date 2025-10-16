import os
import jwt
from fastapi import HTTPException, Header
from typing import Optional

JWT_SECRET = os.getenv("JWT_SECRET")

def verify_token(authorization: Optional[str] = Header(None)):
    """
    Dependency to verify JWT token
    """
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
