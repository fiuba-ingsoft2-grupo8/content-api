from fastapi import APIRouter, Depends, Query, Header
from fastapi.responses import JSONResponse
from typing import Optional

import databases.activity_database as activity_db
import schemas
from auth import verify_token
from common.utils import create_error_response
from resources.logger import logger

router = APIRouter()


@router.get(
    "/{user_id}",
    responses={
        200: {
            "description": "User activity feed",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "type": "like",
                                "userId": "user_123",
                                "targetId": "507f1f77bcf86cd799439011",
                                "targetType": "song",
                                "timestamp": "2025-11-10T14:30:00Z",
                                "createdAt": "2025-11-10T14:30:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439011",
                                    "title": "Bohemian Rhapsody",
                                    "artist": "Queen",
                                    "coverUrl": "https://example.com/cover.jpg"
                                }
                            },
                            {
                                "type": "play",
                                "userId": "user_123",
                                "songId": "507f1f77bcf86cd799439012",
                                "targetType": "song",
                                "timestamp": "2025-11-10T13:15:00Z",
                                "playedAt": "2025-11-10T13:15:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439012",
                                    "title": "Imagine",
                                    "artist": "John Lennon",
                                    "coverUrl": "https://example.com/imagine.jpg"
                                }
                            },
                            {
                                "type": "playlist_published",
                                "userId": "user_123",
                                "playlistId": "507f1f77bcf86cd799439013",
                                "playlistName": "My Favorites",
                                "timestamp": "2025-11-09T10:00:00Z",
                                "publishedAt": "2025-11-09T10:00:00Z"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_user_activity(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of activities to return"),
    activity_type: Optional[str] = Query(default=None, description="Filter by activity type: 'like', 'play', 'playlist_published', 'share'"),
    user: dict = Depends(verify_token)
):
    """
    Obtener la actividad reciente de un usuario específico.
    
    Este endpoint retorna una lista cronológicamente ordenada de las actividades de un usuario,
    incluyendo información detallada sobre las canciones, colecciones y playlists involucradas.
    Es útil para mostrar el perfil de actividad de un usuario o su historial de interacciones.
    
    **Tipos de actividades incluidas:**
    - **Likes**: Canciones o colecciones que el usuario ha marcado como favoritas
    - **Plays**: Canciones que el usuario ha reproducido
    - **Published Playlists**: Playlists que el usuario ha hecho públicas
    - **Shares**: Contenido que el usuario ha compartido
    
    **Parámetros de consulta:**
    - `limit`: Número máximo de actividades a retornar (1-100, por defecto: 50)
    - `activity_type`: Filtro opcional por tipo. Valores válidos: 'like', 'play', 'playlist_published', 'share'
    
    **Nota sobre privacidad de shares:**
    - Si consultas tu propia actividad, verás todos tus shares
    - Si consultas la actividad de otro usuario, solo verás los shares que ese usuario te hizo a ti
    
    **Nota:** Las actividades se ordenan de más reciente a más antigua.
    
    **Retorna:**
    - 200: Lista de actividades del usuario con detalles enriquecidos
    - 400: Error en los parámetros de la solicitud
    """
    try:
        requesting_user_id = user["user_id"]
        logger.info(f"User {requesting_user_id} fetching activity for user {user_id} (limit={limit}, type={activity_type})")
        
        # Get activities with privacy filtering for shares
        activities = await activity_db.get_user_activity(user_id, limit, activity_type, requesting_user_id)
        
        # Enrich with full details
        enriched_activities = await activity_db.enrich_activity_with_details(activities)
        
        logger.info(f"Successfully retrieved {len(enriched_activities)} activities for user {user_id}")
        return {"data": enriched_activities}
        
    except Exception as e:
        logger.error(f"Failed to fetch activity for user {user_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), f"/activity/{user_id}"
            ),
        )


@router.get(
    "/",
    responses={
        200: {
            "description": "Following activity feed",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "type": "like",
                                "userId": "user_456",
                                "targetId": "507f1f77bcf86cd799439011",
                                "targetType": "song",
                                "timestamp": "2025-11-10T16:45:00Z",
                                "createdAt": "2025-11-10T16:45:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439011",
                                    "title": "Stairway to Heaven",
                                    "artist": "Led Zeppelin",
                                    "coverUrl": "https://example.com/stairway.jpg"
                                }
                            },
                            {
                                "type": "play",
                                "userId": "user_789",
                                "songId": "507f1f77bcf86cd799439014",
                                "targetType": "song",
                                "timestamp": "2025-11-10T15:20:00Z",
                                "playedAt": "2025-11-10T15:20:00Z",
                                "song": {
                                    "_id": "507f1f77bcf86cd799439014",
                                    "title": "Hotel California",
                                    "artist": "Eagles",
                                    "coverUrl": "https://example.com/hotel.jpg"
                                }
                            },
                            {
                                "type": "playlist_published",
                                "userId": "user_456",
                                "playlistId": "507f1f77bcf86cd799439015",
                                "playlistName": "Summer Hits 2025",
                                "timestamp": "2025-11-10T12:00:00Z",
                                "publishedAt": "2025-11-10T12:00:00Z"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_following_activity(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of activities to return"),
    activity_type: Optional[str] = Query(default=None, description="Filter by activity type: 'like', 'play', 'playlist_published', 'share'"),
    authorization: Optional[str] = Header(None),
    user: dict = Depends(verify_token)
):
    """
    Obtener la actividad reciente de los usuarios que sigue el usuario autenticado.
    
    Este endpoint retorna un feed cronológicamente ordenado de las actividades de los usuarios
    que el usuario autenticado sigue. Es ideal para crear un feed de noticias o timeline social
    donde se pueda ver qué están escuchando, compartiendo o publicando los amigos.
    
    **Tipos de actividades incluidas:**
    - **Likes**: Canciones o colecciones que han marcado como favoritas
    - **Plays**: Canciones que han reproducido
    - **Published Playlists**: Playlists que han hecho públicas
    - **Shares**: Contenido que han compartido
    
    **Parámetros de consulta:**
    - `limit`: Número máximo de actividades a retornar (1-100, por defecto: 50)
    - `activity_type`: Filtro opcional por tipo. Valores válidos: 'like', 'play', 'playlist_published', 'share'
    
    **Notas importantes:**
    - Las actividades se ordenan de más reciente a más antigua entre todos los usuarios seguidos
    - Requiere autenticación del usuario
    - Retorna una lista vacía si el usuario no sigue a nadie
    - Las actividades incluyen detalles enriquecidos sobre el contenido compartido
    
    **Retorna:**
    - 200: Feed de actividades de usuarios seguidos
    - 400: Error en los parámetros de la solicitud
    """
    try:
        user_id = user["user_id"]
        logger.info(f"Fetching following activity feed for user {user_id} (limit={limit}, type={activity_type})")
        
        # Get activities from followed users (pass authorization header directly)
        activities = await activity_db.get_following_activity(user_id, authorization, limit, activity_type)
        
        # Enrich with full details
        enriched_activities = await activity_db.enrich_activity_with_details(activities)
        
        logger.info(f"Successfully retrieved {len(enriched_activities)} activities for user {user_id}'s feed")
        return {"data": enriched_activities}
        
    except Exception as e:
        logger.error(f"Failed to fetch following activity feed for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), "/activity"
            ),
        )

