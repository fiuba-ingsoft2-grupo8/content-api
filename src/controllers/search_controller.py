import schemas
import databases.collections_database as collections_db, databases.songs_database as songs_db
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter, Depends
from common.utils import create_error_response, serialize_song
from auth import verify_token

router = APIRouter()

@router.get("/")
async def search(str_name: str, user: dict = Depends(verify_token)):

    # Entiendo que no hay que hacer nada con el User por ahora, porque no hay que validar nada para buscar canciones
    # Va a servir para el tema de regiones y eso.

    print(f"Buscando collections con nombre parecido a: {str_name}")
    collection_ids = await collections_db.get_ids_by_name(str_name)
    if not collection_ids:
        return create_error_response(404, "Not Found", "No collections found")

    logger.info(f'Collection IDs: {collection_ids}, type: {type(collection_ids)}')

    for coleccion, elementos in collection_ids.items():
        collections_to_return = []
        if coleccion == 'playlists':
            for cid in elementos:
                playlist = await collections_db.get_collection(cid)
                if playlist:
                    collections_to_return.append(serialize_song(playlist))
        elif coleccion == 'songs':
            for cid in elementos:
                song = await songs_db.get_song(cid)
                if song:
                    collections_to_return.append(serialize_song(song))
        
    
    #collections = [serialize_song(collection) for collection in await collections_db.get_collections_by_ids(collection_ids)]
    return JSONResponse(content={"collections": collections_to_return})

