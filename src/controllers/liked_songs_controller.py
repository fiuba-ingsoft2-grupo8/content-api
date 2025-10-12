import databases.playlists_database as playlists_db
import databases.songs_database as songs_db
import schemas
from fastapi import Body
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter
from common.utils import create_error_response, serialize_playlist

router = APIRouter()

@router.post("/", status_code=201)
async def create_liked_songs_playlist(request: schemas.ModifyPlaylistRequest):
    logger.info("Creating Liked Songs playlist")
    try:
        db_playlist, e = await playlists_db.create_playlist("Liked Songs", "", True, request.userId, "liked_songs.png", True)
        if not db_playlist:
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", str(e), "/playlists"),
            )
        return {"data": serialize_playlist(db_playlist, [])}
    except Exception as e:
        logger.error(f"Failed to create Liked Songs playlist: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/playlists"),
        )


@router.post("/addSongs")
async def add_to_liked_songs(request: schemas.ModifySongInPlaylistRequest):
    liked_songs = await playlists_db.get_liked_songs_playlist(request.userId)
    
    if not liked_songs:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Playlist with id {id} not found",
                f"/playlists/{id}/songs"
            ),
        )
    id = str(liked_songs["_id"])    

    logger.info(f"Adding song {request.songId} to playlist {id}")
    try:
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

        print(f"\n1. passing id: {id}\n")
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

        print(f"\n2. passing id: {id}\n")
        updated_playlist = await playlists_db.get_playlist(id, request.userId)
        songs = await playlists_db.get_songs_from_playlist(id)
        return {"data": serialize_playlist(updated_playlist, songs)}

    except Exception as e:
        logger.error(f"Failed to add song {request.songId} to playlist {id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/playlists/{id}/songs"),
        )


@router.delete("/")
async def remove_from_liked_songs(request: schemas.ModifySongInPlaylistRequest = Body(...)):
    liked_songs = await playlists_db.get_liked_songs_playlist(request.userId)
    
    if not liked_songs:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Playlist with id {id} not found",
                f"/playlists/{id}/songs"
            ),
        )
    id = str(liked_songs["_id"])

    logger.info(f"Removing song {request.songId} from playlist {id}")
    try:
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

        updated_playlist = await playlists_db.get_playlist(id, request.userId)
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


@router.get("/")
async def get_liked_songs(userId: str = None):
    try:
        liked_songs = await playlists_db.get_liked_songs_playlist(userId)
        id = str(liked_songs["_id"])
        if liked_songs is None:
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
        serialized_playlist = serialize_playlist(liked_songs, songs)
        logger.info(f"Successfully retrieved playlist {id} with {len(liked_songs['songs'])} songs")
        return {"data": serialized_playlist}
    except Exception as e:
        logger.error(f"Failed to fetch playlist with id={id}: {str(e)}")
        raise