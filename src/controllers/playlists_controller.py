import random
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, UploadFile, File
from fastapi.responses import JSONResponse

import databases.playlists_database as playlists_db
import databases.songs_database as songs_db
import databases.storage_database as storage_db
import schemas
from auth import verify_token, is_authorized
from common.utils import create_error_response, serialize_playlist, DEFAULT_COVERS
from resources.logger import logger

router = APIRouter()


def _parse_iso(dt: str | None):
    if not dt:
        return None
    try:
        # Soporta "YYYY-MM-DD" o ISO con hora
        if len(dt) == 10:
            return datetime.fromisoformat(dt).replace(tzinfo=timezone.utc)
        d = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Playlist created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "name": "My Favorites",
                            "description": "My favorite songs collection",
                            "userId": "user_123",
                            "is_published": False,
                            "published_at": "2025-11-10T00:00:00Z",
                            "coverUrl": "https://example.com/cover.jpg",
                            "songs": []
                        }
                    }
                }
            }
        }
    }
)
async def create_playlist(playlist: schemas.CreatePlaylistRequest, user: dict = Depends(verify_token)):
    logger.info(f"Creating playlist: name='{playlist.name}', description='{playlist.description}'")
    cover_url = playlist.coverUrl if playlist.coverUrl else random.choice(DEFAULT_COVERS)

    try:
        db_playlist, e = await playlists_db.create_playlist(
            playlist.name, playlist.description, False, user["user_id"], cover_url, False
        )
        if not db_playlist:
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", str(e), "/playlists"),
            )
        return {"data": serialize_playlist(db_playlist, [])}
    except Exception as e:
        logger.error(f"Failed to create playlist '{playlist.name}': {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/playlists"),
        )


@router.get(
    "/",
    responses={
        200: {
            "description": "List of playlists",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "_id": "507f1f77bcf86cd799439011",
                                "name": "My Favorites",
                                "description": "My favorite songs",
                                "userId": "user_123",
                                "is_published": True,
                                "published_at": "2025-11-10T00:00:00Z",
                                "coverUrl": "https://example.com/cover.jpg",
                                "songs": []
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_playlists(
    isPublished: bool = False,
    # nuevos filtros catálogo:
    state: str | None = None,                 # "Publicado" | "Programado"
    publishedFrom: str | None = None,         # ISO date/datetime
    publishedTo: str | None = None,           # ISO date/datetime
    user: dict = Depends(verify_token),
):
    """
    Catálogo (playlists) con filtros:
    - state: "Publicado"/"Programado" (Publicado => is_published=True; Programado => is_published=False)
    - publishedFrom/publishedTo: rango sobre published_at (sólo aplica cuando is_published=True)
    """
    is_backoffice = user.get("user_type") == "backoffice"
    owner_id = None if is_backoffice else user["user_id"]

    # normalizamos "state"
    st = (state or "").strip().lower()
    if st not in ("", "publicado", "programado"):
        st = ""

    dt_from = _parse_iso(publishedFrom)
    dt_to = _parse_iso(publishedTo)

    logger.info(
        f"Fetching playlists (isPublished={isPublished}, userId={owner_id}, state={st}, from={dt_from}, to={dt_to})"
    )
    try:
        playlists = await playlists_db.get_playlists(
            published=isPublished,
            userId=owner_id,
            state=st,
            published_from=dt_from,
            published_to=dt_to,
        )
        serialized_playlists = []
        for playlist in playlists:
            songs = await playlists_db.get_songs_from_playlist(playlist["_id"])
            serialized_playlists.append(serialize_playlist(playlist, songs))
        return {"data": serialized_playlists}
    except Exception as e:
        logger.error(f"Failed to fetch published playlists: {str(e)}")
        raise


@router.get("/{id}")
async def get_playlist(id: str, user: dict = Depends(verify_token)):
    """
    Retrieve a specific playlist by its ID with all songs.
    Access rules:
    - Published playlists: accessible by anyone
    - Unpublished playlists: only accessible by owner or backoffice users
    """
    logger.info(f"Fetching playlist with id={id}, user={user.get('user_id')}, user_type={user.get('user_type')}")
    try:
        playlist = await playlists_db.get_playlist(id, user)
        if playlist is None:
            logger.warning(f"Playlist with id={id} not found or access denied")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Playlist with id {id} not found or you don't have access",
                    f"/playlists/{id}",
                ),
            )

        songs = await playlists_db.get_songs_from_playlist(id)
        serialized_playlist = serialize_playlist(playlist, songs)
        logger.info(f"Successfully retrieved playlist {id} with {len(songs)} songs")
        return {"data": serialized_playlist}
    except Exception as e:
        logger.error(f"Failed to fetch playlist with id={id}: {str(e)}")
        raise


@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(playlist_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Deleting playlist with id={playlist_id}")

    playlist = await playlists_db.get_playlist(playlist_id, user)
    if playlist is None:
        logger.warning(f"Playlist with id={playlist_id} not found for deletion")
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404,
                "Not Found",
                f"Playlist with id {playlist_id} not found",
                f"/playlists/{playlist_id}",
            ),
        )
    
    if not is_authorized(user, playlist["userId"]):
        logger.warning(f"User not authorized to delete playlist {playlist_id}")
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403,
                "Forbidden",
                "You are not authorized to delete this playlist",
                f"/playlists/{playlist_id}",
            ),
        )

    await playlists_db.delete_playlist(playlist)
    return JSONResponse(status_code=204, content=None)


