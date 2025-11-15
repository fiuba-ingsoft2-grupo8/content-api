import schemas
import databases.collections_database as collections_db, databases.songs_database as songs_db
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter, Depends
from common.utils import create_error_response, serialize_song, serialize_playlist, serialize_collection
from auth import verify_token
from fastapi import Header


router = APIRouter()

@router.get(
    "/",
    responses={
        200: {
            "description": "Search results",
            "content": {
                "application/json": {
                    "example": {
                        "collections": {
                            "playlists": [
                                {
                                    "_id": "507f1f77bcf86cd799439011",
                                    "name": "Rock Classics",
                                    "userId": "user_123",
                                    "is_published": True,
                                    "songs": []
                                }
                            ],
                            "songs": [
                                {
                                    "_id": "507f1f77bcf86cd799439012",
                                    "title": "Bohemian Rhapsody",
                                    "artist": "Queen",
                                    "duration": "354"
                                }
                            ],
                            "users": [
                                {"id": "user_456"}
                            ]
                        }
                    }
                }
            }
        }
    }
)
async def search(str_name: str, user: dict = Depends(verify_token), authorization: str = Header(None)):
    """
    Buscar contenido por nombre o término de búsqueda.
    
    Este endpoint permite realizar búsquedas globales a través de diferentes tipos de contenido
    (playlists, canciones, usuarios) utilizando un término de búsqueda. Los resultados se agrupan
    por tipo y se enriquecen con información completa de cada elemento.
    
    **Parámetros de consulta:**
    - str_name: Término de búsqueda para buscar en nombres de playlists, canciones y usuarios
    
    **Tipos de resultados:**
    - **playlists**: Playlists que coinciden con el término de búsqueda
    - **songs**: Canciones que coinciden con el término de búsqueda
    - **users**: Usuarios que coinciden con el término de búsqueda
    
    **Comportamiento:**
    - La búsqueda es case-insensitive y busca coincidencias parciales
    - Los resultados incluyen detalles completos de cada elemento
    - Se utiliza el servicio de usuarios para expandir información de usuarios
    
    **Retorna:**
    - 200: Resultados de búsqueda agrupados por tipo (collections: {playlists, songs, users})
    - 404: No se encontraron resultados
    """
    logger.info(f"Buscando collections con nombre parecido a: {str_name}")

    collection_ids = await collections_db.get_ids_by_name(str_name, token=authorization)
    if not collection_ids:
        return create_error_response(404, "Not Found", "No collections found")

    logger.info(f"Collection IDs: {collection_ids}, type: {type(collection_ids)}")

    # Acumulador por tipo (no se pisa entre sí)
    result = {
        "playlists": [],
        "songs": [],
        "users": [],   # si todavía no vas a expandir usuarios, al menos devolvé sus IDs
    }

    # Playlists (cada item suele ser {"_id": ObjectId(...)})
    for item in collection_ids.get("playlists", []):
        pid = item.get("_id") if isinstance(item, dict) else item
        if pid:
            playlist = await collections_db.get_collection(pid)
            if playlist:
                result["playlists"].append(serialize_playlist(playlist))  # usa serializer de playlist

    # Songs
    for item in collection_ids.get("songs", []):
        sid = item.get("_id") if isinstance(item, dict) else item
        if sid:
            song = await songs_db.get_song(sid)
            if song:
                result["songs"].append(serialize_song(song))

    # Users (tu get_ids_by_name hoy devuelve [{"id": "uuid"}, ...])
    # Si por ahora no tenés cómo expandirlos, devolvé los IDs tal cual:
    for item in collection_ids.get("users", []):
        uid = item.get("id") if isinstance(item, dict) else item
        if uid:
            result["users"].append({"id": uid})

    return {"collections": result}
