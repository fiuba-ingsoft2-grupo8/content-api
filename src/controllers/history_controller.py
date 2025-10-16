import databases.playlists_database as playlists_db
import databases.songs_database as songs_db
import databases.history_database as history_db
import schemas
from fastapi import Body, Depends
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter
from common.utils import create_error_response, serialize_playlist
from auth import verify_token

router = APIRouter()

@router.post("/")
async def add_to_history(request: schemas.ListeningHistoryRequest, user_data: dict = Depends(verify_token)):
    logger.info(f"Adding song with id {request.songId} to user {request.userId}'s listening history")

    # to do: agregar validacion del estado del historial (pausado o no)

    song = await songs_db.get_song(request.songId)
    if not song:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Song with id {request.songId} not found",
                f"/playlists/{id}/songs"
            ),
        )

    error = await history_db.add_to_history(request.songId, request.userId)
    if error:
        logger.info(f"Failed to log song with id {id} to user {request.userId}'s listening history")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(error), "/history"),
        )

    logger.info(f"Succesfully logged song with id {id} to user {request.userId}'s listening history")
    return JSONResponse(status_code=201, content={"message": "Added to history"})

@router.get("/")
async def get_history(userId: str, search: str = None, user_data: dict = Depends(verify_token)):
    """
    Retrieve the listening history for a specific user.
    Returns a list of songs (most recent first).
    Optionally filter by a search term in song title or artist.
    """
    try:
        logger.info(f"Fetching listening history for user {userId} with search={search}")
        history_entries = await history_db.get_user_history(userId, search)

        if not history_entries:
            logger.info(f"No listening history found for user {userId}")
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

        logger.info(f"Successfully retrieved {len(full_history)} entries for user {userId}")
        return {"data": full_history}

    except Exception as e:
        logger.error(f"Failed to retrieve history for user {userId}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), f"/history?userId={userId}"
            ),
        )

@router.put("/")
async def update_song_progress(request: schemas.ListeningHistoryRequest, user_data: dict = Depends(verify_token)):
    """
    Update the progress of a song in the user's listening history.
    """
    logger.info(f"Updating progress for song {request.songId} for user {request.userId}")
    
    error = await history_db.update_history_progress(request.userId, request.songId, request.progress)
    if error:
        logger.error(f"Failed to update progress for song {request.songId}: {str(error)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(error), "/history")
        )

    logger.info(f"Successfully updated progress for song {request.songId}")
    return JSONResponse(status_code=200, content={"message": "Progress updated"})

@router.delete("/")
async def clear_history(userId: str, user_data: dict = Depends(verify_token)):
    """
    Clear all listening history for a specific user.
    """
    try:
        await history_db.clear_user_history(userId)
        logger.info(f"Cleared history entries for user {userId}")
        return JSONResponse(
            status_code=200,
            content={"message": f"Cleared history entries"}
        )
    except Exception as e:
        logger.error(f"Failed to clear history for user {userId}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/history?userId={userId}")
        )
