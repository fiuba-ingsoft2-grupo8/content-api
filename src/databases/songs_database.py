from db import models
from resources.logger import logger

def create_song(db, title, artist):
    try:
        db_song = models.Song(title=title, artist=artist)
        logger.debug(f"Created song model: {db_song}")
        db.add(db_song)
        logger.debug("Added song to database session")
        db.commit()
        logger.debug("Committed song to database")
        db.refresh(db_song)
        logger.info(f"Successfully created song with id={db_song.id}")
        return (db_song, None)
    except Exception as e:
        db.rollback()
        return (None, e)
    
def get_all_songs(db):
    songs = db.query(models.Song).all()
    logger.info(f"Retrieved {len(songs)} songs from database")
    return songs

def get_song(db, id):
    song = db.query(models.Song).filter(models.Song.id == id).first()
    if song is None:
        logger.warning(f"Song with id={id} not found")
        return None
    logger.info(f"Successfully retrieved song: title='{song.title}', artist='{song.artist}'")
    return song

def update_song(db, existing_song, new_title, new_artist):
    try:
        old_title, old_artist = existing_song.title, existing_song.artist
        existing_song.title = new_title
        existing_song.artist = new_artist
        logger.debug(f"Updated song fields: '{old_title}' -> '{new_title}', '{old_artist}' -> '{new_artist}'")
        db.commit()
        logger.debug("Committed song update to database")
        db.refresh(existing_song)
        logger.info(f"Successfully updated song with id={existing_song.id}")
        return (existing_song, None)
    except Exception as e:
        db.rollback()
        return (None, e)

def delete_song(db, existing_song):
    try:
        db.delete(existing_song)
        logger.debug("Marked song for deletion")
        db.commit()
        logger.info(f"Successfully deleted song with id={existing_song.id}")
        return None
    except Exception as e:
        logger.error(f"Failed to delete song with id={existing_song.id}: {str(e)}")
        db.rollback()
        logger.debug("Database transaction rolled back")
        return None