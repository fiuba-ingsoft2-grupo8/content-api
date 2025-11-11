from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional

import databases.activity_database as activity_db
import schemas
from auth import verify_token
from common.utils import create_error_response
from resources.logger import logger

router = APIRouter()


@router.get(
    "/{user_id}",
    responses={
        200: {
            "description": "User activity feed",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "type": "like",
                                "userId": "user_123",
                                "targetId": "507f1f77bcf86cd799439011",
                                "targetType": "song",
                                "timestamp": "2025-11-10T14:30:00Z",
                                "createdAt": "2025-11-10T14:30:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439011",
                                    "title": "Bohemian Rhapsody",
                                    "artist": "Queen",
                                    "coverUrl": "https://example.com/cover.jpg"
                                }
                            },
                            {
                                "type": "play",
                                "userId": "user_123",
                                "songId": "507f1f77bcf86cd799439012",
                                "targetType": "song",
                                "timestamp": "2025-11-10T13:15:00Z",
                                "playedAt": "2025-11-10T13:15:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439012",
                                    "title": "Imagine",
                                    "artist": "John Lennon",
                                    "coverUrl": "https://example.com/imagine.jpg"
                                }
                            },
                            {
                                "type": "playlist_published",
                                "userId": "user_123",
                                "playlistId": "507f1f77bcf86cd799439013",
                                "playlistName": "My Favorites",
                                "timestamp": "2025-11-09T10:00:00Z",
                                "publishedAt": "2025-11-09T10:00:00Z"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_user_activity(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of activities to return"),
    activity_type: Optional[str] = Query(default=None, description="Filter by activity type: 'like', 'play', 'playlist_published', 'share'"),
    user: dict = Depends(verify_token)
):
    """
    Get recent activity for a specific user.
    
    Returns a chronologically ordered list of user activities including:
    - **Likes**: Songs or collections the user has liked
    - **Plays**: Songs the user has listened to
    - **Published Playlists**: Playlists the user has made public
    - **Shares**: Content the user has shared (coming soon)
    
    **Query Parameters:**
    - `limit`: Maximum number of activities to return (1-100, default: 50)
    - `activity_type`: Optional filter by type. Valid values: 'like', 'play', 'playlist_published', 'share'
    
    **Note:** Activities are ordered from most recent to oldest.
    """
    try:
        logger.info(f"Fetching activity for user {user_id} (limit={limit}, type={activity_type})")
        
        # Get activities
        activities = await activity_db.get_user_activity(user_id, limit, activity_type)
        
        # Enrich with full details
        enriched_activities = await activity_db.enrich_activity_with_details(activities)
        
        logger.info(f"Successfully retrieved {len(enriched_activities)} activities for user {user_id}")
        return {"data": enriched_activities}
        
    except Exception as e:
        logger.error(f"Failed to fetch activity for user {user_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), f"/activity/{user_id}"
            ),
        )


@router.get(
    "/",
    responses={
        200: {
            "description": "Following activity feed",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "type": "like",
                                "userId": "user_456",
                                "targetId": "507f1f77bcf86cd799439011",
                                "targetType": "song",
                                "timestamp": "2025-11-10T16:45:00Z",
                                "createdAt": "2025-11-10T16:45:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439011",
                                    "title": "Stairway to Heaven",
                                    "artist": "Led Zeppelin",
                                    "coverUrl": "https://example.com/stairway.jpg"
                                }
                            },
                            {
                                "type": "play",
                                "userId": "user_789",
                                "songId": "507f1f77bcf86cd799439014",
                                "targetType": "song",
                                "timestamp": "2025-11-10T15:20:00Z",
                                "playedAt": "2025-11-10T15:20:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439014",
                                    "title": "Hotel California",
                                    "artist": "Eagles",
                                    "coverUrl": "https://example.com/hotel.jpg"
                                }
                            },
                            {
                                "type": "playlist_published",
                                "userId": "user_456",
                                "playlistId": "507f1f77bcf86cd799439015",
                                "playlistName": "Summer Hits 2025",
                                "timestamp": "2025-11-10T12:00:00Z",
                                "publishedAt": "2025-11-10T12:00:00Z"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_following_activity(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of activities to return"),
    activity_type: Optional[str] = Query(default=None, description="Filter by activity type: 'like', 'play', 'playlist_published', 'share'"),
    user: dict = Depends(verify_token)
):
    """
    Get recent activity from users that the authenticated user follows.
    
    Returns a chronologically ordered feed of activities from followed users, including:
    - **Likes**: Songs or collections they have liked
    - **Plays**: Songs they have listened to
    - **Published Playlists**: Playlists they have made public
    - **Shares**: Content they have shared (coming soon)
    
    **Query Parameters:**
    - `limit`: Maximum number of activities to return (1-100, default: 50)
    - `activity_type`: Optional filter by type. Valid values: 'like', 'play', 'playlist_published', 'share'
    
    **Note:** 
    - Activities are ordered from most recent to oldest across all followed users
    - Requires user authentication
    - Returns empty list if user doesn't follow anyone or follows feature is not yet implemented
    """
    try:
        user_id = user["user_id"]
        logger.info(f"Fetching following activity feed for user {user_id} (limit={limit}, type={activity_type})")
        
        # Get activities from followed users
        activities = await activity_db.get_following_activity(user_id, limit, activity_type)
        
        # Enrich with full details
        enriched_activities = await activity_db.enrich_activity_with_details(activities)
        
        logger.info(f"Successfully retrieved {len(enriched_activities)} activities for user {user_id}'s feed")
        return {"data": enriched_activities}
        
    except Exception as e:
        logger.error(f"Failed to fetch following activity feed for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), "/activity"
            ),
        )

