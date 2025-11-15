import databases.metrics_database as metrics_db
import databases.songs_database as songs_db
import databases.collections_database as collections_db
import schemas
from fastapi import Depends
from auth import verify_token
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from resources.logger import logger
from common.utils import create_error_response

router = APIRouter()

@router.get(
    "/likes/{target_type}/{target_id}",
    status_code=200,
    responses={
        200: {
            "description": "Like status",
            "content": {
                "application/json": {
                    "example": {
                        "liked": True
                    }
                }
            }
        }
    }
)
async def check_like_status(target_type: str, target_id: str, user: dict = Depends(verify_token)):
    """
    Verificar si el usuario actual ha marcado como favorita una canción específica.
    
    Este endpoint permite consultar el estado de "like" de una canción para el usuario autenticado.
    Es útil para mostrar correctamente el estado del botón de "me gusta" en la interfaz de usuario.
    
    **Parámetros de ruta:**
    - target_type: Tipo de contenido (solo "song" es válido)
    - target_id: ID de la canción a consultar
    
    **Nota importante:** Solo funciona para canciones (target_type: "song").
    Las colecciones no tienen "likes" directos, su conteo de likes es la suma de los likes de sus canciones.
    
    **Retorna:**
    - 200: Estado del like con campo `liked` (true/false)
    - 400: Tipo de contenido no válido (no es "song")
    """
    logger.info(f"Checking like status for {target_type} {target_id} by user {user['user_id']}")
    
    if target_type != "song":
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request",
                "Only songs can be liked. Collections don't have direct likes - their like count is the sum of their songs' likes.",
                f"/metrics/likes/{target_type}/{target_id}"
            ),
        )
    
    is_liked = await metrics_db.is_liked_by_user(user["user_id"], target_id, target_type)
    
    return {
        "liked": is_liked
    }

@router.post("/shares", status_code=201)
async def record_share(request: schemas.ShareRequest, user: dict = Depends(verify_token)):
    """
    Registrar un evento de compartir contenido (canción o colección).
    
    Este endpoint registra cuando un usuario comparte una canción o colección, incrementando
    el contador de shares en las métricas. Es usado por otros endpoints de sharing pero también
    puede ser llamado directamente para registrar shares a través de otros medios (redes sociales, etc).
    
    **Cuerpo de la solicitud:**
    - targetType: Tipo de contenido compartido ("song" o "collection")
    - targetId: ID del contenido compartido
    
    **Validaciones:**
    - El contenido (canción o colección) debe existir
    - El targetType debe ser "song" o "collection"
    
    **Retorna:**
    - 201: Share registrado exitosamente
    - 400: targetType inválido
    - 404: Contenido no encontrado
    - 500: Error al registrar el share
    """
    logger.info(f"User {user['user_id']} sharing {request.targetType} {request.targetId}")
    
    # Validate target exists
    if request.targetType == "song":
        target = await songs_db.get_song(request.targetId)
        if not target:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Song with id {request.targetId} not found",
                    "/metrics/shares"
                ),
            )
    elif request.targetType == "collection":
        target = await collections_db.get_collection(request.targetId)
        if not target:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404, "Not Found",
                    f"Collection with id {request.targetId} not found",
                    "/metrics/shares"
                ),
            )
    else:
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request",
                "targetType must be 'song' or 'collection'",
                "/metrics/shares"
            ),
        )
    
    error = await metrics_db.record_share(user["user_id"], request.targetId, request.targetType)
    if error:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                str(error),
                "/metrics/shares"
            ),
        )
    
    return {"message": "Share recorded successfully"}

@router.get(
    "/songs/{song_id}",
    status_code=200,
    responses={
        200: {
            "description": "Song metrics",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "totalPlays": 1523,
                            "totalLikes": 245,
                            "totalShares": 67,
                            "totalPlaylistSaves": 89,
                            "popularityScore": 8.5
                        }
                    }
                }
            }
        }
    }
)
async def get_song_metrics(song_id: str, user: dict = Depends(verify_token)):
    """
    Obtener las métricas completas de una canción específica.
    
    Este endpoint retorna todas las estadísticas de engagement de una canción, incluyendo
    reproducciones, likes y shares. Es útil para mostrar estadísticas públicas de popularidad
    o para que los artistas vean el rendimiento de sus canciones.
    
    **Parámetros de ruta:**
    - song_id: ID de la canción
    
    **Métricas retornadas:**
    - totalPlays: Total de reproducciones registradas
    - totalLikes: Total de usuarios que marcaron como favorita
    - totalShares: Total de veces que fue compartida
    - totalPlaylistSaves: Total de veces agregada a playlists (si disponible)
    - popularityScore: Puntaje de popularidad calculado (si disponible)
    
    **Validaciones:**
    - La canción debe existir
    
    **Retorna:**
    - 200: Métricas completas de la canción
    - 404: Canción no encontrada
    - 500: Error al obtener las métricas
    """
    logger.info(f"Fetching metrics for song {song_id}")
    
    # Validate song exists
    song = await songs_db.get_song(song_id)
    if not song:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Song with id {song_id} not found",
                f"/metrics/songs/{song_id}"
            ),
        )
    
    metrics = await metrics_db.get_song_metrics(song_id)
    if not metrics:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                "Failed to fetch song metrics",
                f"/metrics/songs/{song_id}"
            ),
        )
    
    return {"data": metrics}

