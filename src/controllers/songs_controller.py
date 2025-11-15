import schemas
import databases.songs_database as songs_db
import databases.metrics_database as metrics_db
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter, Depends
from common.utils import create_error_response, serialize_song
from auth import verify_token, is_authorized

router = APIRouter()

@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Song created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "title": "Bohemian Rhapsody",
                            "artist": "Queen",
                            "duration": "354",
                            "artistId": "artist_123",
                            "isLiked": False
                        }
                    }
                }
            }
        }
    }
)
async def create_song(song: schemas.CreateSongRequest, user: dict = Depends(verify_token)):
    """
    Crear una nueva canción en la base de datos.
    
    Este endpoint permite a un artista registrar una nueva canción en el sistema. La canción
    se crea con información básica (título, duración) y se asocia automáticamente al artista
    autenticado. Las canciones creadas pueden posteriormente ser agregadas a colecciones o playlists.
    
    **Cuerpo de la solicitud:**
    - title: Título de la canción (requerido)
    - duration: Duración de la canción en segundos (requerido)
    
    **Comportamiento:**
    - El artista (stage_name) se obtiene automáticamente del usuario autenticado
    - La canción se crea asociada al artistId del usuario
    - Se inicializa sin portada ni colección asignada
    
    **Validaciones:**
    - El usuario debe tener un stage_name (ser artista)
    
    **Retorna:**
    - 201: Canción creada exitosamente
    - 400: Error en los datos proporcionados o usuario no es artista
    """
    logger.info(f"Creating song: title='{song.title}', artist='{user['stage_name']}', duration='{song.duration}'")

    (db_song, e) = await songs_db.create_song(song.title, user["stage_name"], song.duration, user["user_id"])
    if not db_song:
        return JSONResponse(
        status_code=400,
        content=create_error_response(400, "Bad Request", str(e), "/songs"),
    )
    return { "data": serialize_song(db_song) }


@router.get(
    "/",
    responses={
        200: {
            "description": "List of songs",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "_id": "507f1f77bcf86cd799439011",
                                "title": "Bohemian Rhapsody",
                                "artist": "Queen",
                                "duration": "354",
                                "artistId": "artist_123",
                                "isLiked": False
                            },
                            {
                                "_id": "507f1f77bcf86cd799439012",
                                "title": "Imagine",
                                "artist": "John Lennon",
                                "duration": "183",
                                "artistId": "artist_456",
                                "isLiked": True
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_all_songs(includeUnpublished: bool = False, user: dict = Depends(verify_token)):
    """
    Obtener todas las canciones disponibles en el catálogo.
    
    Este endpoint retorna el listado completo de canciones del sistema. Por defecto solo muestra
    canciones publicadas (en colecciones ya lanzadas o canciones standalone), pero puede incluir
    canciones no publicadas del usuario si se especifica.
    
    **Parámetros de consulta:**
    - includeUnpublished: Si es true, incluye canciones no publicadas del usuario autenticado (por defecto: false)
    
    **Comportamiento:**
    - Por defecto: solo canciones en colecciones publicadas o canciones standalone
    - Con includeUnpublished=true: incluye también canciones del usuario en colecciones no publicadas
    - Útil para que artistas vean su catálogo completo incluyendo lanzamientos futuros
    
    **Retorna:**
    - 200: Lista completa de canciones que cumplan los criterios
    """
    logger.info(f"Fetching all songs (includeUnpublished={includeUnpublished})")
    try:
        songs = await songs_db.get_all_songs(includeUnpublished, user["user_id"])
        return { "data": [serialize_song(song) for song in songs] }
    except Exception as e:
        logger.error(f"Failed to fetch all songs: {str(e)}")
        raise


@router.get(
    "/{id}",
    responses={
        200: {
            "description": "Song details",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "title": "Bohemian Rhapsody",
                            "artist": "Queen",
                            "duration": "354",
                            "artistId": "artist_123",
                            "isLiked": False
                        }
                    }
                }
            }
        }
    }
)
async def get_song(id: str, includeUnpublished: bool = False, user: dict = Depends(verify_token)):
    """
    Obtener una canción específica por su ID.
    
    Este endpoint retorna los detalles completos de una canción incluyendo título, artista,
    duración, portada y estado de "like" para el usuario autenticado. Por defecto solo retorna
    canciones publicadas, pero puede mostrar canciones no publicadas del usuario si se especifica.
    
    **Parámetros de ruta:**
    - id: ID de la canción
    
    **Parámetros de consulta:**
    - includeUnpublished: Si es true, permite ver canciones no publicadas del usuario (por defecto: false)
    
    **Comportamiento:**
    - Por defecto: solo canciones en colecciones publicadas o standalone
    - Con includeUnpublished=true y siendo el dueño: permite ver canciones en colecciones no publicadas
    - Incluye el estado de "like" (isLiked) para el usuario autenticado
    
    **Retorna:**
    - 200: Detalles completos de la canción con estado de like
    - 404: Canción no encontrada o no publicada aún
    """
    logger.info(f"Fetching song with id={id} (includeUnpublished={includeUnpublished})")
    try:
        song = await songs_db.get_song(id, includeUnpublished, user["user_id"])
        if song is None:
            logger.warning(f"Song with id={id} not found or not published")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found", f"Song with id {id} not found or not published", f"/songs/{id}"
                ),
            )
        
        # Check if the song is liked by the authenticated user
        is_liked = await metrics_db.is_liked_by_user(user["user_id"], id, "song")
        
        return {"data": serialize_song(song, is_liked)}
    except Exception as e:
        logger.error(f"Failed to fetch song with id={id}: {str(e)}")
        raise


