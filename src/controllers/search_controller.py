import schemas
import databases.collections_database as collections_db, databases.songs_database as songs_db
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter, Depends
from common.utils import create_error_response, serialize_song, serialize_playlist, serialize_collection
from auth import verify_token
from fastapi import Header
from bson import ObjectId
from db.database import get_db
from controllers.collections_controller import _can_access_collection


router = APIRouter()


async def _can_user_access_song(user: dict, song_id: str, db=None) -> bool:
    """
    Check if a user can access a song based on geographical restrictions of its collections.
    
    A song is accessible if:
    - User is backoffice
    - User is the owner of the song
    - Song is not in any collection (standalone - available everywhere)
    - Song is in at least one collection available in user's country
    
    Args:
        user: User dictionary from verify_token
        song_id: Song ID to check
        db: Database instance (optional, will use get_db() if not provided)
        
    Returns:
        bool: True if user can access, False otherwise
    """
    # Backoffice users can access all songs
    if user.get("user_type") == "backoffice":
        return True
    
    if db is None:
        db = get_db()
    
    # Check if user owns the song
    song = db.songs.find_one({"_id": ObjectId(song_id)})
    if song and song.get("artistId") == user.get("user_id"):
        return True
    
    # Get collections this song belongs to
    collection_songs = list(db.collection_songs.find(
        {"song_id": ObjectId(song_id)},
        {"collection_id": 1}
    ))
    
    # If song is not in any collection (standalone), it's available everywhere
    if not collection_songs:
        return True
    
    # Check if song is in at least one collection available in user's country
    user_country = user.get("country", "")
    collection_ids = [cs["collection_id"] for cs in collection_songs]
    
    collections = list(db.collections.find(
        {"_id": {"$in": collection_ids}},
        {"availableCountries": 1, "artistId": 1}
    ))
    
    for collection in collections:
        available_countries = collection.get("availableCountries", [])
        
        # If collection has no restrictions, song is accessible
        if not available_countries:
            return True
        
        # If user's country is in the available countries, song is accessible
        if user_country in available_countries:
            return True
    
    # Song is not accessible in user's country
    return False


def _can_access_collection(user: dict, collection: dict) -> bool:
    """
    Check if a user can access a collection based on geographical restrictions.
    
    Returns True if:
    - User is backoffice
    - User is the owner of the collection
    - User's country is in the collection's availableCountries list
    
    Args:
        user: User dictionary from verify_token
        collection: Collection document from database
        
    Returns:
        bool: True if user can access, False otherwise
    """
    # Backoffice users can access all collections
    if user.get("user_type") == "backoffice":
        return True
    
    # Owner can access their own collections
    if user.get("user_id") == collection.get("artistId"):
        return True
    
    # Check geographical restrictions
    user_country = user.get("country", "")
    available_countries = collection.get("availableCountries", [])
    
    # If no restrictions, available everywhere
    if not available_countries:
        return True
    
    # Check if user's country is in the available list
    return user_country in available_countries

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
        "albums": [],
        "users": [],   # si todavía no vas a expandir usuarios, al menos devolvé sus IDs
    }

    # Playlists (cada item suele ser {"_id": ObjectId(...)})
    # Note: Playlists themselves don't have geographical restrictions, 
    # but songs within them will be filtered when the playlist is accessed
    for item in collection_ids.get("playlists", []):
        pid = item.get("_id") if isinstance(item, dict) else item
        if pid:
            playlist = await collections_db.get_collection(pid)
            if playlist:
                result["playlists"].append(serialize_playlist(playlist))  # usa serializer de playlist

    # Songs - Filter by geographical restrictions based on their collections
    for item in collection_ids.get("songs", []):
        sid = item.get("_id") if isinstance(item, dict) else item
        if sid:
            # Check geographical access before fetching full song details
            if await _can_user_access_song(user, str(sid)):
                song = await songs_db.get_song(sid)
                if song:
                    result["songs"].append(serialize_song(song))

    # Albums (Collections) - Filter by geographical restrictions
    for item in collection_ids.get("albums", []):
        aid = item.get("_id") if isinstance(item, dict) else item
        if aid:
            album = await collections_db.get_collection(aid)
            if album:
                # Check geographical access before including
                if _can_access_collection(user, album):
                    # Get songs from the collection
                    songs = await collections_db.get_songs_from_collection(str(aid), include_unreleased=False)
                    result["albums"].append(serialize_collection(album, songs))

    # Users (tu get_ids_by_name hoy devuelve [{"id": "uuid"}, ...])
    # Si por ahora no tenés cómo expandirlos, devolvé los IDs tal cual:
    for item in collection_ids.get("users", []):
        uid = item.get("id") if isinstance(item, dict) else item
        if uid:
            result["users"].append({"id": uid})

    logger.info(f"Search results filtered by geographical restrictions: {len(result['playlists'])} playlists, {len(result['songs'])} songs, {len(result['albums'])} albums, {len(result['users'])} users")
    return {"collections": result}
