from typing import Optional
from databases.collections_database import USER_API_BASE
import databases.playlists_database as playlists_db
import databases.songs_database as songs_db
import databases.history_database as history_db
import databases.metrics_database as metrics_db
import schemas
from fastapi import Body, Depends, Header
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter
from common.utils import create_error_response, serialize_playlist
from auth import verify_token

router = APIRouter()

@router.post("/")
async def add_to_history(request: schemas.ListeningHistoryRequest, user: dict = Depends(verify_token)):
    """
    Agregar una canción al historial de reproducción del usuario.
    
    Este endpoint registra que el usuario ha reproducido una canción, agregándola a su historial
    de escucha. También registra la reproducción en las métricas permanentes para estadísticas del artista.
    
    **Comportamiento:**
    - Si el historial del usuario está pausado, no se registra la reproducción
    - Valida que la canción exista antes de registrar
    - Registra la reproducción en dos lugares: historial del usuario y métricas permanentes
    - Si ya existe la canción en el historial, actualiza la fecha de última reproducción
    
    **Cuerpo de la solicitud:**
    - songId: ID de la canción reproducida
    - progress: Progreso de reproducción en segundos (opcional)
    
    **Retorna:**
    - 201: Canción agregada al historial exitosamente
    - 200: Historial pausado, reproducción no registrada
    - 404: Canción no encontrada
    - 400: Error en la solicitud
    """
    logger.info(f"Adding song with id {request.songId} to user {user['user_id']}'s listening history")
    
    # Check if user's history is paused
    state = await history_db.get_history_state(user["user_id"])
    if state and state.get("isPaused", False):
        logger.info(f"History is paused for user {user['user_id']}")
        return JSONResponse(status_code=200, content={"message": "History is paused"})

    song = await songs_db.get_song(request.songId)
    if not song:
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404, "Not Found",
                f"Song with id {request.songId} not found",
                f"/history"
            ),
        )

    error = await history_db.add_to_history(request.songId, user["user_id"])
    if error:
        logger.info(f"Failed to log song with id {request.songId} to user {user['user_id']}'s listening history")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(error), "/history"),
        )

    # Record play in permanent metrics table (separate from user history)
    metrics_error = await metrics_db.record_play(user["user_id"], request.songId, request.country)
    if metrics_error:
        logger.warning(f"Failed to record play metrics for song {request.songId}: {str(metrics_error)}")
        # Don't fail the request if metrics recording fails, just log it

    logger.info(f"Succesfully logged song with id {request.songId} to user {user['user_id']}'s listening history")
    return JSONResponse(status_code=201, content={"message": "Added to history"})

