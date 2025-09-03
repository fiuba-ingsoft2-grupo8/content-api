from fastapi import FastAPI, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from datetime import datetime, timezone
import uvicorn
import os
from dotenv import load_dotenv
from db import models
import schemas
from db.database import engine, get_db, wait_for_db
from resources.logger import logger, LOGGING_CONFIG

logger.info("Load configurations")
load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

logger.info("Waiting for database")
wait_for_db()
logger.info("Creating database tables if they don't exist")
models.Base.metadata.create_all(bind=engine)
logger.info("Database initialization complete")

logger.info("Initializing FastAPI application")
app = FastAPI(title="Melodia API", version="1.0.0")
logger.info("FastAPI application initialized")


def create_error_response(
    status_code: int, title: str, detail: str, instance: str = ""
):
    """
    Create a standardized error response following RFC 7807 Problem Details format.
    """
    logger.debug(
        f"Creating error response: {status_code} - {title} - {detail} - {instance}"
    )
    return {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Global exception handler for FastAPI request validation errors.
    
    This handler catches all RequestValidationError exceptions thrown by FastAPI
    when request data fails Pydantic validation. It logs the validation errors
    and returns a standardized 400 Bad Request response.
    """
    logger.warning(
        f"Request validation error on {request.method} {request.url.path}: {exc.errors()}"
    )
    logger.debug(f"Request validation details: {exc}")
    return JSONResponse(
        status_code=400,
        content=create_error_response(
            status_code=400,
            title="Bad Request",
            detail="Invalid request body",
            instance=str(request.url.path),
        ),
    )


@app.post("/songs", status_code=201, response_model=schemas.SongResponse)
def create_song(song: schemas.CreateSongRequest, db: Session = Depends(get_db)):
    """
    Create a new song in the database.
    
    This endpoint accepts song data (title and artist) and creates a new song
    record in the database. It handles database operations with proper error
    handling and transaction management.
    """
    logger.info(f"Creating song: title='{song.title}', artist='{song.artist}'")
    try:
        db_song = models.Song(title=song.title, artist=song.artist)
        logger.debug(f"Created song model: {db_song}")
        db.add(db_song)
        logger.debug("Added song to database session")
        db.commit()
        logger.debug("Committed song to database")
        db.refresh(db_song)
        logger.info(f"Successfully created song with id={db_song.id}")
        return {"data": db_song}
    except Exception as e:
        logger.error(
            f"Failed to create song '{song.title}' by '{song.artist}': {str(e)}"
        )
        db.rollback()
        logger.debug("Database transaction rolled back")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/songs"),
        )


@app.get("/songs", response_model=schemas.SongsResponse)
def get_all_songs(db: Session = Depends(get_db)):
    """
    Retrieve all songs from the database.
    
    This endpoint fetches and returns all song records from the database.
    No filtering or pagination is applied - all songs are returned in a single response.
    """
    logger.info("Fetching all songs")
    try:
        songs = db.query(models.Song).all()
        logger.info(f"Retrieved {len(songs)} songs from database")
        return {"data": songs}
    except Exception as e:
        logger.error(f"Failed to fetch all songs: {str(e)}")
        raise


@app.get("/songs/{id}", response_model=schemas.SongResponse)
def get_song(id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific song by its ID.
    
    This endpoint fetches a single song from the database using its unique ID.
    If the song doesn't exist, returns a 404 Not Found error.
    """
    logger.info(f"Fetching song with id={id}")
    try:
        song = db.query(models.Song).filter(models.Song.id == id).first()
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


@app.put("/songs/{id}", response_model=schemas.SongResponse)
def update_song(
    id: int, song: schemas.UpdateSongRequest, db: Session = Depends(get_db)
):
    """
    Update an existing song's information.
    
    This endpoint updates the title and artist of an existing song identified by ID.
    If the song doesn't exist, returns a 404 Not Found error. The update operation
    is performed within a database transaction for data consistency.
    """
    logger.info(
        f"Updating song with id={id}: title='{song.title}', artist='{song.artist}'"
    )
    try:
        db_song = db.query(models.Song).filter(models.Song.id == id).first()
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
        old_title, old_artist = db_song.title, db_song.artist
        db_song.title = song.title
        db_song.artist = song.artist
        logger.debug(
            f"Updated song fields: '{old_title}' -> '{song.title}', '{old_artist}' -> '{song.artist}'"
        )
        db.commit()
        logger.debug("Committed song update to database")
        db.refresh(db_song)
        logger.info(f"Successfully updated song with id={id}")
        return {"data": db_song}
    except Exception as e:
        logger.error(f"Failed to update song with id={id}: {str(e)}")
        db.rollback()
        logger.debug("Database transaction rolled back")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/songs/{id}"),
        )


