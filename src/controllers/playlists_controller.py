import databases.playlists_database as playlists_db
import databases.songs_database as songs_db
import schemas
from fastapi import Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from db.database import get_db
from resources.logger import logger
from fastapi import APIRouter
from common.utils import create_error_response, serialize_playlist

router = APIRouter()

@router.post("/", status_code=201, response_model=schemas.PlaylistResponse)
def create_playlist(playlist: schemas.CreatePlaylistRequest, db: Session = Depends(get_db)):
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
        db_playlist, e = playlists_db.create_playlist(db, playlist.name, playlist.description)

        if not db_playlist:
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", str(e), "/playlists"),
            )
        return {"data": serialize_playlist(db_playlist)}
    except Exception as e:
        logger.error(f"Failed to create playlist '{playlist.name}': {str(e)}")
        logger.debug("Database transaction rolled back")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/playlists"),
        )


@router.get("/", response_model=schemas.PlaylistsResponse)
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
        playlists = playlists_db.get_all_playlists(db)
        return {"data": [serialize_playlist(p) for p in playlists]}

    except Exception as e:
        logger.error(f"Failed to fetch published playlists: {str(e)}")
        raise


@router.get("/{id}", response_model=schemas.PlaylistResponse)
def get_playlist(id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific playlist by its ID with all songs.
    
    This endpoint fetches a single playlist from the database using its unique ID,
    including all songs in the playlist with their metadata. Unlike the get all
    playlists endpoint, this returns the playlist regardless of its publication status.
    """
    logger.info(f"Fetching playlist with id={id}")
    try:
        playlist = playlists_db.get_playlist(db, id)

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

        serialized_playlist = serialize_playlist(playlist)
        logger.info(f"Successfully retrieved playlist {id} with {len(serialized_playlist.songs)} songs")
        return {"data": serialized_playlist}
    except Exception as e:
        logger.error(f"Failed to fetch playlist with id={id}: {str(e)}")
        raise


@router.delete("/{id}", status_code=204)
def delete_playlist(id: int, db: Session = Depends(get_db)):
    """
    Delete a playlist from the database.
    
    This endpoint permanently removes a playlist record from the database.
    If the playlist doesn't exist, returns a 404 Not Found error.
    The operation also removes all song associations from the playlist
    due to foreign key constraints, but the songs themselves remain in the database.
    """
    logger.info(f"Deleting playlist with id={id}")

    playlist = playlists_db.get_playlist(db, id)
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

    playlists_db.delete_playlist(db, playlist)
    return JSONResponse(status_code=204, content={"message": f"Playlist {id} deleted successfully"})


@router.post("/{id}/songs", response_model=schemas.PlaylistResponse)
def add_song_to_playlist( id: int, request: schemas.AddSongToPlaylistRequest, db: Session = Depends(get_db)):
    """
    Add an existing song to a playlist.
    
    This endpoint adds a song (identified by songId) to an existing playlist.
    It validates that both the playlist and song exist, and that the song
    is not already in the playlist. The song is added with the current timestamp.
    """
    logger.info(f"Adding song {request.songId} to playlist {id}")
    try:
        playlist = playlists_db.get_playlist(db, id)
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

        song = songs_db.get_song(db, request.songId)
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

        playlists_db.add_song_to_playlist(db, request.songId, id)

        logger.debug("Fetching updated playlist data")

        updated_playlist = playlists_db.get_playlist(db, id)

        return {"data": serialize_playlist(updated_playlist)}

    except Exception as e:
        logger.error(f"Failed to add song {request.songId} to playlist {id}: {str(e)}")
        # db.rollback()
        logger.debug("Database transaction rolled back")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), f"/playlists/{id}/songs"
            ),
        )
