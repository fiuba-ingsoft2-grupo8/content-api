from datetime import datetime, timezone

from bson import ObjectId
from pymongo import DESCENDING

from db.database import get_db
from db.models import PlaylistSong
from resources.logger import logger
from auth import is_authorized  # usado en get_playlist (acceso privado)
import random

# ----------------- CRUD y consultas ----------------- #

async def create_playlist(name, description, is_published, userId, coverUrl=None, isLikedSongs=False, isMix=False):
    db = get_db()
    try:
        publish_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        playlist_doc = {
            "name": name,
            "description": description,
            "is_published": is_published,
            "published_at": publish_time,
            "userId": userId,
            "songs": [],
            "coverUrl": coverUrl or "default_cover.png",
            "isLikedSongs": isLikedSongs,
            "isMix": isMix,
        }
        result = db.playlists.insert_one(playlist_doc)
        logger.info(f"Successfully created playlist with id={result.inserted_id}")
        playlist = db.playlists.find_one({"_id": result.inserted_id})
        return (playlist, None)
    except Exception as e:
        logger.error(f"Failed to create playlist: {str(e)}")
        return (None, e)
    
async def create_mix_playlist(name, description, is_published, userId, coverUrl=None, isLikedSongs=False, isMix=True, songs=None):
    db = get_db()
    try:
        publish_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        playlist_doc = {
            "name": name,
            "description": description,
            "is_published": is_published,
            "published_at": publish_time,
            "userId": userId,
            "songs": songs or [],
            "coverUrl": coverUrl or "default_cover.png",
            "isLikedSongs": isLikedSongs,
            "isMix": isMix,
        }
        result = db.playlists.insert_one(playlist_doc)
        logger.info(f"Successfully created mix playlist with id={result.inserted_id}")
        playlist = db.playlists.find_one({"_id": result.inserted_id})
        return (playlist, None)
    except Exception as e:
        logger.error(f"Failed to create mix playlist: {str(e)}")
        return (None, e)


async def get_playlists(published: bool, userId: str = None, state: str = "", published_from=None, published_to=None):
    """
    Filtros:
    - published (bool): mantener compatibilidad existente
    - state: "publicado" / "programado" (case-insensitive)
    - published_from/published_to: rango sobre published_at (aplica cuando is_published=True)
    """
    db = get_db()

    try:
        query = {}
        # compatibilidad: si viene published=True, forzamos is_published=True
        if published:
            query["is_published"] = True

        # por user (cuando no es backoffice)
        if userId:
            query["userId"] = userId

        st = (state or "").strip().lower()
        if st == "publicado":
            query["is_published"] = True
        elif st == "programado":
            query["is_published"] = False

        # Rango de fechas sobre published_at sólo si filtramos publicados
        if query.get("is_published") is True and (published_from or published_to):
            range_q = {}
            if published_from:
                range_q["$gte"] = published_from
            if published_to:
                range_q["$lte"] = published_to
            query["published_at"] = range_q

        # No traigo los mixes del inicio
        query["isMix"] = False

        playlists = list(
            db.playlists.find(query)
            .sort([("published_at", DESCENDING), ("_id", DESCENDING)])
        )
        logger.info(f"Retrieved {len(playlists)} playlists from database")
        return playlists
    except Exception as e:
        logger.error(f"Failed to retrieve playlists: {str(e)}")
        return []


async def get_playlist(id, user: dict = None):
    """
    Get a playlist by ID. Respeta las reglas de acceso:
    - Publicadas: accesibles
    - Privadas: sólo dueño o backoffice
    """
    db = get_db()
    try:
        playlist = db.playlists.find_one({"_id": ObjectId(id)})
        if playlist is None:
            logger.warning(f"Playlist with id={id} not found")
            return None

        # Si está publicada, devolverla
        if bool(playlist.get("is_published", False)):
            logger.info(f"Successfully retrieved playlist '{playlist['name']}' (published)")
            return playlist

        # Es privada: sólo backoffice o dueño
        if isinstance(user, dict):
            if user.get("user_type") == "backoffice":
                logger.info(f"Backoffice access to private playlist id={id}")
                return playlist
            if str(playlist.get("userId")) == str(user.get("user_id")):
                logger.info(f"Owner access to private playlist id={id}")
                return playlist

        logger.warning(f"Access denied to private playlist id={id} for user={user}")
        return None
    except Exception as e:
        logger.error(f"Failed to get playlist with id={id}: {str(e)}")
        return None


