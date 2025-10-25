import databases.storage_database as storage_db
import databases.collections_database as collections_db
import databases.songs_database as songs_db
import schemas
from fastapi import Depends
from auth import verify_token
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from resources.logger import logger
from common.utils import create_error_response, serialize_collection

router = APIRouter()

@router.post("/", status_code=201)
async def create_collection(collection: schemas.CreateCollectionRequest, user: dict = Depends(verify_token)):
    logger.info(
        f"Creating collection {collection.name}"
    )

    try:
        db_collection, e = await collections_db.create_collection(collection.name, collection.artistId, collection.artistName, collection.type, collection.coverUrl, collection.songIds)
        if not db_collection:
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", str(e), "/collections"),
            )
        songs = []
        for songId in collection.songIds:
            await songs.append(songs_db.get_song(songId, user))
        return {"data": serialize_collection(db_collection, songs)}
    except Exception as e:
        logger.error(f"Failed to create collection {collection.name}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/collections"),
        )


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(collection_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Deleting collection with id={collection_id}")

    collection = await collections_db.get_collection(collection_id)
    if collection is None:
        logger.warning(f"Collection with id={collection_id} not found for deletion")
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404,
                "Not Found",
                f"Collection with id {collection_id} not found",
                f"/collections/{collection_id}",
            ),
        )

    await collections_db.delete_collection(collection)
    return JSONResponse(status_code=204, content=None)


@router.post("/", status_code=201)
async def modify_songs_in_collection():
    pass