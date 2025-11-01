from datetime import datetime, timezone
from resources.logger import logger
from pymongo import DESCENDING
from db.database import get_db
from db.models import CollectionSong
from bson import ObjectId

async def create_collection(name, artistId, artistName, type, coverUrl, songIds, releaseDate=None):
    db = get_db()
    try:
        collection_doc = {
            "name": name,
            "artistId": artistId,
            "artistName": artistName,
            "type": type,
            "coverUrl": coverUrl,
            "createdAt": datetime.now(timezone.utc),
            "releaseDate": releaseDate if releaseDate else datetime.now(timezone.utc),
        }
        result = db.collections.insert_one(collection_doc)
        logger.info(f"Successfully created collection: title={name}, artist={artistName}, type={type}, id={result.inserted_id}, releaseDate={releaseDate}")

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


async def get_collection(id, includeUnpublished: bool = False):
    db = get_db()
    try:
        query = {"_id": ObjectId(id)}
        
        # Filter by release date unless includeUnpublished is True
        if not includeUnpublished:
            query["releaseDate"] = {"$lte": datetime.now(timezone.utc)}
        
        collection = db.collections.find_one(query)
        if collection is None:
            logger.warning(f"Collection with id={id} not found or not yet released")
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

async def get_collections(type: str = None, artistId: str = None, includeUnpublished: bool = False):
    db = get_db()

    try:
        query = {}
        if type:
            query["type"] = type
        if artistId:
            query["artistId"] = artistId
        
        # Filter by release date unless includeUnpublished is True
        if not includeUnpublished:
            query["releaseDate"] = {"$lte": datetime.now(timezone.utc)}

        collections = list(
            db.collections.find(query)
            .sort([("createdAt", DESCENDING), ("name", 1)])
        )
        logger.info(f"Retrieved {len(collections)} collections from database (includeUnpublished={includeUnpublished})")
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

async def publish_collection_now(collection_id: str, artist_id: str):
    """
    Publishes a collection immediately by setting its release date to now.
    Only works if the collection is unpublished and belongs to the requesting artist.
    
    Args:
        collection_id: The ID of the collection to publish
        artist_id: The ID of the artist making the request
        
    Returns:
        Tuple of (success: bool, error_message: str or None)
    """
    db = get_db()
    try:
        # Get collection including unpublished ones
        collection = await get_collection(collection_id, includeUnpublished=True)
        
        if not collection:
            return (False, "Collection not found")
        
        # Check if artist owns the collection
        if collection["artistId"] != artist_id:
            return (False, "You are not authorized to publish this collection")
        
        # Check if collection is already published
        if collection.get("releaseDate"):
            release_date = collection["releaseDate"]
            # Ensure both datetimes are timezone-aware for comparison
            if release_date.tzinfo is None:
                release_date = release_date.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            if release_date <= now:
                return (False, "Collection is already published")
        
        # Update release date to now
        result = db.collections.update_one(
            {"_id": ObjectId(collection_id)},
            {"$set": {"releaseDate": datetime.now(timezone.utc)}}
        )
        
        if result.modified_count > 0:
            logger.info(f"Successfully published collection {collection_id}")
            return (True, None)
        else:
            logger.warning(f"Failed to publish collection {collection_id}")
            return (False, "Failed to publish collection")
            
    except Exception as e:
        logger.error(f"Failed to publish collection {collection_id}: {str(e)}")
        return (False, str(e))

async def get_popular_collections(artistId: str, limit: int = 50, type: str = None, includeUnpublished: bool = False):
    """
    Get collections ordered by popularity (total plays descending) for a specific artist.
    
    Args:
        artistId: Artist ID (required)
        limit: Maximum number of collections to return
        type: Optional filter by collection type (album, single, ep)
        includeUnpublished: Whether to include unpublished collections (default: False)
        
    Returns:
        List of collections with popularity metrics
    """
    db = get_db()
    try:
        # Get all collections for the artist with optional type filter
        query = {"artistId": artistId}
        if type:
            query["type"] = type
        
        # Filter by release date unless includeUnpublished is True
        if not includeUnpublished:
            query["releaseDate"] = {"$lte": datetime.now(timezone.utc)}
            
        collections = list(db.collections.find(query))
        
        # Calculate popularity for each collection (total plays)
        collections_with_metrics = []
        for collection in collections:
            # Get all songs in the collection
            collection_songs = list(db.collection_songs.find(
                {"collection_id": collection["_id"]},
                {"song_id": 1}
            ))
            song_ids = [cs["song_id"] for cs in collection_songs]
            
            # Count total plays for all songs in collection from permanent plays table
            total_plays = 0
            if song_ids:
                total_plays = db.plays.count_documents({"song_id": {"$in": song_ids}})
            
            # Add popularity metric to collection
            collection["totalPlays"] = total_plays
            collections_with_metrics.append(collection)
        
        # Sort by total plays descending
        collections_with_metrics.sort(key=lambda x: x["totalPlays"], reverse=True)
        
        # Return limited results
        result = collections_with_metrics[:limit]
        logger.info(f"Retrieved {len(result)} popular collections")
        return result
        
    except Exception as e:
        logger.error(f"Failed to retrieve popular collections: {str(e)}")
        return []