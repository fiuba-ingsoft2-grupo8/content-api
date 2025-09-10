from db import models
from resources.logger import logger

def create_song(db, title, artist):
    try:
        db_song = {"title": title, "artist": artist}
        result = db.songs.insert_one(db_song)
        db_song["id"] = result.inserted_id
        logger.info(f"Successfully created song with id={db_song['id']}")
        return (db_song, None)
    except Exception as e:
        logger.error(f"Failed to create song: {str(e)}")
        return (None, e)
    
def get_all_songs(db):
    try:
        songs = list(db.songs.find())
        logger.info(f"Retrieved {len(songs)} songs from database")
        return songs
    except Exception as e:
        logger.error(f"Failed to retrieve songs: {str(e)}")
        return []

def get_song(db, id):
    song = db.songs.find_one({"id": id})
    if song is None:
        logger.warning(f"Song with id={id} not found")
        return None
    logger.info(f"Successfully retrieved song: title='{song['title']}', artist='{song['artist']}'")
    return song

def update_song(db, existing_song, new_title, new_artist):
    try:
        old_title = existing_song.get("title")
        old_artist = existing_song.get("artist")

        result = db.songs.update_one(
            {"id": existing_song["id"]},
            {"$set": {"title": new_title, "artist": new_artist}}
        )

        if result.modified_count > 0:
            logger.info(f"Successfully updated song with id={existing_song.id}")
            logger.debug(f"Updated song fields: '{old_title}' -> '{new_title}', '{old_artist}' -> '{new_artist}'")
            updated_song = db.songs.find_one({"id": existing_song["id"]})
            return (updated_song, None)
        else:
            logger.warning(f"No song updated with id={existing_song['_id']}")
            return (None, None)
    except Exception as e:
        logger.error(f"Failed to update song with id={existing_song.get('_id')}: {str(e)}")
        return (None, e)

def delete_song(db, existing_song):
    try:
        result = db.songs.delete_one({"id": existing_song["id"]})
        if result.deleted_count > 0:
            logger.info(f"Successfully deleted song with id={existing_song.id}")
        else:
            logger.warning(f"Song with id={id} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to delete song with id={existing_song.id}: {str(e)}")