@router.get(
    "/",
    responses={
        200: {
            "description": "Successfully retrieved listening history",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "song": {
                                    "_id": "507f1f77bcf86cd799439011",
                                    "title": "Bohemian Rhapsody",
                                    "artist": "Queen",
                                    "coverUrl": "https://example.com/cover.jpg"
                                },
                                "playedAt": "2025-11-10T14:30:00Z",
                                "progress": 180
                            },
                            {
                                "song": {
                                    "_id": "507f1f77bcf86cd799439012",
                                    "title": "Imagine",
                                    "artist": "John Lennon",
                                    "coverUrl": "https://example.com/imagine.jpg"
                                },
                                "playedAt": "2025-11-10T13:15:00Z",
                                "progress": 90
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_history(
    user: dict = Depends(verify_token), 
    search: str = None
):
    """
    Obtener el historial de reproducción del usuario autenticado.
    
    Este endpoint retorna la lista completa de canciones que el usuario ha reproducido,
    ordenadas desde la más reciente hasta la más antigua. Incluye información detallada
    de cada canción y el progreso de reproducción guardado.
    
    **Parámetros de consulta opcionales:**
    - `search`: Filtrar el historial por título de canción o nombre de artista (no distingue mayúsculas/minúsculas)
    
    **Respuesta:**
    - Lista de entradas del historial, cada una conteniendo:
        - `song`: Detalles de la canción (_id, title, artist, coverUrl)
        - `playedAt`: Timestamp ISO 8601 de cuándo se reprodujo la canción por última vez
        - `progress`: Progreso de reproducción en segundos
    
    **Nota:** Si el usuario no tiene historial de reproducción, retorna una lista vacía en el campo data.
    
    **Retorna:**
    - 200: Lista del historial de reproducción
    - 400: Error en la solicitud
    """
    try:
        logger.info(f"Fetching listening history for user {user['user_id']} with search={search}")
        history_entries = await history_db.get_user_history(user["user_id"], search)

        if not history_entries:
            logger.info(f"No listening history found for user {user['user_id']}")
            return {"data": []}

        full_history = []
        for entry in history_entries:
            song = await songs_db.get_song(entry["songId"])
            if song:
                full_history.append({
                    "song": {
                        "_id": str(song["_id"]),
                        "title": song["title"],
                        "artist": song["artist"],
                        "coverUrl": song.get("coverUrl")
                    },
                    "playedAt": entry.get("playedAt"),
                    "progress": entry.get("progress")
                })

        logger.info(f"Successfully retrieved {len(full_history)} entries for user {user['user_id']}")
        return {"data": full_history}

    except Exception as e:
        logger.error(f"Failed to retrieve history for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), f"/history?userId={user['user_id']}"
            ),
        )

@router.put("/")
async def update_song_progress(request: schemas.ListeningHistoryRequest, user: dict = Depends(verify_token)):
    """
    Actualizar el progreso de reproducción de una canción en el historial.
    
    Este endpoint permite actualizar el punto de reproducción guardado de una canción en el historial
    del usuario. Es útil para permitir que el usuario continúe reproduciendo desde donde dejó
    una canción previamente escuchada.
    
    **Cuerpo de la solicitud:**
    - songId: ID de la canción
    - progress: Progreso de reproducción en segundos (posición actual en la canción)
    
    **Validaciones:**
    - La canción debe existir en el historial del usuario
    
    **Retorna:**
    - 200: Progreso actualizado exitosamente
    - 400: Error en la actualización (ej: canción no está en el historial)
    """
    logger.info(f"Updating progress for song {request.songId} for user {user['user_id']}")
    
    error = await history_db.update_history_progress(user["user_id"], request.songId, request.progress)
    if error:
        logger.error(f"Failed to update progress for song {request.songId}: {str(error)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(error), "/history")
        )

    logger.info(f"Successfully updated progress for song {request.songId}")
    return JSONResponse(status_code=200, content={"message": "Progress updated"})

@router.delete("/")
async def clear_history(user: dict = Depends(verify_token)):
    """
    Eliminar todo el historial de reproducción del usuario.
    
    Este endpoint borra permanentemente todas las entradas del historial de escucha del usuario autenticado.
    Es una operación irreversible que elimina todo el registro de canciones reproducidas.
    
    **Importante:** Esta operación NO afecta las métricas permanentes de los artistas (contadores de reproducciones),
    solo elimina el historial personal del usuario.
    
    **Retorna:**
    - 200: Historial eliminado exitosamente
    - 400: Error al intentar eliminar el historial
    """
    try:
        await history_db.clear_user_history(user["user_id"])
        logger.info(f"Cleared history entries for user {user['user_id']}")
        return JSONResponse(
            status_code=200,
            content={"message": f"Cleared history entries"}
        )
    except Exception as e:
        logger.error(f"Failed to clear history for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), f"/history?userId={user['user_id']}")
        )

@router.post(
    "/state/toggle",
    responses={
        200: {
            "description": "Successfully toggled history state",
            "content": {
                "application/json": {
                    "examples": {
                        "paused": {
                            "summary": "History was paused",
                            "value": {"message": "History paused", "isPaused": True}
                        },
                        "resumed": {
                            "summary": "History was resumed",
                            "value": {"message": "History resumed", "isPaused": False}
                        }
                    }
                }
            }
        }
    }
)
async def toggle_history_state(user: dict = Depends(verify_token)):
    """
    Alternar el estado de pausa/activación del historial de reproducción.
    
    Este endpoint permite al usuario pausar o reanudar el registro de su historial de escucha.
    Es útil para sesiones privadas o cuando el usuario no quiere que se registren ciertas reproducciones.
    
    **Comportamiento:**
    - Si el historial está actualmente **activo**, se **pausará**
    - Si el historial está actualmente **pausado**, se **reanudará**
    - Para usuarios nuevos: Crea un nuevo registro de estado y pausa el historial
    
    **Cuando el historial está pausado:**
    - Las canciones NO se agregarán al historial de reproducción
    - El historial existente permanece accesible y no se modifica
    - Las métricas de artistas se siguen registrando normalmente
    
    **Respuesta:**
    - `message`: "History paused" o "History resumed"
    - `isPaused`: Estado actual después del toggle (true/false)
    
    **Retorna:**
    - 200: Estado alternado exitosamente
    - 500: Error al alternar el estado
    """
    try:
        result = await history_db.toggle_history_state(user["user_id"])
        if result is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(500, "Internal Server Error", "Failed to toggle history state", "/history/state/toggle")
            )
        
        action = "paused" if result["isPaused"] else "resumed"
        logger.info(f"History {action} for user {user['user_id']}")
        return JSONResponse(
            status_code=200,
            content={"message": f"History {action}", "isPaused": result["isPaused"]}
        )
    except Exception as e:
        logger.error(f"Failed to toggle history state for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/history/state/toggle")
        )

@router.get(
    "/state",
    responses={
        200: {
            "description": "Current history pause state",
            "content": {
                "application/json": {
                    "examples": {
                        "paused": {
                            "summary": "History is paused",
                            "value": {"isPaused": True}
                        },
                        "active": {
                            "summary": "History is active (default)",
                            "value": {"isPaused": False}
                        }
                    }
                }
            }
        }
    }
)
async def get_history_state(user: dict = Depends(verify_token)):
    """
    Consultar el estado actual de pausa del historial de reproducción.
    
    Este endpoint permite verificar si el historial del usuario está actualmente pausado o activo.
    Es útil para mostrar el estado correcto en la interfaz de usuario y determinar si se deben
    registrar las reproducciones.
    
    **Retorna:**
    - `isPaused`: `true` si el historial está pausado, `false` si está activo (por defecto)
    
    **Comportamiento por defecto:**
    - Los usuarios que nunca han pausado su historial recibirán `isPaused: false`
    - El estado se crea automáticamente la primera vez que se consulta
    
    **Casos de uso:**
    - Verificar el estado antes de intentar agregar canciones al historial
    - Mostrar el estado correcto del botón pausar/reanudar en la UI
    - Sincronizar el estado entre diferentes dispositivos o sesiones
    
    **Retorna:**
    - 200: Estado del historial
    - 500: Error al obtener el estado
    """
    try:
        state = await history_db.get_history_state(user["user_id"])
        if state is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(500, "Internal Server Error", "Failed to get history state", "/history/state")
            )
        
        logger.info(f"Retrieved history state for user {user['user_id']}: isPaused={state['isPaused']}")
        return JSONResponse(
            status_code=200,
            content=state
        )
    except Exception as e:
        logger.error(f"Failed to get history state for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/history/state")
        )
