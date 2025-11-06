from resources.logger import logger
from db.database import get_db
from bson import ObjectId
from datetime import datetime, timezone

async def create_song(title, artist, duration, userId):
    db = get_db()
    try:
        db_song = {"title": title, "artist": artist, "duration": duration, "artistId": userId}
        result = db.songs.insert_one(db_song)
        logger.info(f"Successfully created song with id={result.inserted_id}")
        song = db.songs.find_one({ "_id": result.inserted_id })
        return (song, None)
    except Exception as e:
        logger.error(f"Failed to create song: {str(e)}")
        return (None, e)
    
async def get_all_songs(includeUnpublished: bool = False, userId: str = None):
    """
    Get all songs, filtering out unreleased songs unless specified.
    
    A song is visible if:
    - includeUnpublished=True and userId matches the song's artistId, OR
    - The song is not in any collection (standalone), OR
    - The song is in at least one published collection (releaseDate <= now), OR
    - The song has an early_release_date that has passed in at least one collection
    
    Args:
        includeUnpublished: If True and userId matches, shows all songs for that artist
        userId: The user ID requesting the songs (for ownership check)
    """
    db = get_db()
    try:
        all_songs = list(db.songs.find())
        
        # If user wants to see their unpublished songs
        if includeUnpublished and userId:
            # Only show unpublished songs that belong to this user
            filtered_songs = [song for song in all_songs if song.get("artistId") == userId]
            logger.info(f"Retrieved {len(filtered_songs)} songs (including unpublished) for user {userId}")
            return filtered_songs
        
        # Otherwise, filter by publication status
        now = datetime.now(timezone.utc)
        visible_song_ids = set()
        
        # Get all collection_songs with early_release_date info
        collection_songs = list(db.collection_songs.find({}, {
            "song_id": 1, 
            "collection_id": 1, 
            "early_release_date": 1
        }))
        
        # Build a map of song_id -> collection_ids
        song_to_collections = {}
        for cs in collection_songs:
            song_id = str(cs["song_id"])
            if song_id not in song_to_collections:
                song_to_collections[song_id] = []
            song_to_collections[song_id].append({
                "collection_id": cs["collection_id"],
                "early_release_date": cs.get("early_release_date")
            })
        
        # Get all collections with their release dates
        collections = list(db.collections.find({}, {"_id": 1, "releaseDate": 1}))
        collection_release_map = {
            str(col["_id"]): col.get("releaseDate")
            for col in collections
        }
        
        # Check each song's visibility
        for song in all_songs:
            song_id = str(song["_id"])
            
            # Case 1: Song is not in any collection (standalone)
            if song_id not in song_to_collections:
                visible_song_ids.add(song_id)
                continue
            
            # Case 2 & 3: Check if song is in a published collection or has passed early_release_date
            for col_info in song_to_collections[song_id]:
                collection_id = str(col_info["collection_id"])
                collection_release_date = collection_release_map.get(collection_id)
                early_release_date = col_info.get("early_release_date")
                
                # Check if collection is published
                if collection_release_date:
                    # Make timezone-aware if needed
                    if collection_release_date.tzinfo is None:
                        collection_release_date = collection_release_date.replace(tzinfo=timezone.utc)
                    
                    if collection_release_date <= now:
                        visible_song_ids.add(song_id)
                        break
                
                # Check if song has early release that has passed
                if early_release_date:
                    # Make timezone-aware if needed
                    if early_release_date.tzinfo is None:
                        early_release_date = early_release_date.replace(tzinfo=timezone.utc)
                    
                    if early_release_date <= now:
                        visible_song_ids.add(song_id)
                        break
        
        # Filter songs to only visible ones
        visible_songs = [song for song in all_songs if str(song["_id"]) in visible_song_ids]
        
        logger.info(f"Retrieved {len(visible_songs)} visible songs out of {len(all_songs)} total")
        return visible_songs
        
    except Exception as e:
        logger.error(f"Failed to retrieve songs: {str(e)}")
        return []

