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
async def get_artist_metrics(
    artist_id: str, 
    user: dict = Depends(verify_token),
    period: str = "monthly",
    start_date: str = None,
    end_date: str = None,
    country: str = None
):
    """
    Obtener las métricas generales de un artista específico con filtros opcionales.
    
    Este endpoint retorna un resumen completo de las estadísticas de un artista, incluyendo
    métricas del período actual y comparaciones con el período anterior para análisis de tendencias.
    
    **Parámetros de ruta:**
    - artist_id: ID del artista
    
    **Parámetros de consulta opcionales:**
    - period: Tipo de período ('daily', 'weekly', 'monthly', 'custom'). Default: 'monthly'
    - start_date: Fecha de inicio para período custom (ISO 8601 format). Requerido si period='custom'
    - end_date: Fecha de fin para período custom (ISO 8601 format). Requerido si period='custom'
    - country: Código ISO del país para filtrar (ej: 'US', 'AR', 'BR')
    
    **Métricas retornadas:**
    - monthlyListeners: Oyentes únicos del período
    - plays: Total de reproducciones del período
    - saves: Total de saves/likes del período
    - shares: Total de shares del período
    - Cada métrica incluye: value (valor actual), delta (cambio vs período anterior), percentChange (% de cambio)
    
    **Retorna:**
    - 200: Métricas completas del artista con comparaciones
    - 400: Error en los parámetros (ej: período custom sin fechas)
    - 500: Error al obtener las métricas
    """
    logger.info(f"Fetching metrics for artist {artist_id} (period={period}, country={country})")
    
    # Parse dates if provided
    parsed_start_date = None
    parsed_end_date = None
    if period == "custom":
        if not start_date or not end_date:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    "start_date and end_date are required for custom period",
                    f"/metrics/artists/{artist_id}"
                ),
            )
        try:
            from datetime import datetime
            parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    f"Invalid date format: {str(e)}",
                    f"/metrics/artists/{artist_id}"
                ),
            )
    
    metrics = await metrics_db.get_artist_metrics(
        artist_id, 
        period=period,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        country=country
    )
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
async def get_my_artist_metrics(
    user: dict = Depends(verify_token),
    period: str = "monthly",
    start_date: str = None,
    end_date: str = None,
    country: str = None
):
    """
    Obtener las métricas generales del artista autenticado con filtros opcionales.
    
    Este endpoint retorna las estadísticas propias del artista que hace la solicitud,
    proporcionando un dashboard de métricas personales con comparaciones temporales.
    Es el endpoint principal para que los artistas vean su propio rendimiento.
    
    **Parámetros de consulta opcionales:**
    - period: Tipo de período ('daily', 'weekly', 'monthly', 'custom'). Default: 'monthly'
    - start_date: Fecha de inicio para período custom (ISO 8601 format). Requerido si period='custom'
    - end_date: Fecha de fin para período custom (ISO 8601 format). Requerido si period='custom'
    - country: Código ISO del país para filtrar (ej: 'US', 'AR', 'BR')
    
    **Métricas retornadas:**
    - monthlyListeners: Oyentes únicos del período
    - plays: Total de reproducciones del período
    - saves: Total de saves/likes del período  
    - shares: Total de shares del período
    - Cada métrica incluye: value (valor actual), delta (cambio vs período anterior), percentChange (% de cambio)
    
    **Validaciones:**
    - El usuario debe ser un artista (tener stage_name)
    
    **Retorna:**
    - 200: Métricas completas del artista con comparaciones
    - 400: Error en los parámetros (ej: período custom sin fechas)
    - 403: Usuario no es un artista
    - 500: Error al obtener las métricas
    """
    artist_id = user["user_id"]
    logger.info(f"Fetching metrics for authenticated artist {artist_id} (period={period}, country={country})")
    
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
    
    # Parse dates if provided
    parsed_start_date = None
    parsed_end_date = None
    if period == "custom":
        if not start_date or not end_date:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    "start_date and end_date are required for custom period",
                    "/metrics/artists/me/overview"
                ),
            )
        try:
            from datetime import datetime
            parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    f"Invalid date format: {str(e)}",
                    "/metrics/artists/me/overview"
                ),
            )
    
    metrics = await metrics_db.get_artist_metrics(
        artist_id,
        period=period,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        country=country
    )
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