@app.delete("/songs/{id}", status_code=204)
def delete_song(id: int, db: Session = Depends(get_db)):
    """
    Delete a song from the database.
    
    This endpoint permanently removes a song record from the database.
    If the song doesn't exist, returns a 404 Not Found error.
    The operation also removes the song from all playlists due to foreign key constraints.
    """
    logger.info(f"Deleting song with id={id}")
    try:
        song = db.query(models.Song).filter(models.Song.id == id).first()
        if song is None:
            logger.warning(f"Song with id={id} not found for deletion")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found", f"Song with id {id} not found", f"/songs/{id}"
                ),
            )

        logger.debug(
            f"Found song to delete: title='{song.title}', artist='{song.artist}'"
        )
        db.delete(song)
        logger.debug("Marked song for deletion")
        db.commit()
        logger.info(f"Successfully deleted song with id={id}")
        return None
    except Exception as e:
        logger.error(f"Failed to delete song with id={id}: {str(e)}")
        db.rollback()
        logger.debug("Database transaction rolled back")
        raise


@app.post("/playlists", status_code=201, response_model=schemas.PlaylistResponse)
def create_playlist(
    playlist: schemas.CreatePlaylistRequest, db: Session = Depends(get_db)
):
    """
    Create a new playlist in the database.
    
    This endpoint creates a new playlist with the provided name and description.
    All new playlists are automatically published with the current timestamp.
    The playlist starts empty - songs can be added using the add song to playlist endpoint.
    """
    logger.info(
        f"Creating playlist: name='{playlist.name}', description='{playlist.description}'"
    )
    try:
        publish_time = datetime.now(timezone.utc)
        db_playlist = models.Playlist(
            name=playlist.name,
            description=playlist.description,
            is_published=True,
            published_at=publish_time,
        )
        logger.debug(f"Created playlist model with published_at={publish_time}")
        db.add(db_playlist)
        logger.debug("Added playlist to database session")
        db.commit()
        logger.debug("Committed playlist to database")
        db.refresh(db_playlist)
        logger.info(f"Successfully created playlist with id={db_playlist.id}")

        playlist_data = schemas.Playlist(
            id=db_playlist.id,
            name=db_playlist.name,
            description=db_playlist.description,
            isPublished=db_playlist.is_published,
            publishedAt=db_playlist.published_at,
            songs=[],
        )
        logger.debug(f"Prepared playlist response data")
        return {"data": playlist_data}
    except Exception as e:
        logger.error(f"Failed to create playlist '{playlist.name}': {str(e)}")
        db.rollback()
        logger.debug("Database transaction rolled back")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/playlists"),
        )


@app.get("/playlists", response_model=schemas.PlaylistsResponse)
def get_published_playlists(db: Session = Depends(get_db)):
    """
    Retrieve all published playlists with their songs.
    
    This endpoint fetches all playlists that are marked as published,
    ordered by publication date (newest first) and includes all songs
    in each playlist with their metadata. Only published playlists are
    returned to maintain privacy of unpublished playlists.
    """
    logger.info("Fetching all published playlists")
    try:
        playlists = (
            db.query(models.Playlist)
            .filter(models.Playlist.is_published == True)
            .order_by(desc(models.Playlist.published_at), desc(models.Playlist.id))
            .all()
        )
        logger.info(f"Retrieved {len(playlists)} published playlists from database")

        playlist_data = []
        for playlist in playlists:
            logger.debug(
                f"Processing playlist: id={playlist.id}, name='{playlist.name}'"
            )
            playlist_songs = db.execute(
                text(
                    f"""
                SELECT s.id, s.title, s.artist, ps.added_at
                FROM songs s
                JOIN playlist_songs ps ON s.id = ps.song_id
                WHERE ps.playlist_id = {playlist.id}
                ORDER BY ps.added_at DESC, s.id DESC
                """
                )
            ).fetchall()
            logger.debug(f"Found {len(playlist_songs)} songs in playlist {playlist.id}")

            songs = []
            for song_row in playlist_songs:
                songs.append(
                    schemas.PlaylistSong(
                        id=song_row[0],
                        title=song_row[1],
                        artist=song_row[2],
                        addedAt=song_row[3],
                    )
                )

            playlist_data.append(
                schemas.Playlist(
                    id=playlist.id,
                    name=playlist.name,
                    description=playlist.description,
                    isPublished=playlist.is_published,
                    publishedAt=playlist.published_at,
                    songs=songs,
                )
            )

        logger.info(
            f"Successfully processed {len(playlist_data)} playlists with their songs"
        )
        return {"data": playlist_data}
    except Exception as e:
        logger.error(f"Failed to fetch published playlists: {str(e)}")
        raise


