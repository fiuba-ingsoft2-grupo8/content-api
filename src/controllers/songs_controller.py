import schemas
import databases.songs_database as songs_db
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter, Depends
from common.utils import create_error_response, serialize_song
from auth import verify_token

router = APIRouter()

@router.post("/", status_code=201)
async def create_song(song: schemas.CreateSongRequest, user_data: dict = Depends(verify_token)):
    """
    Create a new song in the database.
    
    This endpoint accepts song data (title and artist) and creates a new song
    record in the database. It handles database operations with proper error
    handling and transaction management.
    """
    logger.info(f"Creating song: title='{song.title}', artist='{song.artist}'")

    (db_song, e) = await songs_db.create_song(song.title, song.artist)
    if not db_song:
        return JSONResponse(
        status_code=400,
        content=create_error_response(400, "Bad Request", str(e), "/songs"),
    )
    return { "data": serialize_song(db_song) }


@router.get("/")
async def get_all_songs(user_data: dict = Depends(verify_token)):
    """
    Retrieve all songs from the database.
    
    This endpoint fetches and returns all song records from the database.
    No filtering or pagination is applied - all songs are returned in a single response.
    """
    logger.info("Fetching all songs")
    try:
        songs = await songs_db.get_all_songs()
        return { "data": [serialize_song(song) for song in songs] }
    except Exception as e:
        logger.error(f"Failed to fetch all songs: {str(e)}")
        raise


@router.get("/{id}")
async def get_song(id: str, user_data: dict = Depends(verify_token)):
    """
    Retrieve a specific song by its ID.
    
    This endpoint fetches a single song from the database using its unique ID.
    If the song doesn't exist, returns a 404 Not Found error.
    """
    logger.info(f"Fetching song with id={id}")
    try:
        song = await songs_db.get_song(id)
        if song is None:
            logger.warning(f"Song with id={id} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found", f"Song with id {id} not found", f"/songs/{id}"
                ),
            )
        return {"data": serialize_song(song)}
    except Exception as e:
        logger.error(f"Failed to fetch song with id={id}: {str(e)}")
        raise


@router.put("/{id}", status_code=200)
async def update_song(id: str, song: schemas.UpdateSongRequest, user_data: dict = Depends(verify_token)):
    """
    Update an existing song's information.
    
    This endpoint updates the title and artist of an existing song identified by ID.
    If the song doesn't exist, returns a 404 Not Found error. The update operation
    is performed within a database transaction for data consistency.
    """
    logger.info(
        f"Updating song with id={id}: title='{song.title}', artist='{song.artist}'"
    )

    db_song = await songs_db.get_song(id)
    if db_song is None:
        logger.warning(f"Song with id={id} not found for update")
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found", f"Song with id {id} not found", f"/songs/{id}"
            ),
        )

    updated_song, e = await songs_db.update_song(db_song, song.title, song.artist)

    if not updated_song:
        logger.error(f"Failed to update song with id={id}: {str(e)}")
        logger.debug("Database transaction rolled back")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/songs/{id}"),
        )
    return {"data": serialize_song(updated_song)}


@router.delete("/{id}", status_code=204)
async def delete_song(id: str, user_data: dict = Depends(verify_token)):
    """
    Delete a song from the database.
    
    This endpoint permanently removes a song record from the database.
    If the song doesn't exist, returns a 404 Not Found error.
    The operation also removes the song from all playlists due to foreign key constraints.
    """
    logger.info(f"Deleting song with id={id}")
    db_song = await songs_db.get_song(id)
    if db_song is None:
        logger.warning(f"Song with id={id} not found for update")
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found", f"Song with id {id} not found", f"/songs/{id}"
            ),
        )

    return await songs_db.delete_song(db_song)

