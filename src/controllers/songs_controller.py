import schemas
import databases.songs_database as songs_db
from fastapi import Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from db.database import get_db
from resources.logger import logger
from fastapi import APIRouter
from common.utils import create_error_response

router = APIRouter()

@router.post("/", status_code=201, response_model=schemas.SongResponse)
def create_song(song: schemas.CreateSongRequest, db: Session = Depends(get_db)):
    """
    Create a new song in the database.
    
    This endpoint accepts song data (title and artist) and creates a new song
    record in the database. It handles database operations with proper error
    handling and transaction management.
    """
    logger.info(f"Creating song: title='{song.title}', artist='{song.artist}'")

    (db_song, e) = songs_db.create_song(db, song.title, song.artist)
    if not db_song:
        return JSONResponse(
        status_code=400,
        content=create_error_response(400, "Bad Request", str(e), "/songs"),
    )


@router.get("/", response_model=schemas.SongsResponse)
def get_all_songs(db: Session = Depends(get_db)):
    """
    Retrieve all songs from the database.
    
    This endpoint fetches and returns all song records from the database.
    No filtering or pagination is applied - all songs are returned in a single response.
    """
    logger.info("Fetching all songs")
    try:
        songs = songs_db.get_all_songs(db)
        return { "data": songs}
    except Exception as e:
        logger.error(f"Failed to fetch all songs: {str(e)}")
        raise


@router.get("/{id}", response_model=schemas.SongResponse)
def get_song(id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific song by its ID.
    
    This endpoint fetches a single song from the database using its unique ID.
    If the song doesn't exist, returns a 404 Not Found error.
    """
    logger.info(f"Fetching song with id={id}")
    try:
        song = songs_db.get_song(db, id)
        if song is None:
            logger.warning(f"Song with id={id} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found", f"Song with id {id} not found", f"/songs/{id}"
                ),
            )
        logger.info(
            f"Successfully retrieved song: title='{song.title}', artist='{song.artist}'"
        )
        return {"data": song}
    except Exception as e:
        logger.error(f"Failed to fetch song with id={id}: {str(e)}")
        raise


@router.put("/{id}", response_model=schemas.SongResponse, status_code=200)
def update_song(id: int, song: schemas.UpdateSongRequest, db: Session = Depends(get_db)):
    """
    Update an existing song's information.
    
    This endpoint updates the title and artist of an existing song identified by ID.
    If the song doesn't exist, returns a 404 Not Found error. The update operation
    is performed within a database transaction for data consistency.
    """
    logger.info(
        f"Updating song with id={id}: title='{song.title}', artist='{song.artist}'"
    )

    db_song = songs_db.get_song(db, id)
    if db_song is None:
        logger.warning(f"Song with id={id} not found for update")
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found", f"Song with id {id} not found", f"/songs/{id}"
            ),
        )

    logger.debug(
        f"Found song to update: current title='{db_song.title}', artist='{db_song.artist}'"
    )

    updated_song, e = songs_db.update_song(db, db_song, song.title, song.artist)

    if not updated_song:
        logger.error(f"Failed to update song with id={id}: {str(e)}")
        logger.debug("Database transaction rolled back")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/songs/{id}"),
        )
    return {"data": updated_song}


@router.delete("/{id}", status_code=204)
def delete_song(id: int, db: Session = Depends(get_db)):
    """
    Delete a song from the database.
    
    This endpoint permanently removes a song record from the database.
    If the song doesn't exist, returns a 404 Not Found error.
    The operation also removes the song from all playlists due to foreign key constraints.
    """
    logger.info(f"Deleting song with id={id}")
    db_song = songs_db.get_song(db, id)
    if db_song is None:
        logger.warning(f"Song with id={id} not found for update")
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found", f"Song with id {id} not found", f"/songs/{id}"
            ),
        )

    logger.debug(
        f"Found song to delete: title='{db_song.title}', artist='{db_song.artist}'"
    )
    return songs_db.delete_song(db, db_song)