from sqlalchemy import desc
from datetime import datetime, timezone
from db import models
from resources.logger import logger

def create_playlist(db, name, description):
    try:
        publish_time = datetime.now(timezone.utc)
        db_playlist = models.Playlist(
            name=name,
            description=description,
            is_published=True,
            published_at=publish_time,
        )
        logger.debug(f"Created playlist model with published_at={publish_time}")
        db.add(db_playlist)
        logger.debug("Added playlist to database session")
        db.commit()
        logger.debug("Committed playlist to database")
        db.refresh(db_playlist)
        logger.info(f"Successfully created playlist with id={db_playlist.id}")

        return (db_playlist, None)
    except Exception as e:
        db.rollback()
        return (None, e)
    
def get_all_playlists(db):
    playlists = (
        db.query(models.Playlist)
        .filter(models.Playlist.is_published == True)
        .order_by(desc(models.Playlist.published_at), desc(models.Playlist.id))
        .all()
    )
    logger.info(f"Retrieved {len(playlists)} published playlists from database")
    return playlists

def add_song_to_playlist(db, song_id, playlist_id):
    try:
        playlist_song = models.PlaylistSong(
            song_id= song_id,
            playlist_id= playlist_id
        )
        db.add(playlist_song)
        db.commit()
        db.refresh(playlist_song)
        logger.info(f"Successfully added song {song_id} to playlist {playlist_id}")
        
        return playlist_song
    except:
        db.rollback()

        return None

def get_playlist(db, id):
    playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
    if playlist is None:
        logger.warning(f"Playlist with id={id} not found")
        return None
    logger.info(f"Successfully retrieved Playlist")
    return playlist

def delete_playlist(db, existing_playlist):
    try:
        db.delete(existing_playlist)
        logger.debug("Marked playlist for deletion")
        db.commit()
        logger.info(f"Successfully deleted playlist with id={existing_playlist.id}")
        return None
    except Exception as e:
        logger.error(f"Failed to delete playlist with id={existing_playlist.id}: {str(e)}")
        db.rollback()
        logger.debug("Database transaction rolled back")
        return None