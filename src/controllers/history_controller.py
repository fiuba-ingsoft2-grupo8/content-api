from typing import Optional
from databases.collections_database import USER_API_BASE
import databases.playlists_database as playlists_db
import databases.songs_database as songs_db
import databases.history_database as history_db
import databases.metrics_database as metrics_db
import schemas
from fastapi import Body, Depends, Header
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter
from common.utils import create_error_response, serialize_playlist
from auth import verify_token
import httpx

router = APIRouter()

async def fetch_user_history_preference(token: Optional[str] = None) -> bool:
    """
    Llama al endpoint público GET /users/history_preference y devuelve { "isPaused": bool }
    Ajustá el path si en tu API quedó distinto.
    """
    url = f"{USER_API_BASE}/users/history_preference"
    headers = {}
    if token:
        headers["Authorization"] = token

    timeout = httpx.Timeout(20.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        logger.info(f"Calling: {USER_API_BASE.rstrip('/')}/users/history_preference")
        resp = await client.get(url, headers=headers) # user_id se puede obtener del header Authorization
        resp.raise_for_status()
        data = resp.json()
        # Asumiendo que la respuesta es {"isPaused": bool}
        isPaused = data.get("isPaused")
        return isPaused or False

@router.post("/")
async def add_to_history(request: schemas.ListeningHistoryRequest, user: dict = Depends(verify_token), authorization: str = Header(None)):
    logger.info(f"Adding song with id {request.songId} to user {user['user_id']}'s listening history")
    # Descomentar la linea de abajo cuando este el endpoint "history_preference en user api" y comentar la linea "paused = False"
    # paused = await fetch_user_history_preference(authorization)
    paused = False 
    if paused:
        return JSONResponse(status_code=201, content={"message": "History is paused"})

    song = await songs_db.get_song(request.songId)
    if not song:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Song with id {request.songId} not found",
                f"/history"
            ),
        )

    error = await history_db.add_to_history(request.songId, user["user_id"])
    if error:
        logger.info(f"Failed to log song with id {request.songId} to user {user['user_id']}'s listening history")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(error), "/history"),
        )

    # Record play in permanent metrics table (separate from user history)
    metrics_error = await metrics_db.record_play(user["user_id"], request.songId)
    if metrics_error:
        logger.warning(f"Failed to record play metrics for song {request.songId}: {str(metrics_error)}")
        # Don't fail the request if metrics recording fails, just log it

    logger.info(f"Succesfully logged song with id {request.songId} to user {user['user_id']}'s listening history")
    return JSONResponse(status_code=201, content={"message": "Added to history"})

@router.get("/")
async def get_history(user: dict = Depends(verify_token), search: str = None):
    """
    Retrieve the listening history for a specific user.
    Returns a list of songs (most recent first).
    Optionally filter by a search term in song title or artist.
    """
    try:
        logger.info(f"Fetching listening history for user {user['user_id']} with search={search}")
        history_entries = await history_db.get_user_history(user["user_id"], search)

        if not history_entries:
            logger.info(f"No listening history found for user {user['user_id']}")
            return {"data": []}

        full_history = []
        for entry in history_entries:
            song = await songs_db.get_song(entry["songId"])
            if song:
                full_history.append({
                    "song": {
                        "_id": str(song["_id"]),
                        "title": song["title"],
                        "artist": song["artist"],
                        "coverUrl": song.get("coverUrl")
                    },
                    "playedAt": entry.get("playedAt"),
                    "progress": entry.get("progress")
                })

        logger.info(f"Successfully retrieved {len(full_history)} entries for user {user['user_id']}")
        return {"data": full_history}

    except Exception as e:
        logger.error(f"Failed to retrieve history for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), f"/history?userId={user['user_id']}"
            ),
        )

@router.put("/")
async def update_song_progress(request: schemas.ListeningHistoryRequest, user: dict = Depends(verify_token)):
    """
    Update the progress of a song in the user's listening history.
    """
    logger.info(f"Updating progress for song {request.songId} for user {user['user_id']}")
    
    error = await history_db.update_history_progress(user["user_id"], request.songId, request.progress)
    if error:
        logger.error(f"Failed to update progress for song {request.songId}: {str(error)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(error), "/history")
        )

    logger.info(f"Successfully updated progress for song {request.songId}")
    return JSONResponse(status_code=200, content={"message": "Progress updated"})

@router.delete("/")
async def clear_history(user: dict = Depends(verify_token)):
    """
    Clear all listening history for a specific user.
    """
    try:
        await history_db.clear_user_history(user["user_id"])
        logger.info(f"Cleared history entries for user {user['user_id']}")
        return JSONResponse(
            status_code=200,
            content={"message": f"Cleared history entries"}
        )
    except Exception as e:
        logger.error(f"Failed to clear history for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/history?userId={user['user_id']}")
        )
