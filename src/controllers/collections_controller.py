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
from fastapi import UploadFile, File, Form

router = APIRouter()

@router.post("/{collection_id}/upload-cover", status_code=201)
async def upload_collection_cover(collection_id: str, file: UploadFile = File(...), user: dict = Depends(verify_token)):
    try:
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

        result = await storage_db.upload_cover_image("albums", collection["artistId"], file)
        cover_url = result["coverUrl"]

        updated = await collections_db.update_collection_cover(collection_id, cover_url)
        if not updated:
            logger.error(f"Failed to update playlist cover for id {collection_id}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    "Failed to update collection cover",
                    f"/collection/{collection_id}/upload-cover"
                ),
            )

        logger.info(f"Successfully updated collection cover for {collection_id}")
        return {"coverUrl": cover_url}

    except Exception as e:
        logger.error(f"Failed to upload playlist cover: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                f"/collection/{collection_id}/upload-cover"
            ),
        )

@router.post("/", status_code=201)
async def create_collection(collection: schemas.CreateCollectionRequest, user: dict = Depends(verify_token)):
    logger.info(
        f"Creating collection {collection.name}"
    )

    try:
        # uploaded_file = await storage_db.upload_cover_image(collection.artistId, collection.type, file)
        db_collection, e = await collections_db.create_collection(collection.name, collection.artistId, collection.artistName, collection.type, "None", collection.songIds)
        if not db_collection:
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", str(e), "/collections"),
            )

        songs = await collections_db.get_songs_from_collection(db_collection['_id'])
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


@router.post("/{collection_id}/modify", status_code=200)
async def modify_songs_in_collection(collection_id: str, collection_songs_in_order: schemas.ModifyCollectionRequest, user: dict = Depends(verify_token)):
    logger.info(f"Modifying songs in collection")
    try:
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
        await collections_db.delete_songs_from_collection(collection_id)
        order = 0
        for songId in collection_songs_in_order.songIds:
            if not await collections_db.add_song_to_collection(songId, collection_id, order):
                logger.error(f"Failed to add song {songId} to collection")
            order += 1

        collection = await collections_db.get_collection(collection_id)
        songs = await collections_db.get_songs_from_collection(collection_id)

        return {"data": serialize_collection(collection, songs)}

    except Exception as e:
        logger.error(f"Failed to fetch collections: {str(e)}")
        raise


@router.get("/", status_code=200)
async def get_collections(type: str = None, artistId: str = None, user: dict = Depends(verify_token)):
    logger.info(f"Fetching collections (type={type}, artistId={artistId})")
    try:
        collections = await collections_db.get_collections(type=type, artistId=artistId)
        serialized_collections = []
        for collection in collections:
            songs = await collections_db.get_songs_from_collection(collection["_id"])
            serialized_collections.append(serialize_collection(collection, songs))
        return {"data": serialized_collections}

    except Exception as e:
        logger.error(f"Failed to fetch collections: {str(e)}")
        raise


@router.get("/{collection_id}", status_code=200)
async def get_collection(collection_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Fetching collection collection_id={collection_id}")
    try:
        collection = await collections_db.get_collection(collection_id)
        songs = await collections_db.get_songs_from_collection(collection["_id"])

        return {"data": serialize_collection(collection, songs)}

    except Exception as e:
        logger.error(f"Failed to fetch collections: {str(e)}")
        raise