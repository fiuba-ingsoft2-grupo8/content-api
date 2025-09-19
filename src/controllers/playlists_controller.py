import databases.playlists_database as playlists_db
import databases.songs_database as songs_db
import schemas
from fastapi import Depends
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter
from common.utils import create_error_response, serialize_playlist

router = APIRouter()

@router.post("/", status_code=201)
async def create_playlist(playlist: schemas.CreatePlaylistRequest):
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
        db_playlist, e = await playlists_db.create_playlist(playlist.name, playlist.description)
        if not db_playlist:
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", str(e), "/playlists"),
            )
        return {"data": serialize_playlist(db_playlist)}
    except Exception as e:
        logger.error(f"Failed to create playlist '{playlist.name}': {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/playlists"),
        )


@router.get("/")
async def get_all_playlists():
    """
    Retrieve all playlists with their songs.
    
    This endpoint fetches all playlists, ordered by publication date
    (newest first) and includes all songs in each playlist with
    their metadata.
    """
    logger.info("Fetching all published playlists")
    try:
        playlists = await playlists_db.get_playlists(False)
        serialized_playlists = []
        for playlist in playlists:
            songs = await playlists_db.get_songs_from_playlist(playlist["_id"])
            serialized_playlists.append(serialize_playlist(playlist, songs))
        return {"data": serialized_playlists}

    except Exception as e:
        logger.error(f"Failed to fetch published playlists: {str(e)}")
        raise


@router.get("/")
async def get_published_playlists():
    """
    Retrieve all published playlists with their songs.
    
    This endpoint fetches all playlists that are marked as published,
    ordered by publication date (newest first) and includes all songs
    in each playlist with their metadata. Only published playlists are
    returned to maintain privacy of unpublished playlists.
    """
    logger.info("Fetching all published playlists")
    try:
        playlists = await playlists_db.get_playlists(True)
        serialized_playlists = []
        for playlist in playlists:
            songs = await playlists_db.get_songs_from_playlist(playlist["_id"])
            serialized_playlists.append(serialize_playlist(playlist, songs))
        return {"data": serialized_playlists}

    except Exception as e:
        logger.error(f"Failed to fetch published playlists: {str(e)}")
        raise


@router.get("/{id}")
async def get_playlist(id: str):
    """
    Retrieve a specific playlist by its ID with all songs.
    
    This endpoint fetches a single playlist from the database using its unique ID,
    including all songs in the playlist with their metadata. Unlike the get all
    playlists endpoint, this returns the playlist regardless of its publication status.
    """
    logger.info(f"Fetching playlist with id={id}")
    try:
        playlist = await playlists_db.get_playlist(id)

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

        songs = await playlists_db.get_songs_from_playlist(id)
        serialized_playlist = serialize_playlist(playlist, songs)
        logger.info(f"Successfully retrieved playlist {id} with {len(playlist['songs'])} songs")
        return {"data": serialized_playlist}
    except Exception as e:
        logger.error(f"Failed to fetch playlist with id={id}: {str(e)}")
        raise


@router.delete("/{id}", status_code=204)
async def delete_playlist(id: str):
    """
    Delete a playlist from the database.
    
    This endpoint permanently removes a playlist record from the database.
    If the playlist doesn't exist, returns a 404 Not Found error.
    The operation also removes all song associations from the playlist
    due to foreign key constraints, but the songs themselves remain in the database.
    """
    logger.info(f"Deleting playlist with id={id}")

    playlist = await playlists_db.get_playlist(id)
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

    await playlists_db.delete_playlist(playlist)
    return JSONResponse(status_code=204, content=None)


