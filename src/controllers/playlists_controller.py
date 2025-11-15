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
    """
    Crear una nueva playlist personal.
    
    Este endpoint permite crear una playlist personalizada que el usuario puede usar para organizar
    sus canciones favoritas. Las playlists se crean como privadas por defecto y pueden ser publicadas
    posteriormente.
    
    **Cuerpo de la solicitud:**
    - name: Nombre de la playlist (requerido)
    - description: Descripción opcional de la playlist
    - coverUrl: URL de portada personalizada (opcional, se asigna una aleatoria si no se proporciona)
    
    **Comportamiento:**
    - La playlist se crea vacía, las canciones se agregan posteriormente
    - Se crea como privada (is_published = false)
    - Se asigna una portada aleatoria del catálogo por defecto si no se especifica
    - El usuario autenticado es automáticamente el dueño
    
    **Retorna:**
    - 201: Playlist creada exitosamente
    - 400: Error en los datos proporcionados
    """
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
    Obtener playlists con filtros avanzados de catálogo.
    
    Este endpoint permite listar y filtrar playlists con diversos criterios. Los usuarios regulares
    solo ven sus propias playlists, mientras que los usuarios backoffice pueden ver todas.
    
    **Parámetros de consulta:**
    - isPublished: Filtrar por estado publicado (true) o privado (false) - por defecto: false
    - state: Estado de publicación - "Publicado" (publicadas) o "Programado" (privadas pendientes)
    - publishedFrom: Fecha inicial del rango de publicación (formato ISO date/datetime)
    - publishedTo: Fecha final del rango de publicación (formato ISO date/datetime)
    
    **Comportamiento:**
    - state="Publicado": filtra playlists con is_published=true
    - state="Programado": filtra playlists con is_published=false
    - Los filtros de fecha aplican sobre el campo published_at (solo para playlists publicadas)
    - Usuarios regulares: solo ven sus propias playlists
    - Usuarios backoffice: ven todas las playlists del sistema
    
    **Retorna:**
    - 200: Lista de playlists que cumplen los criterios, cada una con sus canciones
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
    Obtener una playlist específica por su ID con todas sus canciones.
    
    Este endpoint retorna los detalles completos de una playlist incluyendo su metadata
    y la lista completa de canciones en su orden original.
    
    **Parámetros de ruta:**
    - id: ID de la playlist
    
    **Reglas de acceso:**
    - Playlists publicadas: accesibles por cualquier usuario autenticado
    - Playlists privadas: solo accesibles por el dueño o usuarios backoffice
    
    **Información retornada:**
    - Metadata de la playlist (nombre, descripción, portada, estado de publicación, fecha)
    - Lista completa de canciones con detalles (título, artista, duración, portada)
    - Orden de las canciones preservado
    
    **Retorna:**
    - 200: Playlist encontrada con todas sus canciones
    - 404: Playlist no encontrada o sin acceso (privada de otro usuario)
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
    """
    Eliminar una playlist permanentemente.
    
    Este endpoint borra completamente una playlist de la base de datos. La eliminación es permanente
    e irreversible. Las canciones en sí no se eliminan, solo la playlist que las agrupaba.
    
    **Parámetros de ruta:**
    - playlist_id: ID de la playlist a eliminar
    
    **Autorización:**
    - Solo el dueño de la playlist o usuarios backoffice pueden eliminarla
    
    **Retorna:**
    - 204: Playlist eliminada exitosamente (sin contenido)
    - 403: No autorizado para eliminar esta playlist
    - 404: Playlist no encontrada
    """
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
    """
    Agregar una canción a una playlist.
    
    Este endpoint permite agregar una canción específica al final de una playlist.
    La canción se agrega en la última posición de la lista actual.
    
    **Parámetros de ruta:**
    - playlist_id: ID de la playlist
    - song_id: ID de la canción a agregar
    
    **Validaciones:**
    - La playlist debe existir
    - La canción debe existir
    - El usuario debe ser el dueño de la playlist o backoffice
    - No se puede agregar la misma canción dos veces
    
    **Retorna:**
    - 200: Canción agregada exitosamente con la playlist actualizada
    - 400: Error al agregar (ej: canción ya está en la playlist)
    - 403: No autorizado para modificar esta playlist
    - 404: Playlist o canción no encontrada
    """
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
    """
    Quitar una canción de una playlist.
    
    Este endpoint permite remover una canción específica de una playlist. El orden de las
    canciones restantes se mantiene.
    
    **Parámetros de ruta:**
    - playlist_id: ID de la playlist
    - song_id: ID de la canción a quitar
    
    **Validaciones:**
    - La playlist debe existir
    - La canción debe existir
    - La canción debe estar actualmente en la playlist
    - El usuario debe ser el dueño de la playlist o backoffice
    
    **Retorna:**
    - 200: Canción quitada exitosamente con la playlist actualizada
    - 403: No autorizado para modificar esta playlist
    - 404: Playlist no encontrada, canción no encontrada, o canción no está en la playlist
    """
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
    """
    Publicar una playlist privada.
    
    Este endpoint hace pública una playlist que estaba en modo privado. Una vez publicada,
    la playlist será visible para todos los usuarios y aparecerá en el perfil público del creador.
    Se registra la fecha de publicación.
    
    **Parámetros de ruta:**
    - playlist_id: ID de la playlist a publicar
    
    **Comportamiento:**
    - Cambia el estado de is_published a true
    - Registra la fecha y hora de publicación (published_at)
    - La playlist aparece en búsquedas públicas y en el perfil del usuario
    
    **Autorización:**
    - Solo el dueño de la playlist o usuarios backoffice pueden publicarla
    
    **Retorna:**
    - 200: Playlist publicada exitosamente
    - 400: Error al publicar
    - 403: No autorizado para publicar esta playlist
    - 404: Playlist no encontrada
    """
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
    """
    Hacer privada una playlist pública.
    
    Este endpoint revierte el estado de publicación de una playlist, haciéndola privada nuevamente.
    Una playlist privada solo es visible para su dueño y no aparece en búsquedas públicas.
    
    **Parámetros de ruta:**
    - playlist_id: ID de la playlist a hacer privada
    
    **Comportamiento:**
    - Cambia el estado de is_published a false
    - La playlist deja de aparecer en búsquedas públicas
    - Solo el dueño y usuarios backoffice pueden verla
    
    **Autorización:**
    - Solo el dueño de la playlist o usuarios backoffice pueden cambiar su privacidad
    
    **Retorna:**
    - 200: Playlist hecha privada exitosamente
    - 400: Error al cambiar el estado
    - 403: No autorizado para modificar esta playlist
    - 404: Playlist no encontrada
    """
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
    Subir una imagen de portada personalizada para una playlist.
    
    Este endpoint permite subir y establecer una imagen de portada personalizada para una playlist.
    La imagen se sube al almacenamiento de Supabase y se actualiza la URL en la playlist.
    
    **Parámetros de ruta:**
    - playlist_id: ID de la playlist
    
    **Parámetros:**
    - file: Archivo de imagen a subir (multipart/form-data)
    
    **Autorización:**
    - Solo el dueño de la playlist o usuarios backoffice pueden subir portadas
    
    **Retorna:**
    - 200: Portada subida y actualizada exitosamente con la nueva URL
    - 400: Error al actualizar la portada
    - 403: No autorizado para modificar esta playlist
    - 404: Playlist no encontrada
    - 500: Error interno del servidor
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
    Reordenar las canciones de una playlist.
    
    Este endpoint permite cambiar el orden de las canciones en una playlist. Se proporciona
    la lista completa de canciones en el nuevo orden deseado.
    
    **Parámetros de ruta:**
    - playlist_id: ID de la playlist
    
    **Cuerpo de la solicitud:**
    - songs: Lista completa de IDs de canciones en el nuevo orden
    
    **Validaciones:**
    - La lista debe contener todas las canciones actuales de la playlist
    - No se pueden agregar ni quitar canciones con este endpoint (solo reordenar)
    
    **Retorna:**
    - 200: Orden actualizado exitosamente
    - 400: Error al reordenar (ej: lista de canciones no coincide)
    - 500: Error interno del servidor
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
    """
    Actualizar los metadatos de una playlist (PUT).
    
    Este endpoint permite actualizar la información descriptiva de una playlist.
    Por ahora solo soporta la actualización de la descripción.
    
    **Parámetros de ruta:**
    - playlist_id: ID de la playlist
    
    **Cuerpo de la solicitud:**
    - description: Nueva descripción de la playlist
    
    **Autorización:**
    - Solo el dueño de la playlist o usuarios backoffice pueden actualizar metadatos
    
    **Retorna:**
    - 200: Metadatos actualizados exitosamente con la playlist completa
    - 400: Error al actualizar
    - 403: No autorizado para editar esta playlist
    - 404: Playlist no encontrada o sin acceso
    """
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
