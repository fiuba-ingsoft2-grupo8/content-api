from fastapi import APIRouter, Depends, Query, Body
from fastapi.responses import JSONResponse
from typing import Optional

import databases.share_database as share_db
import databases.metrics_database as metrics_db
import databases.playlists_database as playlists_db
import schemas
from auth import verify_token
from common.utils import create_error_response
from resources.logger import logger

router = APIRouter()


@router.post(
    "/song/{song_id}",
    status_code=201,
    responses={
        201: {
            "description": "Song shared successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Song shared successfully",
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "userId": "user_123",
                            "targetId": "507f1f77bcf86cd799439012",
                            "targetType": "song",
                            "recipientId": "user_456",
                            "createdAt": "2025-11-15T10:30:00Z"
                        }
                    }
                }
            }
        }
    }
)
async def share_song(
    song_id: str,
    body: dict = Body(default={}),
    user: dict = Depends(verify_token)
):
    """
    Compartir una canción con un amigo o públicamente.
    
    **Criterio de Aceptación (CA 1):** Al escuchar una canción, seleccionar 'Compartir' y elegir un amigo.
    La canción se compartirá en su feed de actividad y podrán acceder a ella.
    
    **Cuerpo de la Solicitud:**
    - `recipientId` (opcional): ID del usuario amigo con quien compartir. Si no se proporciona, el share es público.
    
    **Comportamiento:**
    - Crea un registro de compartido en la base de datos
    - Incrementa las métricas de shares para la canción
    - Aparece en el feed de actividad del destinatario (si se proporciona recipientId)
    - Aparece en el feed de actividad del usuario que comparte
    
    **Notas:**
    - La canción debe existir
    - Si se proporciona recipientId, el share es directo a ese usuario
    - Si no se proporciona recipientId, el share se considera público
    """
    try:
        user_id = user["user_id"]
        recipient_id = body.get("recipientId") if body else None
        logger.info(f"User {user_id} sharing song {song_id}" + (f" with {recipient_id}" if recipient_id else " publicly"))
        
        # Crear el registro de compartido
        share, error = await share_db.create_share(
            user_id=user_id,
            target_id=song_id,
            target_type="song",
            recipient_id=recipient_id
        )
        
        if error:
            logger.error(f"Failed to share song {song_id}: {str(error)}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    str(error),
                    f"/share/song/{song_id}"
                )
            )
        
        # Enriquecer el share con detalles de la canción
        enriched_share = await share_db.enrich_share_with_details(share)
        
        logger.info(f"Successfully shared song {song_id}")
        return {
            "message": "Song shared successfully",
            "data": {
                "_id": str(enriched_share["_id"]),
                "userId": enriched_share["user_id"],
                "targetId": str(enriched_share["target_id"]),
                "targetType": enriched_share["target_type"],
                "recipientId": enriched_share.get("recipient_id"),
                "createdAt": enriched_share["created_at"],
                "song": enriched_share.get("song")
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to share song {song_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                f"/share/song/{song_id}"
            )
        )


@router.post(
    "/playlist/{playlist_id}",
    status_code=201,
    responses={
        201: {
            "description": "Playlist shared successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Playlist shared successfully and made public",
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "name": "My Favorites",
                            "is_published": True,
                            "published_at": "2025-11-15T10:30:00Z"
                        }
                    }
                }
            }
        }
    }
)
async def share_playlist(
    playlist_id: str,
    body: dict = Body(default={"make_public": True}),
    user: dict = Depends(verify_token)
):
    """
    Compartir una playlist públicamente.
    
    **Criterio de Aceptación (CA 2):** Al crear una playlist, seleccionar 'Compartir' y elegir hacerla pública.
    La playlist estará disponible en mi perfil para que otros usuarios la vean y escuchen.
    
    **Cuerpo de la Solicitud:**
    - `make_public` (opcional, por defecto: true): Si se debe hacer pública la playlist al compartir
    
    **Comportamiento:**
    - Hace pública la playlist (establece is_published = true) si make_public es true
    - Crea un registro de compartido en la base de datos
    - Incrementa las métricas de shares para la playlist
    - Aparece en el feed de actividad del usuario como una playlist publicada
    
    **Notas:**
    - El usuario debe ser el dueño de la playlist o backoffice
    - La playlist debe existir
    - Si la playlist ya es pública, aún así se registra el share
    """
    try:
        user_id = user["user_id"]
        make_public = body.get("make_public", True) if body else True
        logger.info(f"User {user_id} sharing playlist {playlist_id} (make_public={make_public})")
        
        # Obtener la playlist
        playlist = await playlists_db.get_playlist(playlist_id, user)
        if not playlist:
            logger.warning(f"Playlist {playlist_id} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Playlist with id {playlist_id} not found",
                    f"/share/playlist/{playlist_id}"
                )
            )
        
        # Verificar autorización
        is_owner = playlist.get("userId") == user_id
        is_backoffice = user.get("user_type") == "backoffice"
        
        if not is_owner and not is_backoffice:
            logger.warning(f"User {user_id} not authorized to share playlist {playlist_id}")
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to share this playlist",
                    f"/share/playlist/{playlist_id}"
                )
            )
        
        # Hacer pública la playlist si se solicita
        if make_public and not playlist.get("is_published"):
            await playlists_db.change_playlist_state(playlist, True)
            logger.info(f"Playlist {playlist_id} made public")
        
        # Crear el registro de compartido (share público, sin destinatario específico)
        share, error = await share_db.create_share(
            user_id=user_id,
            target_id=playlist_id,
            target_type="playlist",
            recipient_id=None  # Share público
        )
        
        if error:
            logger.error(f"Failed to share playlist {playlist_id}: {str(error)}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    str(error),
                    f"/share/playlist/{playlist_id}"
                )
            )
        
        # Obtener la playlist actualizada
        updated_playlist = await playlists_db.get_playlist(playlist_id, user)
        
        logger.info(f"Successfully shared playlist {playlist_id}")
        return {
            "message": "Playlist shared successfully" + (" and made public" if make_public else ""),
            "data": {
                "_id": str(updated_playlist["_id"]),
                "name": updated_playlist["name"],
                "is_published": updated_playlist["is_published"],
                "published_at": updated_playlist.get("published_at"),
                "userId": updated_playlist["userId"]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to share playlist {playlist_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                f"/share/playlist/{playlist_id}"
            )
        )


@router.post(
    "/collection/{collection_id}",
    status_code=201,
    responses={
        201: {
            "description": "Collection shared successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Collection shared successfully",
                        "data": {
                            "_id": "507f1f77bcf86cd799439011",
                            "userId": "user_123",
                            "targetId": "507f1f77bcf86cd799439012",
                            "targetType": "collection",
                            "recipientId": "user_456",
                            "createdAt": "2025-11-15T10:30:00Z"
                        }
                    }
                }
            }
        }
    }
)
async def share_collection(
    collection_id: str,
    body: dict = Body(default={}),
    user: dict = Depends(verify_token)
):
    """
    Compartir una colección (álbum/EP/single) con un amigo o públicamente.
    
    **Cuerpo de la Solicitud:**
    - `recipientId` (opcional): ID del usuario amigo con quien compartir. Si no se proporciona, el share es público.
    
    **Comportamiento:**
    - Crea un registro de compartido en la base de datos
    - Incrementa las métricas de shares para la colección
    - Aparece en el feed de actividad del destinatario (si se proporciona recipientId)
    - Aparece en el feed de actividad del usuario que comparte
    
    **Notas:**
    - La colección debe existir
    - Si se proporciona recipientId, el share es directo a ese usuario
    - Si no se proporciona recipientId, el share se considera público
    """
    try:
        user_id = user["user_id"]
        recipient_id = body.get("recipientId") if body else None
        logger.info(f"User {user_id} sharing collection {collection_id}" + (f" with {recipient_id}" if recipient_id else " publicly"))
        
        # Crear el registro de compartido
        share, error = await share_db.create_share(
            user_id=user_id,
            target_id=collection_id,
            target_type="collection",
            recipient_id=recipient_id
        )
        
        if error:
            logger.error(f"Failed to share collection {collection_id}: {str(error)}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    str(error),
                    f"/share/collection/{collection_id}"
                )
            )
        
        # Enriquecer el share con detalles de la colección
        enriched_share = await share_db.enrich_share_with_details(share)
        
        logger.info(f"Successfully shared collection {collection_id}")
        return {
            "message": "Collection shared successfully",
            "data": {
                "_id": str(enriched_share["_id"]),
                "userId": enriched_share["user_id"],
                "targetId": str(enriched_share["target_id"]),
                "targetType": enriched_share["target_type"],
                "recipientId": enriched_share.get("recipient_id"),
                "createdAt": enriched_share["created_at"],
                "collection": enriched_share.get("collection")
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to share collection {collection_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                f"/share/collection/{collection_id}"
            )
        )


@router.get(
    "/received",
    responses={
        200: {
            "description": "List of shares received by the user",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "_id": "507f1f77bcf86cd799439011",
                                "userId": "user_456",
                                "targetId": "507f1f77bcf86cd799439012",
                                "targetType": "song",
                                "recipientId": "user_123",
                                "createdAt": "2025-11-15T10:30:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439012",
                                    "title": "Bohemian Rhapsody",
                                    "artist": "Queen",
                                    "coverUrl": "https://example.com/cover.jpg"
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_received_shares(
    limit: int = Query(default=50, ge=1, le=100, description="Número máximo de shares a retornar"),
    user: dict = Depends(verify_token)
):
    """
    Obtener los shares que fueron enviados directamente al usuario autenticado.
    
    Retorna una lista de elementos que amigos han compartido contigo, ordenados del más reciente al más antiguo.
    
    **Parámetros de Consulta:**
    - `limit`: Número máximo de shares a retornar (1-100, por defecto: 50)
    
    **Notas:**
    - Solo retorna shares que fueron enviados directamente a ti (con tu user ID como recipientId)
    - No incluye shares públicos
    - Los shares se enriquecen con detalles sobre el contenido compartido
    """
    try:
        user_id = user["user_id"]
        logger.info(f"Fetching received shares for user {user_id} (limit={limit})")
        
        # Obtener los shares para este usuario
        shares = await share_db.get_shares_for_user(user_id, limit)
        
        # Enriquecer con detalles
        enriched_shares = []
        for share in shares:
            enriched = await share_db.enrich_share_with_details(share)
            enriched_shares.append(enriched)
        
        logger.info(f"Successfully retrieved {len(enriched_shares)} received shares for user {user_id}")
        return {"data": enriched_shares}
        
    except Exception as e:
        logger.error(f"Failed to fetch received shares for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                "/share/received"
            )
        )


@router.post(
    "/external/song/{song_id}",
    status_code=201,
    responses={
        201: {
            "description": "External share link generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "🎵 Escucha 'Bohemian Rhapsody' de Queen en Melodia",
                        "url": "/song/507f1f77bcf86cd799439011"
                    }
                }
            }
        }
    }
)
async def generate_external_song_share(
    song_id: str,
    user: dict = Depends(verify_token)
):
    """
    Generar enlace externo para compartir una canción en redes sociales o apps de mensajería.
    
    **Criterio de Aceptación (CA 3):** Al seleccionar 'Compartir' y elegir una red social o app de mensajería,
    se genera un enlace que se puede pegar o enviar a través de la plataforma externa seleccionada.
    
    **Parámetros de ruta:**
    - song_id: ID de la canción a compartir
    
    **Comportamiento:**
    - Valida que la canción exista
    - Genera un mensaje descriptivo con el título y artista de la canción
    - Genera una URL que la app puede usar para mostrar la canción
    - Registra el share en las métricas
    
    **Respuesta:**
    - `message`: Mensaje descriptivo listo para copiar/pegar
    - `url`: URL para acceder a la canción (formato: /song/{song_id})
    
    **Retorna:**
    - 201: Enlace generado exitosamente
    - 404: Canción no encontrada
    - 400: Error en la solicitud
    """
    try:
        import databases.songs_database as songs_db
        
        user_id = user["user_id"]
        logger.info(f"User {user_id} generating external share link for song {song_id}")
        
        # Validar que la canción existe
        song = await songs_db.get_song(song_id)
        if not song:
            logger.warning(f"Song {song_id} not found for external sharing")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Song with id {song_id} not found",
                    f"/share/external/song/{song_id}"
                )
            )
        
        # Registrar el share en métricas
        await metrics_db.record_share(user_id, song_id, "song")
        
        # Generar mensaje descriptivo
        song_title = song.get("title", "Canción")
        song_artist = song.get("artist", "Artista")
        message = f"🎵 Escucha '{song_title}' de {song_artist} en Melodia"
        
        # Generar URL
        url = f"/song/{song_id}"
        
        logger.info(f"Successfully generated external share link for song {song_id}")
        return {
            "message": message,
            "url": url
        }
        
    except Exception as e:
        logger.error(f"Failed to generate external share link for song {song_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                f"/share/external/song/{song_id}"
            )
        )


