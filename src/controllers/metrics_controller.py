import databases.metrics_database as metrics_db
import databases.songs_database as songs_db
import databases.collections_database as collections_db
import schemas
from fastapi import Depends
from auth import verify_token
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from resources.logger import logger
from common.utils import create_error_response

router = APIRouter()

@router.get("/likes/{target_type}/{target_id}", status_code=200)
async def check_like_status(target_type: str, target_id: str, user: dict = Depends(verify_token)):
    """
    Check if the current user has liked a specific song.
    
    Note: This only works for songs (target_type: "song").
    Collections don't have direct likes.
    """
    logger.info(f"Checking like status for {target_type} {target_id} by user {user['user_id']}")
    
    if target_type != "song":
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request",
                "Only songs can be liked. Collections don't have direct likes - their like count is the sum of their songs' likes.",
                f"/metrics/likes/{target_type}/{target_id}"
            ),
        )
    
    is_liked = await metrics_db.is_liked_by_user(user["user_id"], target_id, target_type)
    
    return {
        "liked": is_liked
    }

@router.post("/shares", status_code=201)
async def record_share(request: schemas.ShareRequest, user: dict = Depends(verify_token)):
    """
    Record a share event for a song or collection.
    """
    logger.info(f"User {user['user_id']} sharing {request.targetType} {request.targetId}")
    
    # Validate target exists
    if request.targetType == "song":
        target = await songs_db.get_song(request.targetId)
        if not target:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song with id {request.targetId} not found",
                    "/metrics/shares"
                ),
            )
    elif request.targetType == "collection":
        target = await collections_db.get_collection(request.targetId)
        if not target:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Collection with id {request.targetId} not found",
                    "/metrics/shares"
                ),
            )
    else:
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request",
                "targetType must be 'song' or 'collection'",
                "/metrics/shares"
            ),
        )
    
    error = await metrics_db.record_share(user["user_id"], request.targetId, request.targetType)
    if error:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                str(error),
                "/metrics/shares"
            ),
        )
    
    return {"message": "Share recorded successfully"}

@router.get("/songs/{song_id}", status_code=200)
async def get_song_metrics(song_id: str, user: dict = Depends(verify_token)):
    """
    Get complete metrics for a specific song.
    Returns plays, likes, and shares count.
    """
    logger.info(f"Fetching metrics for song {song_id}")
    
    # Validate song exists
    song = await songs_db.get_song(song_id)
    if not song:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Song with id {song_id} not found",
                f"/metrics/songs/{song_id}"
            ),
        )
    
    metrics = await metrics_db.get_song_metrics(song_id)
    if not metrics:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                "Failed to fetch song metrics",
                f"/metrics/songs/{song_id}"
            ),
        )
    
    return {"data": metrics}

@router.get("/collections/{collection_id}", status_code=200)
async def get_collection_metrics(collection_id: str, user: dict = Depends(verify_token)):
    """
    Get complete metrics for a specific collection.
    
    Returns:
    - totalPlays: Sum of plays from all songs in the collection
    - likes: Sum of likes from all songs in the collection
    - shares: Number of times the collection itself was shared
    """
    logger.info(f"Fetching metrics for collection {collection_id}")
    
    # Validate collection exists
    collection = await collections_db.get_collection(collection_id)
    if not collection:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Collection with id {collection_id} not found",
                f"/metrics/collections/{collection_id}"
            ),
        )
    
    metrics = await metrics_db.get_collection_metrics(collection_id)
    if not metrics:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                "Failed to fetch collection metrics",
                f"/metrics/collections/{collection_id}"
            ),
        )
    
    return {"data": metrics}

@router.get("/artists/{artist_id}", status_code=200)
async def get_artist_metrics(artist_id: str, user: dict = Depends(verify_token)):
    """
    Get overall metrics for an artist.
    Returns monthly listeners, plays, saves, and shares with comparison to previous period.
    
    Metrics are calculated for the current month vs previous month.
    """
    logger.info(f"Fetching metrics for artist {artist_id}")
    
    # Optionally validate that the user is requesting their own metrics
    # or has permission to view this artist's metrics
    
    metrics = await metrics_db.get_artist_metrics(artist_id)
    if not metrics:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                "Failed to fetch artist metrics",
                f"/metrics/artists/{artist_id}"
            ),
        )
    
    return {"data": metrics}

@router.get("/artists/me/overview", status_code=200)
async def get_my_artist_metrics(user: dict = Depends(verify_token)):
    """
    Get overall metrics for the authenticated artist.
    Returns monthly listeners, plays, saves, and shares with comparison to previous period.
    """
    artist_id = user["user_id"]
    logger.info(f"Fetching metrics for authenticated artist {artist_id}")
    
    # Check if user is an artist
    if not user.get("stage_name"):
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403, "Forbidden",
                "User is not an artist",
                "/metrics/artists/me/overview"
            ),
        )
    
    metrics = await metrics_db.get_artist_metrics(artist_id)
    if not metrics:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                "Failed to fetch artist metrics",
                "/metrics/artists/me/overview"
            ),
        )
    
    return {"data": metrics}