@router.post("/{playlist_id}/songs/{song_id}")
async def add_song_to_playlist(playlist_id: str, song_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Adding song {song_id} to playlist {playlist_id}")
    try:
        playlist = await playlists_db.get_playlist(playlist_id, user)
        if not playlist:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Playlist with id {playlist_id} not found",
                    f"/playlists/{playlist_id}/songs/{song_id}"
                ),
            )
        
        if not is_authorized(user, playlist["userId"]):
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to modify this playlist",
                    f"/playlists/{playlist_id}/songs/{song_id}"
                ),
            )

        song = await songs_db.get_song(song_id)
        if not song:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song with id {song_id} not found",
                    f"/playlists/{playlist_id}/songs/{song_id}"
                ),
            )

        added = await playlists_db.add_song_to_playlist(song_id, playlist_id)
        if not added:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    f"Failed to add song {song_id} to playlist {playlist_id}",
                    f"/playlists/{playlist_id}/songs/{song_id}"
                ),
            )

        updated_playlist = await playlists_db.get_playlist(playlist_id, user)
        songs = await playlists_db.get_songs_from_playlist(playlist_id)
        return {"data": serialize_playlist(updated_playlist, songs)}

    except Exception as e:
        logger.error(f"Failed to add song {song_id} to playlist {playlist_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/playlists/{playlist_id}/songs/{song_id}"),
        )


@router.delete("/{playlist_id}/songs/{song_id}")
async def remove_song_from_playlist(playlist_id: str, song_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Removing song {song_id} from playlist {playlist_id}")
    try:
        playlist = await playlists_db.get_playlist(playlist_id, user)
        if not playlist:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Playlist with id {playlist_id} not found",
                    f"/playlists/{playlist_id}/songs/{song_id}"
                ),
            )
        
        if not is_authorized(user, playlist["userId"]):
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to modify this playlist",
                    f"/playlists/{playlist_id}/songs/{song_id}"
                ),
            )

        song = await songs_db.get_song(song_id)
        if not song:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song with id {song_id} not found",
                    f"/playlists/{playlist_id}/songs/{song_id}"
                ),
            )

        removed = await playlists_db.remove_song_from_playlist(song_id, playlist_id)
        if not removed:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song {song_id} not found in playlist {playlist_id}",
                    f"/playlists/{playlist_id}/songs/{song_id}"
                ),
            )

        updated_playlist = await playlists_db.get_playlist(playlist_id, user)
        songs = await playlists_db.get_songs_from_playlist(playlist_id)
        return {"data": serialize_playlist(updated_playlist, songs)}

    except Exception as e:
        logger.error(f"Failed to remove song {song_id} from playlist {playlist_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request",
                str(e),
                f"/playlists/{playlist_id}/songs/{song_id}"
            ),
        )


@router.post("/{playlist_id}/publish")
async def publish_playlist(playlist_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Publishing playlist with id {playlist_id}")
    playlist = await playlists_db.get_playlist(playlist_id, user)
    if not playlist:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Playlist with id {playlist_id} not found",
                f"/playlists/{playlist_id}/publish"
            ),
        )
    
    if not is_authorized(user, playlist["userId"]):
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403,
                "Forbidden",
                "You are not authorized to publish this playlist",
                f"/playlists/{playlist_id}/publish",
            ),
        )
    try:
        published = await playlists_db.change_playlist_state(playlist, True)
        if not published:
            logger.error(f"Failed to publish playlist with id {playlist_id}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", "", f"/playlists/{playlist_id}/songs"),
            )
        logger.info(f"Successfully published playlist {playlist_id}")
        return {"data": published}
    except Exception:
        logger.error(f"Failed to publish playlist with id {playlist_id}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", "", f"/playlists/{playlist_id}/songs"),
        )


@router.post("/{playlist_id}/private")
async def private_playlist(playlist_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Making playlist with id {playlist_id} private")
    playlist = await playlists_db.get_playlist(playlist_id, user)
    if not playlist:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404,
                "Not Found",
                f"Playlist with id {playlist_id} not found",
                f"/playlists/{playlist_id}/private"
            ),
        )
    
    if not is_authorized(user, playlist["userId"]):
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403,
                "Forbidden",
                "You are not authorized to modify this playlist",
                f"/playlists/{playlist_id}/private",
            ),
        )
    
    try:
        private = await playlists_db.change_playlist_state(playlist, False)
        if not private:
            logger.error(f"Failed to make playlist with id {playlist_id} private")
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", "", f"/playlists/{playlist_id}/songs"),
            )
        logger.info(f"Successfully made playlist {playlist_id} private")
        return {"data": private}
    except Exception as e:
        logger.error(f"Failed to make playlist with id {playlist_id} private")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/playlists/{playlist_id}/songs"),
        )


