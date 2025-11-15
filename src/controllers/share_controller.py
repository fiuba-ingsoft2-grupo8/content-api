from fastapi import APIRouter, Depends, Query, Body
from fastapi.responses import JSONResponse
from typing import Optional

import databases.share_database as share_db
import databases.metrics_database as metrics_db
import databases.playlists_database as playlists_db
import schemas
from auth import verify_token
from common.utils import create_error_response
from resources.logger import logger

router = APIRouter()


@router.post(
    "/song/{song_id}",
    status_code=201,
    responses={
        201: {
            "description": "Song shared successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Song shared successfully",
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "userId": "user_123",
                            "targetId": "507f1f77bcf86cd799439012",
                            "targetType": "song",
                            "recipientId": "user_456",
                            "createdAt": "2025-11-15T10:30:00Z"
                        }
                    }
                }
            }
        }
    }
)
async def share_song(
    song_id: str,
    body: dict = Body(default={}),
    user: dict = Depends(verify_token)
):
    """
    Share a song with a friend or publicly.
    
    **Acceptance Criteria (CA 1):** When listening to a song, select 'Share' and choose a friend.
    The song will be shared in their activity feed and they can access it.
    
    **Request Body:**
    - `recipientId` (optional): User ID of the friend to share with. If not provided, share is public.
    
    **Behavior:**
    - Creates a share record in the database
    - Increments share metrics for the song
    - Appears in the recipient's activity feed (if recipientId provided)
    - Appears in user's own activity feed
    
    **Notes:**
    - Song must exist
    - If recipientId is provided, the share is direct to that user
    - If recipientId is not provided, the share is considered public
    """
    try:
        user_id = user["user_id"]
        recipient_id = body.get("recipientId") if body else None
        logger.info(f"User {user_id} sharing song {song_id}" + (f" with {recipient_id}" if recipient_id else " publicly"))
        
        # Create the share record
        share, error = await share_db.create_share(
            user_id=user_id,
            target_id=song_id,
            target_type="song",
            recipient_id=recipient_id
        )
        
        if error:
            logger.error(f"Failed to share song {song_id}: {str(error)}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    str(error),
                    f"/share/song/{song_id}"
                )
            )
        
        # Enrich share with song details
        enriched_share = await share_db.enrich_share_with_details(share)
        
        logger.info(f"Successfully shared song {song_id}")
        return {
            "message": "Song shared successfully",
            "data": {
                "_id": str(enriched_share["_id"]),
                "userId": enriched_share["user_id"],
                "targetId": str(enriched_share["target_id"]),
                "targetType": enriched_share["target_type"],
                "recipientId": enriched_share.get("recipient_id"),
                "createdAt": enriched_share["created_at"],
                "song": enriched_share.get("song")
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to share song {song_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                f"/share/song/{song_id}"
            )
        )


@router.post(
    "/playlist/{playlist_id}",
    status_code=201,
    responses={
        201: {
            "description": "Playlist shared successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Playlist shared successfully and made public",
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "name": "My Favorites",
                            "is_published": True,
                            "published_at": "2025-11-15T10:30:00Z"
                        }
                    }
                }
            }
        }
    }
)
async def share_playlist(
    playlist_id: str,
    body: dict = Body(default={"make_public": True}),
    user: dict = Depends(verify_token)
):
    """
    Share a playlist publicly.
    
    **Acceptance Criteria (CA 2):** When I've created a playlist, select 'Share' and choose to make it public.
    The playlist will be available on my profile for other users to see and listen to.
    
    **Request Body:**
    - `make_public` (optional, default: true): Whether to make the playlist public when sharing
    
    **Behavior:**
    - Makes the playlist public (sets is_published = true) if make_public is true
    - Creates a share record in the database
    - Increments share metrics for the playlist
    - Appears in user's activity feed as a published playlist
    
    **Notes:**
    - User must be the playlist owner or backoffice
    - Playlist must exist
    - If playlist is already public, still records the share
    """
    try:
        user_id = user["user_id"]
        make_public = body.get("make_public", True) if body else True
        logger.info(f"User {user_id} sharing playlist {playlist_id} (make_public={make_public})")
        
        # Get the playlist
        playlist = await playlists_db.get_playlist(playlist_id, user)
        if not playlist:
            logger.warning(f"Playlist {playlist_id} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Playlist with id {playlist_id} not found",
                    f"/share/playlist/{playlist_id}"
                )
            )
        
        # Check authorization
        is_owner = playlist.get("userId") == user_id
        is_backoffice = user.get("user_type") == "backoffice"
        
        if not is_owner and not is_backoffice:
            logger.warning(f"User {user_id} not authorized to share playlist {playlist_id}")
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to share this playlist",
                    f"/share/playlist/{playlist_id}"
                )
            )
        
        # Make playlist public if requested
        if make_public and not playlist.get("is_published"):
            await playlists_db.change_playlist_state(playlist, True)
            logger.info(f"Playlist {playlist_id} made public")
        
        # Create the share record (public share, no specific recipient)
        share, error = await share_db.create_share(
            user_id=user_id,
            target_id=playlist_id,
            target_type="playlist",
            recipient_id=None  # Public share
        )
        
        if error:
            logger.error(f"Failed to share playlist {playlist_id}: {str(error)}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    str(error),
                    f"/share/playlist/{playlist_id}"
                )
            )
        
        # Get updated playlist
        updated_playlist = await playlists_db.get_playlist(playlist_id, user)
        
        logger.info(f"Successfully shared playlist {playlist_id}")
        return {
            "message": "Playlist shared successfully" + (" and made public" if make_public else ""),
            "data": {
                "_id": str(updated_playlist["_id"]),
                "name": updated_playlist["name"],
                "is_published": updated_playlist["is_published"],
                "published_at": updated_playlist.get("published_at"),
                "userId": updated_playlist["userId"]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to share playlist {playlist_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                f"/share/playlist/{playlist_id}"
            )
        )


@router.post(
    "/collection/{collection_id}",
    status_code=201,
    responses={
        201: {
            "description": "Collection shared successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Collection shared successfully",
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "userId": "user_123",
                            "targetId": "507f1f77bcf86cd799439012",
                            "targetType": "collection",
                            "recipientId": "user_456",
                            "createdAt": "2025-11-15T10:30:00Z"
                        }
                    }
                }
            }
        }
    }
)
async def share_collection(
    collection_id: str,
    body: dict = Body(default={}),
    user: dict = Depends(verify_token)
):
    """
    Share a collection (album/EP/single) with a friend or publicly.
    
    **Request Body:**
    - `recipientId` (optional): User ID of the friend to share with. If not provided, share is public.
    
    **Behavior:**
    - Creates a share record in the database
    - Increments share metrics for the collection
    - Appears in the recipient's activity feed (if recipientId provided)
    - Appears in user's own activity feed
    
    **Notes:**
    - Collection must exist
    - If recipientId is provided, the share is direct to that user
    - If recipientId is not provided, the share is considered public
    """
    try:
        user_id = user["user_id"]
        recipient_id = body.get("recipientId") if body else None
        logger.info(f"User {user_id} sharing collection {collection_id}" + (f" with {recipient_id}" if recipient_id else " publicly"))
        
        # Create the share record
        share, error = await share_db.create_share(
            user_id=user_id,
            target_id=collection_id,
            target_type="collection",
            recipient_id=recipient_id
        )
        
        if error:
            logger.error(f"Failed to share collection {collection_id}: {str(error)}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    str(error),
                    f"/share/collection/{collection_id}"
                )
            )
        
        # Enrich share with collection details
        enriched_share = await share_db.enrich_share_with_details(share)
        
        logger.info(f"Successfully shared collection {collection_id}")
        return {
            "message": "Collection shared successfully",
            "data": {
                "_id": str(enriched_share["_id"]),
                "userId": enriched_share["user_id"],
                "targetId": str(enriched_share["target_id"]),
                "targetType": enriched_share["target_type"],
                "recipientId": enriched_share.get("recipient_id"),
                "createdAt": enriched_share["created_at"],
                "collection": enriched_share.get("collection")
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to share collection {collection_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                f"/share/collection/{collection_id}"
            )
        )


@router.get(
    "/received",
    responses={
        200: {
            "description": "List of shares received by the user",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "_id": "507f1f77bcf86cd799439011",
                                "userId": "user_456",
                                "targetId": "507f1f77bcf86cd799439012",
                                "targetType": "song",
                                "recipientId": "user_123",
                                "createdAt": "2025-11-15T10:30:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439012",
                                    "title": "Bohemian Rhapsody",
                                    "artist": "Queen",
                                    "coverUrl": "https://example.com/cover.jpg"
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_received_shares(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of shares to return"),
    user: dict = Depends(verify_token)
):
    """
    Get shares that were sent directly to the authenticated user.
    
    Returns a list of items that friends have shared with you, ordered by most recent first.
    
    **Query Parameters:**
    - `limit`: Maximum number of shares to return (1-100, default: 50)
    
    **Notes:**
    - Only returns shares that were sent directly to you (with your user ID as recipientId)
    - Does not include public shares
    - Shares are enriched with details about the shared content
    """
    try:
        user_id = user["user_id"]
        logger.info(f"Fetching received shares for user {user_id} (limit={limit})")
        
        # Get shares for this user
        shares = await share_db.get_shares_for_user(user_id, limit)
        
        # Enrich with details
        enriched_shares = []
        for share in shares:
            enriched = await share_db.enrich_share_with_details(share)
            enriched_shares.append(enriched)
        
        logger.info(f"Successfully retrieved {len(enriched_shares)} received shares for user {user_id}")
        return {"data": enriched_shares}
        
    except Exception as e:
        logger.error(f"Failed to fetch received shares for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                "/share/received"
            )
        )

