from resources.logger import logger
from db.database import get_db
from bson import ObjectId
from datetime import datetime

async def create_song(title, artist):
    db = get_db()
    try:
        db_song = {"title": title, "artist": artist}
        result = db.songs.insert_one(db_song)
        logger.info(f"Successfully created song with id={result.inserted_id}")
        song = db.songs.find_one({ "_id": result.inserted_id })
        return (song, None)
    except Exception as e:
        logger.error(f"Failed to create song: {str(e)}")
        return (None, e)
    
async def get_all_songs():
    db = get_db()
    try:
        songs = list(db.songs.find())
        logger.info(f"Retrieved {len(songs)} songs from database")
        return songs
    except Exception as e:
        logger.error(f"Failed to retrieve songs: {str(e)}")
        return []

async def get_song(id):
    db = get_db()
    song = db.songs.find_one({"_id": ObjectId(id)})
    if song is None:
        logger.warning(f"Song with id={id} not found")
        return None
    logger.info(f"Successfully retrieved song: title='{song['title']}', artist='{song['artist']}'")
    return song

async def update_song(existing_song, new_title, new_artist):
    db = get_db()
    try:
        old_title = existing_song.get("title")
        old_artist = existing_song.get("artist")

        result = db.songs.update_one(
            {"_id": existing_song["_id"]},
            {"$set": {"title": new_title, "artist": new_artist}}
        )

        if result.modified_count > 0:
            logger.info(f"Successfully updated song with id={existing_song['_id']}")
            logger.debug(f"Updated song fields: '{old_title}' -> '{new_title}', '{old_artist}' -> '{new_artist}'")
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

async def add_to_history(songId, userId):
    db = get_db()
    try:
        result = db.history.insert_one({"userId": userId, "songId": songId, "playedAt": datetime.now()})
        return None
    except Exception as e:
        return e

async def get_user_history(userId):
    db = get_db()