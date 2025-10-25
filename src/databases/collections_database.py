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
            if not add_song_to_collection(songId, result.inserted_id, order):
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