@router.get("/collections/{collection_id}", status_code=200)
async def get_collection_metrics(collection_id: str, user: dict = Depends(verify_token)):
    """
    Obtener las métricas completas de una colección específica.
    
    Este endpoint retorna las estadísticas agregadas de una colección (álbum, EP o single),
    calculando métricas tanto a nivel de colección como agregando las métricas de todas
    sus canciones individuales.
    
    **Parámetros de ruta:**
    - collection_id: ID de la colección
    
    **Métricas retornadas:**
    - totalPlays: Suma de reproducciones de todas las canciones de la colección
    - likes: Suma de likes de todas las canciones de la colección
    - shares: Número de veces que la colección en sí fue compartida
    
    **Nota:** A diferencia de las canciones, las colecciones no tienen "likes" directos.
    El conteo de likes es la suma de los likes de todas sus canciones.
    
    **Validaciones:**
    - La colección debe existir
    
    **Retorna:**
    - 200: Métricas completas de la colección
    - 404: Colección no encontrada
    - 500: Error al obtener las métricas
    """
    logger.info(f"Fetching metrics for collection {collection_id}")
    
    # Validate collection exists
    collection = await collections_db.get_collection(collection_id)
    if not collection:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Collection with id {collection_id} not found",
                f"/metrics/collections/{collection_id}"
            ),
        )
    
    metrics = await metrics_db.get_collection_metrics(collection_id)
    if not metrics:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                "Failed to fetch collection metrics",
                f"/metrics/collections/{collection_id}"
            ),
        )
    
    return {"data": metrics}

@router.get("/artists/{artist_id}", status_code=200)
async def get_artist_metrics(artist_id: str, user: dict = Depends(verify_token)):
    """
    Obtener las métricas generales de un artista específico.
    
    Este endpoint retorna un resumen completo de las estadísticas de un artista, incluyendo
    métricas del período actual y comparaciones con el período anterior para análisis de tendencias.
    
    **Parámetros de ruta:**
    - artist_id: ID del artista
    
    **Métricas retornadas:**
    - monthlyListeners: Oyentes únicos del mes actual
    - totalPlays: Total de reproducciones del mes actual
    - totalSaves: Total de saves/likes del mes actual
    - totalShares: Total de shares del mes actual
    - Comparaciones con el mes anterior (cambios porcentuales)
    
    **Período de cálculo:**
    - Mes actual vs mes anterior
    - Permite ver el crecimiento o decrecimiento de la audiencia
    
    **Retorna:**
    - 200: Métricas completas del artista con comparaciones
    - 500: Error al obtener las métricas
    """
    logger.info(f"Fetching metrics for artist {artist_id}")
    
    # Optionally validate that the user is requesting their own metrics
    # or has permission to view this artist's metrics
    
    metrics = await metrics_db.get_artist_metrics(artist_id)
    if not metrics:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                "Failed to fetch artist metrics",
                f"/metrics/artists/{artist_id}"
            ),
        )
    
    return {"data": metrics}

@router.get("/artists/me/overview", status_code=200)
async def get_my_artist_metrics(user: dict = Depends(verify_token)):
    """
    Obtener las métricas generales del artista autenticado.
    
    Este endpoint retorna las estadísticas propias del artista que hace la solicitud,
    proporcionando un dashboard de métricas personales con comparaciones temporales.
    Es el endpoint principal para que los artistas vean su propio rendimiento.
    
    **Métricas retornadas:**
    - monthlyListeners: Oyentes únicos del mes actual
    - totalPlays: Total de reproducciones del mes actual
    - totalSaves: Total de saves/likes del mes actual  
    - totalShares: Total de shares del mes actual
    - Comparaciones con el mes anterior (cambios porcentuales y absolutos)
    
    **Validaciones:**
    - El usuario debe ser un artista (tener stage_name)
    
    **Período de cálculo:**
    - Mes actual vs mes anterior
    - Útil para dashboards de artista y análisis de rendimiento personal
    
    **Retorna:**
    - 200: Métricas completas del artista con comparaciones
    - 403: Usuario no es un artista
    - 500: Error al obtener las métricas
    """
    artist_id = user["user_id"]
    logger.info(f"Fetching metrics for authenticated artist {artist_id}")
    
    # Check if user is an artist
    if not user.get("stage_name"):
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403, "Forbidden",
                "User is not an artist",
                "/metrics/artists/me/overview"
            ),
        )
    
    metrics = await metrics_db.get_artist_metrics(artist_id)
    if not metrics:
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                "Failed to fetch artist metrics",
                "/metrics/artists/me/overview"
            ),
        )
    
    return {"data": metrics}