async def get_song(id, includeUnpublished: bool = False, userId: str = None):
    """
    Get a specific song by ID.
    
    Args:
        id: Song ID
        includeUnpublished: If True and userId matches, allows viewing unpublished songs
        userId: The user ID requesting the song (for ownership check)
    
    Returns:
        Song dict if found and visible, None otherwise
    """
    db = get_db()
    song = db.songs.find_one({"_id": ObjectId(id)})
    if song is None:
        logger.warning(f"Song with id={id} not found")
        return None
    
    # If user wants to see their unpublished song and they own it
    if includeUnpublished and userId and song.get("artistId") == userId:
        logger.info(f"Successfully retrieved unpublished song: title='{song['title']}' (owner access)")
        return song
    
    # Check if song is published
    if not await is_song_published(id, db):
        logger.warning(f"Song with id={id} is not published")
        return None
    
    logger.info(f"Successfully retrieved song: title='{song['title']}', artist='{song['artist']}'")
    return song

async def is_song_published(song_id: str, db=None):
    """
    Check if a song is published (visible to public).
    
    A song is published if:
    - It's not in any collection (standalone), OR
    - It's in at least one published collection, OR
    - It has an early_release_date that has passed
    """
    if db is None:
        db = get_db()
    
    now = datetime.now(timezone.utc)
    
    # Get all collection_songs for this song
    collection_songs = list(db.collection_songs.find(
        {"song_id": ObjectId(song_id)},
        {"collection_id": 1, "early_release_date": 1}
    ))
    
    # Case 1: Song is not in any collection (standalone)
    if not collection_songs:
        return True
    
    # Case 2 & 3: Check if in published collection or has passed early_release_date
    for cs in collection_songs:
        collection = db.collections.find_one(
            {"_id": cs["collection_id"]},
            {"releaseDate": 1}
        )
        
        if collection:
            release_date = collection.get("releaseDate")
            if release_date:
                # Make timezone-aware if needed
                if release_date.tzinfo is None:
                    release_date = release_date.replace(tzinfo=timezone.utc)
                
                # Collection is published
                if release_date <= now:
                    return True
        
        # Check early release
        early_release_date = cs.get("early_release_date")
        if early_release_date:
            # Make timezone-aware if needed
            if early_release_date.tzinfo is None:
                early_release_date = early_release_date.replace(tzinfo=timezone.utc)
            
            if early_release_date <= now:
                return True
    
    return False

async def update_song(existing_song, new_title, new_artist, new_duration):
    db = get_db()
    try:
        old_title = existing_song.get("title")
        old_artist = existing_song.get("artist")
        old_duration = existing_song.get("duration")

        result = db.songs.update_one(
            {"_id": existing_song["_id"]},
            {"$set": {"title": new_title, "artist": new_artist, "duration": new_duration}}
        )

        if result.modified_count > 0:
            logger.info(f"Successfully updated song with id={existing_song['_id']}")
            logger.debug(f"Updated song fields: '{old_title}' -> '{new_title}', '{old_artist}' -> '{new_artist}', '{old_duration}' -> '{new_duration}'")
            updated_song = db.songs.find_one({"_id": existing_song["_id"]})
            return (updated_song, None)
        else:
            logger.warning(f"No song updated with id={existing_song['_id']}")
            return (None, None)
    except Exception as e:
        logger.error(f"Failed to update song with id={existing_song.get('_id')}: {str(e)}")
        return (None, e)

async def delete_song(existing_song):
    db = get_db()
    try:
        result = db.songs.delete_one({"_id": existing_song["_id"]})
        if result.deleted_count > 0:
            logger.info(f"Successfullly deleted song with id={existing_song['_id']}")
        else:
            logger.warning(f"Song with id={existing_song['_id']} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to delete song with id={existing_song['_id']}: {str(e)}")
