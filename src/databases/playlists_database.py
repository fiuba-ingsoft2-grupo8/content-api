from datetime import datetime, timezone
from resources.logger import logger
from pymongo import DESCENDING
from db.database import get_db
from db.models import PlaylistSong
from bson import ObjectId

async def create_playlist(name, description):
    db = get_db()
    try:
        publish_time = datetime.now(timezone.utc)
        playlist_doc = {
            "name": name,
            "description": description,
            "is_published": False,
            "published_at": publish_time,
            "songs": []
        }
        result = db.playlists.insert_one(playlist_doc)
        logger.info(f"Successfully created playlist with id={result.inserted_id}")
        playlist = db.playlists.find_one({"_id": result.inserted_id})
        return (playlist, None)
    except Exception as e:
        logger.error(f"Failed to create playlist: {str(e)}")
        return (None, e)
    
async def get_playlists(published: bool):
    db = get_db()
    try:
        if published:
            playlists = list(
                db.playlists.find({"is_published": True})
                .sort([("published_at", DESCENDING), ("_id", DESCENDING)])
            )
        else:
            playlists = list(
                db.playlists.find()
                .sort([("published_at", DESCENDING), ("_id", DESCENDING)])
            )
        logger.info(f"Retrieved {len(playlists)} playlists from database")
        return playlists
    except Exception as e:
        logger.error(f"Failed to retrieve playlists: {str(e)}")
        return []

async def add_song_to_playlist(song_id: str, playlist_id: str) -> bool:
    db = get_db()
    song_oid = ObjectId(song_id)
    playlist_oid = ObjectId(playlist_id)

    playlist_song = PlaylistSong(song_id=song_oid, playlist_id=playlist_oid)
    db.playlist_songs.insert_one(playlist_song.model_dump(by_alias=True))
    logger.info(f"Added song {song_id} to playlist {playlist_id}")
    return True

async def remove_song_from_playlist(song_id: str, playlist_id: str) -> bool:
    db = get_db()

    song_oid = ObjectId(song_id)
    playlist_oid = ObjectId(playlist_id)

    result = db.playlist_songs.delete_one({
            "song_id": song_oid,
            "playlist_id": playlist_oid
        })

    if result.deleted_count > 0:
        logger.info(f"Removed song {song_id} from playlist {playlist_id}")
        return True
    else:
        logger.warning(f"Song {song_id} not found in playlist {playlist_id}")
        return False

async def get_songs_from_playlist(playlist_id: str):
    db = get_db()

    playlist_songs = list(db.playlist_songs.find(
        {"playlist_id": ObjectId(playlist_id)},
        {"song_id": 1, "added_at": 1} 
    ))

    if not playlist_songs:
        return []

    song_ids = [ps["song_id"] for ps in playlist_songs]
    if not song_ids:
        return []

    songs = list(db.songs.find({"_id": {"$in": song_ids}}))
    song_map = {song["_id"]: song for song in songs}
    return [
        {**song_map[ps["song_id"]], "added_at": ps["added_at"]}
        for ps in playlist_songs
        if ps["song_id"] in song_map
    ]

async def get_playlist(id):
    db = get_db()
    try:
        playlist = db.playlists.find_one({"_id": ObjectId(id)})
        if playlist is None:
            logger.warning(f"Playlist with id={id} not found")
            return None
        logger.info(f"Successfully retrieved playlist '{playlist['name']}'")
        return playlist
    except Exception as e:
        logger.error(f"Failed to get playlist with id={id}: {str(e)}")
        return None

async def delete_playlist(existing_playlist):
    db = get_db()
    try:
        result = db.playlists.delete_one({"_id": existing_playlist["_id"]})
        if result.deleted_count > 0:
            logger.info(f"Successfully deleted playlist with id={existing_playlist['_id']}")
        else:
            logger.warning(f"Playlist with id={existing_playlist['_id']} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to delete playlist with id={existing_playlist['_id']}: {str(e)}")

async def change_playlist_state(existing_playist, state):
    db = get_db()
    result = db.playlists.update_one(
        {"_id": existing_playist["_id"]},
        {"$set": {"is_published": state}}
    )
    return result.modified_count > 0