async def add_song_to_playlist(song_id: str, playlist_id: str) -> bool:
    db = get_db()
    song_oid = ObjectId(song_id)
    playlist_oid = ObjectId(playlist_id)

    last_song = db.playlist_songs.find_one(
        {"playlist_id": playlist_oid},
        sort=[("order", -1)],
        projection={"order": 1}
    )

    next_pos = (last_song["order"] + 1) if last_song and "order" in last_song else 1

    playlist_song = PlaylistSong(song_id=song_oid, playlist_id=playlist_oid, order=next_pos)
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
        {"song_id": 1, "added_at": 1, "order": 1}
    ).sort("order", 1))

    if not playlist_songs:
        return []

    song_ids = [ps["song_id"] for ps in playlist_songs]
    if not song_ids:
        return []

    songs = list(db.songs.find({"_id": {"$in": song_ids}}))
    song_map = {song["_id"]: song for song in songs}
    return [
        {**song_map[ps["song_id"]], "added_at": ps["added_at"], "order": ps.get("order", 1)}
        for ps in playlist_songs
        if ps["song_id"] in song_map
    ]


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


async def change_playlist_state(existing_playlist, state):
    """
    Change the published state of a playlist.
    When publishing (state=True), updates published_at to current server time.
    """
    db = get_db()
    update_fields = {"is_published": state}
    
    # When publishing, update the published_at timestamp to current server time
    if state:
        update_fields["published_at"] = datetime.now(timezone.utc)
    
    result = db.playlists.update_one(
        {"_id": existing_playlist["_id"]},
        {"$set": update_fields}
    )
    return result.modified_count > 0


async def update_playlist_cover(existing_playlist: str, cover_url: str):
    db = get_db()
    result = db.playlists.update_one(
        {"_id": existing_playlist["_id"]},
        {"$set": {"coverUrl": cover_url}}
    )
    return result.modified_count > 0


async def playlist_belongs_to_user(playlist_id, userId):
    db = get_db()
    try:
        found = db.playlists.find_one({"_id": ObjectId(playlist_id), "userId": userId})
        return bool(found)
    except Exception:
        return False


async def get_liked_songs_playlist(userId):
    db = get_db()
    try:
        playlist = db.playlists.find_one({"userId": userId, "isLikedSongs": True})
        if playlist is None:
            logger.warning(f"Liked songs for user{userId} not found")
            return None
        logger.info(f"Successfully retrieved liked songs for user{userId}")
        return playlist
    except Exception as e:
        logger.error(f"Failed to get liked songs for user{userId}: {str(e)}")
        return None


# -------- develop: reordenar canciones --------
async def reorder_songs_in_playlist(playlist_id: str, songs: list[dict]) -> bool:
    """
    Espera una lista con elementos que provean .songId y .order
    (si viene como dict, soportamos ambas notaciones).
    """
    db = get_db()
    playlist_oid = ObjectId(playlist_id)

    try:
        for item in songs:
            # soporta pydantic item.songId o dict["songId"]
            song_id = getattr(item, "songId", None) or item.get("songId")
            order = getattr(item, "order", None) or item.get("order")
            if not song_id:
                continue
            db.playlist_songs.update_one(
                {"playlist_id": playlist_oid, "song_id": ObjectId(song_id)},
                {"$set": {"order": int(order) if order is not None else 0}}
            )
        logger.info(f"Updated order for {len(songs)} songs in playlist {playlist_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to reorder songs in playlist {playlist_id}: {str(e)}")
        return False


# -------- feature: actualizar descripción --------
async def update_playlist_description(playlist_id: str, description: str) -> bool:
    db = get_db()
    try:
        oid = ObjectId(playlist_id) if isinstance(playlist_id, str) else playlist_id
        res = db.playlists.update_one({"_id": oid}, {"$set": {"description": description}})
        return res.modified_count > 0
    except Exception as e:
        logger.error(f"Failed to update description for playlist {playlist_id}: {e}")
        return False



async def get_random_playlists(limit: int = 5):
    db = get_db()
    playlists = list(
        db.playlists.find({"is_published": True})
        .sort([("_id", 1)])
    )
    if not playlists:
        return []
    return random.sample(playlists, min(limit, len(playlists)))


async def get_or_create_mix_playlist(user_id: str, name: str, songs: list):
    db = get_db()

    playlist = db.playlists.find_one({"userId": user_id, "name": name})
    if playlist:
        return playlist
    
    if name == "Daily Mix":
        cover_url = "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/liked-songs/daily-mix.png"
    elif name == "Mood Mix":
        cover_url = "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/discover-mix/discover-mix.png"
    elif name == "Because You Listened To":
        cover_url = "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/liked-songs/because-you-listened-to.png"
    else:
        raise ValueError(f"Unknown mix type: {name}")
    
    playlist_doc, err = await create_mix_playlist(
        name=name,
        description="",
        is_published=True,
        userId=user_id,
        coverUrl="https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/liked-songs/liked-songs.png",
        isLikedSongs=False,
        isMix=True,
        songs=songs
    )
    return playlist_doc