@router.post("/{playlist_id}/upload-cover")
async def upload_playlist_cover(playlist_id: str, file: UploadFile = File(...), user: dict = Depends(verify_token)):
    """
    Uploads a playlist cover image to Supabase Storage and updates the playlist document.
    Only the owner or backoffice users can upload covers.
    """
    playlist = await playlists_db.get_playlist(playlist_id, user)
    if not playlist:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404,
                "Not Found",
                f"Playlist with id {playlist_id} not found",
                f"/playlists/{playlist_id}/upload-cover"
            ),
        )
    
    if not is_authorized(user, playlist["userId"]):
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403,
                "Forbidden",
                "You are not authorized to upload a cover for this playlist",
                f"/playlists/{playlist_id}/upload-cover",
            ),
        )

    try:
        result = await storage_db.upload_cover_image("playlists", user["user_id"], file)
        cover_url = result["coverUrl"]

        updated = await playlists_db.update_playlist_cover(playlist, cover_url)
        if not updated:
            logger.error(f"Failed to update playlist cover for id {playlist_id}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    "Failed to update playlist cover",
                    f"/playlists/{playlist_id}/upload-cover"
                ),
            )

        logger.info(f"Successfully updated playlist cover for {playlist_id}")
        return {"coverUrl": cover_url}

    except Exception as e:
        logger.error(f"Failed to upload playlist cover: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                f"/playlists/{playlist_id}/upload-cover"
            ),
        )


# -------- NUEVO (develop): Reordenar canciones --------
@router.put("/{playlist_id}/reorder")
async def reorder_playlist(playlist_id: str, request: schemas.ReorderRequest, user: dict = Depends(verify_token)):
    """
    Reorder songs in a playlist.
    """
    try:
        logger.info(f"Reordering playlist {playlist_id}")
        success = await playlists_db.reorder_songs_in_playlist(playlist_id, request.songs)
        if not success:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    "Failed to reorder playlist",
                    f"/playlists/{playlist_id}/reorder"
                )
            )
        logger.info(f"Successfully reordered playlist {playlist_id}")
        return {"message": "Playlist order updated successfully"}

    except Exception as e:
        logger.error(f"Error reordering playlist {playlist_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error", str(e), f"/playlists/{playlist_id}/reorder"
            ),
        )


# -------- NUEVO (feature): Editar metadata de descripción --------
@router.patch("/{playlist_id}/description", status_code=200)
async def patch_playlist_description(
    playlist_id: str,
    body: dict = Body(...),  # espera {"description": "texto"}
    user: dict = Depends(verify_token),
):
    """
    Edita únicamente la descripción de la playlist.
    Body: {"description": "<texto>"}
    """
    desc = body.get("description", "")
    if not isinstance(desc, str):
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", "description must be a string"),
        )

    playlist = await playlists_db.get_playlist(playlist_id, user)
    if not playlist:
        return JSONResponse(
            status_code=404,
            content=create_error_response(404, "Not Found", f"Playlist {playlist_id} not found", f"/playlists/{playlist_id}/description"),
        )

    if not is_authorized(user, playlist["userId"]):
        return JSONResponse(
            status_code=403,
            content=create_error_response(403, "Forbidden", "Not authorized to edit this playlist"),
        )

    ok = await playlists_db.update_playlist_description(playlist_id, desc)
    if not ok:
        return JSONResponse(
            status_code=500,
            content=create_error_response(500, "Internal Server Error", "Failed to update description"),
        )

    # devolver la playlist actualizada
    updated = await playlists_db.get_playlist(playlist_id, user)
    songs = await playlists_db.get_songs_from_playlist(playlist_id)
    return {"data": serialize_playlist(updated, songs)}


# Variante PUT para metadata (por ahora solo description)
from pydantic import BaseModel as _BaseModel  # evitar colisión con schemas.BaseModel

class UpdatePlaylistMetadataRequest(_BaseModel):
    description: str  # solo esto por ahora


@router.put("/{playlist_id}/metadata", status_code=200)
async def update_playlist_metadata(
    playlist_id: str,
    payload: UpdatePlaylistMetadataRequest,
    user: dict = Depends(verify_token),
):
    playlist = await playlists_db.get_playlist(playlist_id, user)
    if not playlist:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Playlist with id {playlist_id} not found or access denied",
                f"/playlists/{playlist_id}/metadata",
            ),
        )

    # Autorización: dueño o backoffice
    if not is_authorized(user, playlist.get("userId")):
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403, "Forbidden",
                "You are not authorized to edit this playlist",
                f"/playlists/{playlist_id}/metadata",
            ),
        )

    ok = await playlists_db.update_playlist_description(playlist_id, payload.description)
    if not ok:
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request",
                "Failed to update playlist description",
                f"/playlists/{playlist_id}/metadata",
            ),
        )

    updated = await playlists_db.get_playlist(playlist_id, user)
    songs = await playlists_db.get_songs_from_playlist(playlist_id)
    return {"data": serialize_playlist(updated, songs)}
