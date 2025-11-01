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
        
        if collection["artistId"] != user["user_id"]:
            return JSONResponse(
                status_code=401,
                content=create_error_response(
                    401,
                    "Unauthorized",
                    "You are not authorized to upload a cover for this collection",
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

    if user["stage_name"] == "":
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", "User is not an artist", "/collections"),
        )

    try:
        # uploaded_file = await storage_db.upload_cover_image(collection.artistId, collection.type, file)
        db_collection, e = await collections_db.create_collection(collection.name, user["user_id"], user["stage_name"], collection.type, "None", collection.songIds)
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


@router.put("/{collection_id}", status_code=200)
async def update_collection(collection_id: str, update_request: schemas.UpdateCollectionRequest, user: dict = Depends(verify_token)):
    logger.info(f"Updating collection {collection_id}")
    try:
        collection = await collections_db.get_collection(collection_id)
        if collection is None:
            logger.warning(f"Collection with id={collection_id} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Collection with id {collection_id} not found",
                    f"/collections/{collection_id}",
                ),
            )
        
        # Verify user is the owner of the collection
        if collection["artistId"] != user["user_id"]:
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to update this collection",
                    f"/collections/{collection_id}",
                ),
            )
        
        # Build update dictionary with only provided fields
        update_data = {}
        if update_request.name is not None:
            update_data["name"] = update_request.name
        if update_request.type is not None:
            update_data["type"] = update_request.type
        if update_request.coverUrl is not None:
            update_data["coverUrl"] = update_request.coverUrl
        
        # Update collection metadata if there are fields to update
        if update_data:
            success = await collections_db.update_collection(collection_id, update_data)
            if not success:
                return JSONResponse(
                    status_code=500,
                    content=create_error_response(
                        500,
                        "Internal Server Error",
                        "Failed to update collection",
                        f"/collections/{collection_id}",
                    ),
                )
        
        # Update songs if songIds is provided
        if update_request.songIds is not None:
            await collections_db.delete_songs_from_collection(collection_id)
            order = 0
            for songId in update_request.songIds:
                if not await collections_db.add_song_to_collection(songId, collection_id, order):
                    logger.error(f"Failed to add song {songId} to collection")
                order += 1
        
        # Get updated collection with songs
        collection = await collections_db.get_collection(collection_id)
        songs = await collections_db.get_songs_from_collection(collection_id)

        return {"data": serialize_collection(collection, songs)}

    except Exception as e:
        logger.error(f"Failed to update collection: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                f"/collections/{collection_id}",
            ),
        )


@router.get("/popular", status_code=200)
async def get_popular_collections(limit: int = 50, type: str = None, user: dict = Depends(verify_token)):
    """
    Get collections ordered by popularity (most played first).
    
    Query Parameters:
    - limit: Maximum number of collections to return (default: 50, max: 100)
    - type: Optional filter by collection type (album, single, ep)
    """
    logger.info(f"Fetching popular collections (limit={limit}, type={type})")
    
    # Validate limit
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 10
    
    try:
        collections = await collections_db.get_popular_collections(limit=limit, type=type)
        serialized_collections = []
        for collection in collections:
            songs = await collections_db.get_songs_from_collection(collection["_id"])
            serialized_collections.append(serialize_collection(collection, songs))
        return {"data": serialized_collections}

    except Exception as e:
        logger.error(f"Failed to fetch popular collections: {str(e)}")
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