@app.get("/playlists/{id}", response_model=schemas.PlaylistResponse)
def get_playlist(id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific playlist by its ID with all songs.
    
    This endpoint fetches a single playlist from the database using its unique ID,
    including all songs in the playlist with their metadata. Unlike the get all
    playlists endpoint, this returns the playlist regardless of its publication status.
    """
    logger.info(f"Fetching playlist with id={id}")
    try:
        playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
        if playlist is None:
            logger.warning(f"Playlist with id={id} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Playlist with id {id} not found",
                    f"/playlists/{id}",
                ),
            )

        logger.debug(
            f"Found playlist: name='{playlist.name}', published={playlist.is_published}"
        )
        playlist_songs = db.execute(
            text(
                f"""
            SELECT s.id, s.title, s.artist, ps.added_at
            FROM songs s
            JOIN playlist_songs ps ON s.id = ps.song_id
            WHERE ps.playlist_id = {id}
            ORDER BY ps.added_at DESC, s.id DESC
            """
            )
        ).fetchall()
        logger.debug(f"Found {len(playlist_songs)} songs in playlist {id}")

        songs = []
        for song_row in playlist_songs:
            songs.append(
                schemas.PlaylistSong(
                    id=song_row[0],
                    title=song_row[1],
                    artist=song_row[2],
                    addedAt=song_row[3],
                )
            )

        playlist_data = schemas.Playlist(
            id=playlist.id,
            name=playlist.name,
            description=playlist.description,
            isPublished=playlist.is_published,
            publishedAt=playlist.published_at,
            songs=songs,
        )

        logger.info(f"Successfully retrieved playlist {id} with {len(songs)} songs")
        return {"data": playlist_data}
    except Exception as e:
        logger.error(f"Failed to fetch playlist with id={id}: {str(e)}")
        raise


@app.delete("/playlists/{id}", status_code=204)
def delete_playlist(id: int, db: Session = Depends(get_db)):
    """
    Delete a playlist from the database.
    
    This endpoint permanently removes a playlist record from the database.
    If the playlist doesn't exist, returns a 404 Not Found error.
    The operation also removes all song associations from the playlist
    due to foreign key constraints, but the songs themselves remain in the database.
    """
    logger.info(f"Deleting playlist with id={id}")
    try:
        playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
        if playlist is None:
            logger.warning(f"Playlist with id={id} not found for deletion")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Playlist with id {id} not found",
                    f"/playlists/{id}",
                ),
            )

        logger.debug(f"Found playlist to delete: name='{playlist.name}'")
        db.delete(playlist)
        logger.debug("Marked playlist for deletion")
        db.commit()
        logger.info(f"Successfully deleted playlist with id={id}")
        return None
    except Exception as e:
        logger.error(f"Failed to delete playlist with id={id}: {str(e)}")
        db.rollback()
        logger.debug("Database transaction rolled back")
        raise


@app.post("/playlists/{id}/songs", response_model=schemas.PlaylistResponse)
def add_song_to_playlist(
    id: int, request: schemas.AddSongToPlaylistRequest, db: Session = Depends(get_db)
):
    """
    Add an existing song to a playlist.
    
    This endpoint adds a song (identified by songId) to an existing playlist.
    It validates that both the playlist and song exist, and that the song
    is not already in the playlist. The song is added with the current timestamp.
    """
    logger.info(f"Adding song {request.songId} to playlist {id}")
    try:
        playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
        if playlist is None:
            logger.warning(f"Playlist with id={id} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Playlist with id {id} not found",
                    f"/playlists/{id}/songs",
                ),
            )
        logger.debug(f"Found playlist: name='{playlist.name}'")

        song = db.query(models.Song).filter(models.Song.id == request.songId).first()
        if song is None:
            logger.warning(f"Song with id={request.songId} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Song with id {request.songId} not found",
                    f"/playlists/{id}/songs",
                ),
            )
        logger.debug(f"Found song: title='{song.title}', artist='{song.artist}'")

        existing_relation = db.execute(
            text(
                f"""
            SELECT 1 FROM playlist_songs 
            WHERE playlist_id = {id} AND song_id = {request.songId}
            """
            )
        ).fetchone()

        if existing_relation:
            logger.warning(f"Song {request.songId} is already in playlist {id}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    "Song is already in the playlist",
                    f"/playlists/{id}/songs",
                ),
            )

        logger.debug(f"Adding song {request.songId} to playlist {id}")
        db.execute(
            text(
                f"""
            INSERT INTO playlist_songs (playlist_id, song_id, added_at)
            VALUES ({id}, {request.songId}, NOW())
            """
            )
        )
        logger.debug("Executed INSERT statement for playlist_songs")
        db.commit()
        logger.info(f"Successfully added song {request.songId} to playlist {id}")

        logger.debug("Fetching updated playlist data")
        return get_playlist(id, db)

    except Exception as e:
        logger.error(f"Failed to add song {request.songId} to playlist {id}: {str(e)}")
        db.rollback()
        logger.debug("Database transaction rolled back")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), f"/playlists/{id}/songs"
            ),
        )


if __name__ == "__main__":
    logger.info("Starting Fast API")
    uvicorn.run(app, host=HOST, port=PORT, log_config=LOGGING_CONFIG)
