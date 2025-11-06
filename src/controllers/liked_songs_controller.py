import databases.playlists_database as playlists_db
import databases.songs_database as songs_db
import databases.metrics_database as metrics_db
import schemas
from fastapi import Body, Depends
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter
from common.utils import create_error_response, serialize_playlist
from auth import verify_token

router = APIRouter()

@router.post("/", status_code=201)
async def create_liked_songs_playlist(user: dict = Depends(verify_token)):
    logger.info("Creating Liked Songs playlist")
    liked_songs_cover_url = "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/liked-songs/liked-songs.png"
    try:
        db_playlist, e = await playlists_db.create_playlist("Liked Songs", "", True, user["user_id"], liked_songs_cover_url, True)
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


@router.post("/{song_id}")
async def add_to_liked_songs(song_id: str, user: dict = Depends(verify_token)):
    liked_songs_playlist = await playlists_db.get_liked_songs_playlist(user["user_id"])
    
    if not liked_songs_playlist:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Liked songs playlist for user {user['user_id']} not found",
                f"/likedSongs/{user['user_id']}/songs"
            ),
        )
    playlist_id = str(liked_songs_playlist["_id"])    

    logger.info(f"Adding song {song_id} to liked songs and recording like metric")
    try:
        song = await songs_db.get_song(song_id)
        if not song:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song with id {song_id} not found",
                    f"/likedSongs/{user['user_id']}/songs"
                ),
            )

        # Add to liked songs playlist
        added = await playlists_db.add_song_to_playlist(song_id, playlist_id)
        if not added:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    f"Failed to add song {song_id} to playlist {playlist_id}",
                    f"/likedSongs/{user['user_id']}/songs"
                ),
            )

        # Also record the like in metrics (only if not already liked)
        is_already_liked = await metrics_db.is_liked_by_user(user["user_id"], song_id, "song")
        if not is_already_liked:
            _, error = await metrics_db.toggle_like(user["user_id"], song_id, "song")
            if error:
                logger.warning(f"Failed to record like metric for song {song_id}: {error}")

        updated_playlist = await playlists_db.get_playlist(playlist_id, user)
        songs = await playlists_db.get_songs_from_playlist(playlist_id)
        return {"data": serialize_playlist(updated_playlist, songs)}

    except Exception as e:
        logger.error(f"Failed to add song {song_id} to liked songs: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/likedSongs/{user['user_id']}/songs"),
        )


@router.delete("/{song_id}")
async def remove_from_liked_songs(song_id: str, user: dict = Depends(verify_token)):
    liked_songs_playlist = await playlists_db.get_liked_songs_playlist(user["user_id"])
    
    if not liked_songs_playlist:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Liked songs playlist for user {user['user_id']} not found",
                f"/likedSongs/{user['user_id']}/songs"
            ),
        )
    playlist_id = str(liked_songs_playlist["_id"])

    logger.info(f"Removing song {song_id} from liked songs and removing like metric")
    try:
        song = await songs_db.get_song(song_id)
        if not song:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song with id {song_id} not found",
                    f"/likedSongs/{user['user_id']}/songs/{song_id}"
                ),
            )

        removed = await playlists_db.remove_song_from_playlist(song_id, playlist_id)
        if not removed:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song {song_id} not found in playlist {playlist_id}",
                    f"/likedSongs/{user['user_id']}/songs/{song_id}"
                ),
            )

        # Also remove the like from metrics (only if currently liked)
        is_liked = await metrics_db.is_liked_by_user(user["user_id"], song_id, "song")
        if is_liked:
            _, error = await metrics_db.toggle_like(user["user_id"], song_id, "song")
            if error:
                logger.warning(f"Failed to remove like metric for song {song_id}: {error}")

        updated_playlist = await playlists_db.get_playlist(playlist_id, user)
        songs = await playlists_db.get_songs_from_playlist(playlist_id)
        return {"data": serialize_playlist(updated_playlist, songs)}

    except Exception as e:
        logger.error(f"Failed to remove song {song_id} from liked songs: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request",
                str(e),
                f"/likedSongs/{user['user_id']}/songs/{song_id}"
            ),
        )


@router.get("/")
async def get_liked_songs(user: dict = Depends(verify_token)):
    try:
        liked_songs = await playlists_db.get_liked_songs_playlist(user["user_id"])
        
        if liked_songs is None:
            logger.warning(f"Liked songs playlist for user {user['user_id']} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Liked songs playlist for user {user['user_id']} not found",
                    f"/likedSongs/{user['user_id']}",
                ),
            )

        playlist_id = str(liked_songs["_id"])
        songs = await playlists_db.get_songs_from_playlist(playlist_id)
        serialized_playlist = serialize_playlist(liked_songs, songs)
        logger.info(f"Successfully retrieved playlist {playlist_id} with {len(liked_songs['songs'])} songs")
        return {"data": serialized_playlist}
    except Exception as e:
        logger.error(f"Failed to fetch liked songs for user {user['user_id']}: {str(e)}")
        raise