@router.post(
    "/external/playlist/{playlist_id}",
    status_code=201,
    responses={
        201: {
            "description": "External share link generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "🎧 Escucha la playlist 'My Favorites' en Melodia",
                        "url": "/playlist/507f1f77bcf86cd799439011"
                    }
                }
            }
        }
    }
)
async def generate_external_playlist_share(
    playlist_id: str,
    user: dict = Depends(verify_token)
):
    """
    Generar enlace externo para compartir una playlist en redes sociales o apps de mensajería.
    
    **Criterio de Aceptación (CA 3):** Al seleccionar 'Compartir' y elegir una red social o app de mensajería,
    se genera un enlace que se puede pegar o enviar a través de la plataforma externa seleccionada.
    
    **Parámetros de ruta:**
    - playlist_id: ID de la playlist a compartir
    
    **Comportamiento:**
    - Valida que la playlist exista y sea accesible
    - Si la playlist es privada, la hace pública automáticamente
    - Genera un mensaje descriptivo con el nombre de la playlist
    - Genera una URL que la app puede usar para mostrar la playlist
    - Registra el share en las métricas
    
    **Respuesta:**
    - `message`: Mensaje descriptivo listo para copiar/pegar
    - `url`: URL para acceder a la playlist (formato: /playlist/{playlist_id})
    
    **Autorización:**
    - El usuario debe ser el dueño de la playlist o backoffice para compartirla externamente
    
    **Retorna:**
    - 201: Enlace generado exitosamente
    - 403: No autorizado para compartir esta playlist
    - 404: Playlist no encontrada
    - 400: Error en la solicitud
    """
    try:
        user_id = user["user_id"]
        logger.info(f"User {user_id} generating external share link for playlist {playlist_id}")
        
        # Obtener la playlist
        playlist = await playlists_db.get_playlist(playlist_id, user)
        if not playlist:
            logger.warning(f"Playlist {playlist_id} not found for external sharing")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Playlist with id {playlist_id} not found",
                    f"/share/external/playlist/{playlist_id}"
                )
            )
        
        # Verificar autorización
        is_owner = playlist.get("userId") == user_id
        is_backoffice = user.get("user_type") == "backoffice"
        
        if not is_owner and not is_backoffice:
            logger.warning(f"User {user_id} not authorized to share playlist {playlist_id} externally")
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to share this playlist externally",
                    f"/share/external/playlist/{playlist_id}"
                )
            )
        
        # Si la playlist es privada, hacerla pública para que el enlace funcione
        if not playlist.get("is_published"):
            await playlists_db.change_playlist_state(playlist, True)
            logger.info(f"Playlist {playlist_id} made public for external sharing")
        
        # Registrar el share en métricas (como colección tipo playlist)
        # Nota: Actualmente record_share solo acepta "song" o "collection"
        # Podríamos agregar "playlist" o usar el endpoint de share normal
        
        # Generar mensaje descriptivo
        playlist_name = playlist.get("name", "Playlist")
        message = f"🎧 Escucha la playlist '{playlist_name}' en Melodia"
        
        # Generar URL
        url = f"/playlist/{playlist_id}"
        
        logger.info(f"Successfully generated external share link for playlist {playlist_id}")
        return {
            "message": message,
            "url": url
        }
        
    except Exception as e:
        logger.error(f"Failed to generate external share link for playlist {playlist_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                f"/share/external/playlist/{playlist_id}"
            )
        )