@router.get("/artists/{artist_id}/top-songs", status_code=200)
async def get_artist_top_songs(
    artist_id: str,
    user: dict = Depends(verify_token),
    limit: int = 10,
    sort_by: str = "plays",
    start_date: str = None,
    end_date: str = None,
    country: str = None
):
    """
    Obtener el top de canciones de un artista ordenadas por reproducciones o likes.
    
    Este endpoint permite visualizar las canciones más populares de un artista según diferentes métricas,
    facilitando el análisis de qué contenido tiene mejor rendimiento.
    
    **Parámetros de ruta:**
    - artist_id: ID del artista
    
    **Parámetros de consulta opcionales:**
    - limit: Número de canciones a retornar (default: 10)
    - sort_by: Ordenar por 'plays' o 'likes' (default: 'plays')
    - start_date: Fecha de inicio para filtrar reproducciones (ISO 8601 format)
    - end_date: Fecha de fin para filtrar reproducciones (ISO 8601 format)
    - country: Código ISO del país para filtrar (ej: 'US', 'AR', 'BR')
    
    **Respuesta:**
    - Lista de canciones con:
        - songId, title, artist, coverUrl
        - plays: Número de reproducciones (filtradas por período/país si se especifica)
        - likes: Número total de likes (acumulado, sin filtro de fecha)
    
    **Retorna:**
    - 200: Lista de top canciones del artista
    - 400: Error en los parámetros
    - 500: Error al obtener los datos
    """
    logger.info(f"Fetching top songs for artist {artist_id} (sort_by={sort_by}, limit={limit})")
    
    # Validate sort_by
    if sort_by not in ["plays", "likes"]:
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request",
                "sort_by must be 'plays' or 'likes'",
                f"/metrics/artists/{artist_id}/top-songs"
            ),
        )
    
    # Parse dates if provided
    parsed_start_date = None
    parsed_end_date = None
    if start_date:
        try:
            from datetime import datetime
            parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    f"Invalid start_date format: {str(e)}",
                    f"/metrics/artists/{artist_id}/top-songs"
                ),
            )
    if end_date:
        try:
            from datetime import datetime
            parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    f"Invalid end_date format: {str(e)}",
                    f"/metrics/artists/{artist_id}/top-songs"
                ),
            )
    
    try:
        top_songs = await metrics_db.get_artist_top_songs(
            artist_id,
            limit=limit,
            sort_by=sort_by,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            country=country
        )
        
        return {"data": top_songs}
        
    except Exception as e:
        logger.error(f"Failed to get top songs for artist {artist_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                str(e),
                f"/metrics/artists/{artist_id}/top-songs"
            ),
        )

@router.get("/artists/{artist_id}/top-markets", status_code=200)
async def get_artist_top_markets(
    artist_id: str,
    user: dict = Depends(verify_token),
    limit: int = 10,
    start_date: str = None,
    end_date: str = None
):
    """
    Obtener los principales mercados (países) donde el artista tiene más reproducciones.
    
    Este endpoint permite identificar en qué países o regiones el artista tiene mayor audiencia,
    útil para planificación de giras, marketing regional y estrategias de distribución.
    
    **Parámetros de ruta:**
    - artist_id: ID del artista
    
    **Parámetros de consulta opcionales:**
    - limit: Número de mercados a retornar (default: 10)
    - start_date: Fecha de inicio para filtrar reproducciones (ISO 8601 format)
    - end_date: Fecha de fin para filtrar reproducciones (ISO 8601 format)
    
    **Respuesta:**
    - Lista de mercados ordenados por número de reproducciones con:
        - country: Código ISO del país (ej: 'US', 'AR', 'BR')
        - plays: Número de reproducciones en ese mercado
        - listeners: Número de oyentes únicos en ese mercado
    
    **Nota:** Solo se incluyen reproducciones que tienen información de país.
    
    **Retorna:**
    - 200: Lista de top mercados del artista
    - 400: Error en los parámetros (formato de fecha inválido)
    - 500: Error al obtener los datos
    """
    logger.info(f"Fetching top markets for artist {artist_id} (limit={limit})")
    
    # Parse dates if provided
    parsed_start_date = None
    parsed_end_date = None
    if start_date:
        try:
            from datetime import datetime
            parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    f"Invalid start_date format: {str(e)}",
                    f"/metrics/artists/{artist_id}/top-markets"
                ),
            )
    if end_date:
        try:
            from datetime import datetime
            parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400, "Bad Request",
                    f"Invalid end_date format: {str(e)}",
                    f"/metrics/artists/{artist_id}/top-markets"
                ),
            )
    
    try:
        top_markets = await metrics_db.get_artist_top_markets(
            artist_id,
            limit=limit,
            start_date=parsed_start_date,
            end_date=parsed_end_date
        )
        
        return {"data": top_markets}
        
    except Exception as e:
        logger.error(f"Failed to get top markets for artist {artist_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                str(e),
                f"/metrics/artists/{artist_id}/top-markets"
            ),
        )

@router.get("/artists/{artist_id}/top-playlists", status_code=200)
async def get_artist_top_playlists(
    artist_id: str,
    user: dict = Depends(verify_token),
    limit: int = 10
):
    """
    Obtener las principales playlists que incluyen canciones del artista.
    
    Este endpoint identifica las playlists más relevantes que contienen música del artista,
    útil para entender cómo se está curando y distribuyendo su contenido en la plataforma.
    
    **Parámetros de ruta:**
    - artist_id: ID del artista
    
    **Parámetros de consulta opcionales:**
    - limit: Número de playlists a retornar (default: 10)
    
    **Respuesta:**
    - Lista de playlists ordenadas por cantidad de canciones del artista que contienen:
        - playlistId, name, description, coverUrl
        - userId: ID del creador de la playlist
        - songCount: Número de canciones del artista en la playlist
        - isPublished: Si la playlist está publicada
    
    **Caso de uso:**
    - Identificar playlists populares con tu música
    - Contactar curadores de playlists
    - Analizar cómo se agrupa tu música
    
    **Retorna:**
    - 200: Lista de top playlists que incluyen canciones del artista
    - 500: Error al obtener los datos
    """
    logger.info(f"Fetching top playlists for artist {artist_id} (limit={limit})")
    
    try:
        top_playlists = await metrics_db.get_artist_top_playlists(
            artist_id,
            limit=limit
        )
        
        return {"data": top_playlists}
        
    except Exception as e:
        logger.error(f"Failed to get top playlists for artist {artist_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500, "Internal Server Error",
                str(e),
                f"/metrics/artists/{artist_id}/top-playlists"
            ),
        )

