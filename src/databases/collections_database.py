from datetime import datetime, timezone
from resources.logger import logger
from pymongo import DESCENDING
from db.database import get_db
from db.models import CollectionSong
from bson import ObjectId

async def create_collection(name, artistId, artistName, type, coverUrl, songIds):
    db = get_db()
    try:
        collection_doc = {
            "name": name,
            "artistId": artistId,
            "artistName": artistName,
            "type": type,
            "coverUrl": coverUrl,
        }
        result = db.collections.insert_one(collection_doc)
        logger.info(f"Successfully created collection: title={name}, artist={artistName}, type={type}, id={result.inserted_id}")

        order = 0
        for songId in songIds:
            if not await add_song_to_collection(songId, result.inserted_id, order):
                logger.error(f"Failed to add song {songId} to collection")
            order += 1
        collection = db.collections.find_one({"_id": result.inserted_id})
        return (collection, None)

    except Exception as e:
        logger.error(f"Failed to create collection: {str(e)}")
        return (None, e)


async def add_song_to_collection(song_id: str, collection_id: str, order):
    db = get_db()
    song_oid = ObjectId(song_id)
    collection_oid = ObjectId(collection_id)

    collection_song = CollectionSong(song_id=song_oid, collection_id=collection_oid, order=order)
    db.collection_songs.insert_one(collection_song.model_dump(by_alias=True))
    logger.info(f"Added song {song_id} to collection")
    return True


async def delete_collection(existing_collection):
    db = get_db()
    try:
        result = db.collections.delete_one({"_id": existing_collection["_id"]})
        if result.deleted_count > 0:
            logger.info(f"Successfully deleted collection with id={existing_collection['_id']}")
        else:
            logger.warning(f"Collection with id={existing_collection['_id']} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to delete collection with id={existing_collection['_id']}: {str(e)}")


async def get_collection(id):
    db = get_db()
    try:
        collection = db.collections.find_one({"_id": ObjectId(id)})
        if collection is None:
            logger.warning(f"Collection with id={id} not found")
            return None
                
        logger.info(f"Successfully retrieved collection '{collection['name']}'")
        return collection
    except Exception as e:
        logger.error(f"Failed to get collection with id={id}: {str(e)}")
        return None

async def get_songs_from_collection(collection_id: str):
    db = get_db()

    collection_songs = list(db.collection_songs.find(
        {"collection_id": ObjectId(collection_id)},
        {"song_id": 1, "order": 1}
    ))

    if not collection_songs:
        return []

    song_ids = [ps["song_id"] for ps in collection_songs]
    if not song_ids:
        return []

    songs = list(db.songs.find({"_id": {"$in": song_ids}}))
    song_map = {song["_id"]: song for song in songs}
    return [
        {**song_map[ps["song_id"]], "order": ps["order"]}
        for ps in collection_songs
        if ps["song_id"] in song_map
    ]

async def get_collections(type: str = None, artistId: str = None):
    db = get_db()

    try:
        query = {}
        if type:
            query["type"] = type
        if artistId:
            query["artistId"] = artistId

        collections = list(
            db.collections.find(query)
            .sort([("_id", DESCENDING)])
        )
        logger.info(f"Retrieved {len(collections)} collections from database")
        return collections
    except Exception as e:
        logger.error(f"Failed to retrieve collections: {str(e)}")
        return []
    
async def delete_songs_from_collection(collection_id: str):
    db = get_db()

    try:
        result = db.collection_songs.delete_many({ "collection_id": ObjectId(collection_id)})
        logger.info(f"Se eliminaron {result.deleted_count} de collection_sogns")
        return
    except Exception as e:
        logger.error(f"Failed to delete songs from collections: {str(e)}")
        return

async def update_collection_cover(collection_id: str, cover_url: str):
    db = get_db()
    result = db.collections.update_one(
        {"_id": ObjectId(collection_id)},
        {"$set": {"coverUrl": cover_url}}
    )
    return result.modified_count > 0

async def update_collection(collection_id: str, update_data: dict):
    """
    Updates collection fields based on the provided update_data dictionary.
    Only updates fields that are present in update_data.
    
    Args:
        collection_id: The ID of the collection to update
        update_data: Dictionary containing the fields to update
        
    Returns:
        Boolean indicating if the update was successful
    """
    db = get_db()
    try:
        if not update_data:
            logger.warning(f"No fields to update for collection {collection_id}")
            return True
            
        result = db.collections.update_one(
            {"_id": ObjectId(collection_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Successfully updated collection {collection_id} with fields: {list(update_data.keys())}")
        else:
            logger.info(f"No changes made to collection {collection_id}")
            
        return True
    except Exception as e:
        logger.error(f"Failed to update collection {collection_id}: {str(e)}")
        return False