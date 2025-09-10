from sqlalchemy import desc
from datetime import datetime, timezone
from db import models
from resources.logger import logger
from pymongo import DESCENDING

def create_playlist(db, name, description):
    try:
        publish_time = datetime.now(timezone.utc)
        playlist_doc = {
            "name": name,
            "description": description,
            "is_published": True,
            "published_at": publish_time,
        }
        result = db.playlists.insert_one(playlist_doc)
        playlist_doc["id"] = result.inserted_id
        logger.info(f"Successfully created playlist with id={playlist_doc['id']}")
        return (playlist_doc, None)
    except Exception as e:
        logger.error(f"Failed to create playlist: {str(e)}")
        return (None, e)
    
def get_all_playlists(db):
    try:
        playlists = list(
            db.playlists.find({"is_published": True})
            .sort([("published_at", DESCENDING), ("id", DESCENDING)])
        )
        logger.info(f"Retrieved {len(playlists)} published playlists from database")
        return playlists
    except Exception as e:
        logger.error(f"Failed to retrieve playlists: {str(e)}")
        return []

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
    playlist = db.playlists.find_one({"id": id})
    if playlist is None:
        logger.warning(f"Playlist with id={id} not found")
        return None
    logger.info(f"Successfully retrieved Playlist")
    return playlist

def delete_playlist(db, existing_playlist):
    try:
        result = db.playlists.delete_one({"id": existing_playlist["id"]})
        if result.deleted_count > 0:
            logger.info(f"Successfully deleted playlist with id={existing_playlist.id}")
        else:
            logger.warning(f"Playlist with id={id} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to delete playlist with id={existing_playlist.id}: {str(e)}")