@router.put(
    "/{id}",
    status_code=200,
    responses={
        200: {
            "description": "Song updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "title": "Bohemian Rhapsody (Remastered)",
                            "artist": "Queen",
                            "duration": "354",
                            "artistId": "artist_123",
                            "isLiked": False
                        }
                    }
                }
            }
        }
    }
)
async def update_song(id: str, song: schemas.UpdateSongRequest, user: dict = Depends(verify_token)):
    """
    Actualizar la información de una canción existente.
    
    Este endpoint permite modificar los metadatos de una canción (título, artista, duración).
    La actualización se realiza dentro de una transacción de base de datos para garantizar
    la consistencia de los datos. Solo el artista dueño o usuarios backoffice pueden actualizar canciones.
    
    **Parámetros de ruta:**
    - id: ID de la canción a actualizar
    
    **Cuerpo de la solicitud:**
    - title: Nuevo título de la canción (opcional)
    - artist: Nuevo nombre de artista (opcional)
    - duration: Nueva duración en segundos (opcional)
    
    **Autorización:**
    - Solo el artista dueño de la canción o usuarios backoffice pueden actualizarla
    - Se pueden actualizar canciones no publicadas
    
    **Validaciones:**
    - La canción debe existir
    - El usuario debe ser el dueño o backoffice
    
    **Retorna:**
    - 200: Canción actualizada exitosamente
    - 400: Error en los datos proporcionados
    - 403: No autorizado para actualizar esta canción
    - 404: Canción no encontrada
    """
    logger.info(
        f"Updating song with id={id}: title='{song.title}', artist='{song.artist}, duration='{song.duration}'"
    )

    # Backoffice can update any song, owner can only update their own
    if user.get("user_type") == "backoffice":
        # Backoffice: get song without user restriction
        db_song = await songs_db.get_song(id, includeUnpublished=True, userId=None)
    else:
        # Regular user: only get their own songs
        db_song = await songs_db.get_song(id, includeUnpublished=True, userId=user["user_id"])
    
    if db_song is None:
        logger.warning(f"Song with id={id} not found for update")
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found", f"Song with id {id} not found", f"/songs/{id}"
            ),
        )
    
    # Verify authorization (owner or backoffice)
    if not is_authorized(user, db_song.get("artistId")):
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403, "Forbidden", "You are not authorized to update this song", f"/songs/{id}"
            ),
        )

    updated_song, e = await songs_db.update_song(db_song, song.title, song.artist, song.duration)

    if not updated_song:
        logger.error(f"Failed to update song with id={id}: {str(e)}")
        logger.debug("Database transaction rolled back")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/songs/{id}"),
        )
    return {"data": serialize_song(updated_song)}


@router.delete("/{id}", status_code=204)
async def delete_song(id: str, user: dict = Depends(verify_token)):
    """
    Eliminar una canción de la base de datos permanentemente.
    
    Este endpoint borra completamente una canción del sistema. La eliminación es permanente
    e irreversible. La operación también remueve la canción de todas las playlists y colecciones
    donde esté incluida debido a las restricciones de clave foránea en la base de datos.
    
    **Parámetros de ruta:**
    - id: ID de la canción a eliminar
    
    **Autorización:**
    - Solo el artista dueño de la canción o usuarios backoffice pueden eliminarla
    - Se pueden eliminar canciones no publicadas
    
    **Validaciones:**
    - La canción debe existir
    - El usuario debe ser el dueño o backoffice
    
    **Efectos de la eliminación:**
    - La canción se elimina permanentemente
    - Se remueve de todas las playlists donde estaba incluida
    - Se remueve de todas las colecciones donde estaba incluida
    - Las métricas asociadas se mantienen para histórico
    
    **Retorna:**
    - 204: Canción eliminada exitosamente (sin contenido)
    - 403: No autorizado para eliminar esta canción
    - 404: Canción no encontrada
    """
    logger.info(f"Deleting song with id={id}")
    
    # Backoffice can delete any song, owner can only delete their own
    if user.get("user_type") == "backoffice":
        # Backoffice: get song without user restriction
        db_song = await songs_db.get_song(id, includeUnpublished=True, userId=None)
    else:
        # Regular user: only get their own songs
        db_song = await songs_db.get_song(id, includeUnpublished=True, userId=user["user_id"])
    
    if db_song is None:
        logger.warning(f"Song with id={id} not found for deletion")
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found", f"Song with id {id} not found", f"/songs/{id}"
            ),
        )
    
    # Verify authorization (owner or backoffice)
    if not is_authorized(user, db_song.get("artistId")):
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403, "Forbidden", "You are not authorized to delete this song", f"/songs/{id}"
            ),
        )

    return await songs_db.delete_song(db_song)