@router.post("/{id}/songs")
async def add_song_to_playlist(id: str, request: schemas.ModifySongInPlaylistRequest):
    """
    Add an existing song to a playlist.

    This endpoint adds a song (identified by songId) to an existing playlist.
    It validates that both the playlist and song exist, and that the song
    is not already in the playlist. The song is added with the current timestamp.
    """

    logger.info(f"Adding song {request.songId} to playlist {id}")
    try:
        playlist = await playlists_db.get_playlist(id)
        if not playlist:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Playlist with id {id} not found",
                    f"/playlists/{id}/songs"
                ),
            )

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

        added = await playlists_db.add_song_to_playlist(request.songId, id)
        if not added:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    f"Failed to add song {request.songId} to playlist {id}",
                    f"/playlists/{id}/songs"
                ),
            )

        updated_playlist = await playlists_db.get_playlist(id)
        songs = await playlists_db.get_songs_from_playlist(id)
        return {"data": serialize_playlist(updated_playlist, songs)}

    except Exception as e:
        logger.error(f"Failed to add song {request.songId} to playlist {id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/playlists/{id}/songs"),
        )


@router.delete("/{id}/songs")
async def remove_song_from_playlist(id: str, request: schemas.ModifySongInPlaylistRequest):
    """
    Remove a song from a playlist.

    This endpoint removes a song (identified by song_id) from an existing playlist.
    It validates that both the playlist and song exist, and that the song is currently
    in the playlist. If found, the song is removed and the updated playlist is returned.
    """

    logger.info(f"Removing song {request.songId} from playlist {id}")
    try:
        playlist = await playlists_db.get_playlist(id)
        if not playlist:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Playlist with id {id} not found",
                    f"/playlists/{id}/songs/{request.songId}"
                ),
            )

        song = await songs_db.get_song(request.songId)
        if not song:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song with id {request.songId} not found",
                    f"/playlists/{id}/songs/{request.songId}"
                ),
            )

        removed = await playlists_db.remove_song_from_playlist(request.songId, id)
        if not removed:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song {request.songId} not found in playlist {id}",
                    f"/playlists/{id}/songs/{request.songId}"
                ),
            )

        updated_playlist = await playlists_db.get_playlist(id)
        songs = await playlists_db.get_songs_from_playlist(id)
        return {"data": serialize_playlist(updated_playlist, songs)}

    except Exception as e:
        logger.error(f"Failed to remove song {request.songId} from playlist {id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request",
                str(e),
                f"/playlists/{id}/songs/{request.songId}"
            ),
        )


@router.post("/{id}/publish")
async def publish_playlist(id: str):
    """
    Make a playlist public.

    This endpoint marks the specified playlist, identified by it's unique ID, as published (is_published = True).
    It first verifies that the playlist exists.
    """
    logger.info(f"Publishing playlist with id {id}")
    playlist = await playlists_db.get_playlist(id)
    if not playlist:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Playlist with id {id} not found",
                f"/playlists/{id}/songs"
            ),
        )
    try:
        published = await playlists_db.change_playlist_state(playlist, True)
        if not published:
            logger.error(f"Failed to publish playlist with id {id}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", "", f"/playlists/{id}/songs"),
            )
        logger.info(f"Successfully published playlist {id}")
        return {"data": published}
    except Exception as e:
        logger.error(f"Failed to publish playlist with id {id}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", "", f"/playlists/{id}/songs"),
        )


@router.post("/{id}/private")
async def private_playlist(id: str):
    """
    Make a playlist private.

    This endpoint marks the specified playlist, identified by it's unique ID, as private (is_published = True).
    It first verifies that the playlist exists.
    """
    logger.info(f"Making playlist with id {id} private")
    playlist = await playlists_db.get_playlist(id)
    if not playlist:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Playlist with id {id} not found",
                f"/playlists/{id}/songs"
            ),
        )
    try:
        private = await playlists_db.change_playlist_state(playlist, False)
        if not private:
            logger.error(f"Failed to make playlist with id {id} private")
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", "", f"/playlists/{id}/songs"),
            )
        logger.info(f"Successfully made playlist {id} private")
        return {"data": private}
    except Exception as e:
        logger.error(f"Failed to make playlist with id {id} private")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", {str(e)}, f"/playlists/{id}/songs"),
        )
