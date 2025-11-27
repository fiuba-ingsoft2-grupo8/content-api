
from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
import httpx
from auth import verify_token
from resources.logger import logger
import os

import databases.songs_database as songs_db
import databases.metrics_database as metrics_db
import databases.collections_database as collections_db
import databases.playlists_database as playlists_db
from common.utils import serialize_collection, serialize_playlist, serialize_song
import databases.preferences_database as preferences_db
router = APIRouter()
USER_API_BASE = os.getenv("USER_API_BASE", "http://host.docker.internal:8081")

@router.get("/daily-mix")
async def get_daily_mix(user: dict = Depends(verify_token)):
    try:
        user_id = user["user_id"]
        user_genres = await preferences_db.get_user_genres(user_id)
        songs = await songs_db.get_songs_by_genre(user_genres or "pop", limit=10)
        playlist = await playlists_db.get_or_create_mix_playlist(user_id, "Daily Mix", songs)
        return { "data": serialize_playlist(playlist, []) }

    except Exception as e:
        logger.error(f"Failed to fetch Daily Mix: {str(e)}")
        raise


@router.get("/mood-mix")
async def get_mood_mix(user: dict = Depends(verify_token)):
    try:
        
        user_id = user["user_id"]
        playlist_genre = await preferences_db.get_random_genre()
        songs = await songs_db.get_songs_by_genre(playlist_genre or "pop", limit=10)
        playlist = await playlists_db.get_or_create_mix_playlist(user_id, "Mood Mix", songs)
        return { "data": serialize_playlist(playlist, []) }

    except Exception as e:
        logger.error(f"Failed to fetch Mood Mix: {str(e)}")
        raise


@router.get("/because-you-listened")
async def get_because_you_listened_to(user: dict = Depends(verify_token)):
    try:
        user_id = user["user_id"]
        user_top_play = await metrics_db.get_user_top_n_plays(user_id, n=1)
        top_artist = user_top_play[0].get("artist") if user_top_play else None
    

        # Obtener colecciones del artista (solo publicadas si includeUnpublished=False)
        artist_collections = await collections_db.get_collections(
            artistId=top_artist,        
            includeUnpublished=False   
        )

        genres = set()
        for collection in artist_collections:
            genre = collection.get("genre")
            if genre:
                genres.add(genre)
    
        songs = []
        for genre in genres:
            logger.info(f"Top artist {top_artist} has collection in genre: {genre}")
            songs = await songs_db.get_songs_by_genre(genre or "pop", limit=10)
            songs.extend(songs)

        playlist = await playlists_db.get_or_create_mix_playlist(user_id, "Because You Listened To", songs)
        return { "data": serialize_playlist(playlist, []) }

    except Exception as e:
        logger.error(f"Failed to fetch BYL Mix: {str(e)}")
        raise


@router.get("/new-releases")
async def get_new_releases(user: dict = Depends(verify_token), authorization: str = Header(None)):
    try:
        logger.info("Fetching New Release (mock)")

        # Endpoint real del User API → OJO: sin "/users/"
        url = f"{USER_API_BASE}/followingArtists"

        headers = {}
        if authorization:
            headers["Authorization"] = authorization

        # timeouts: 5s connect, 20s total lectura
        timeout = httpx.Timeout(20.0, connect=5.0)

        followed_artists = []

        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"User API base: {USER_API_BASE}")
            logger.info(f"Calling: {USER_API_BASE.rstrip('/')}/followingArtists (token: {bool(authorization)})")

            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

            data = resp.json()

            items = (
                data.get("users")
                or data.get("following")
                or data.get("result")
                or []
            )

            followed_artists = [{"id": u.get("id")} for u in items if u.get("id")]

        logger.info(f"User {user['user_id']} follows {len(followed_artists)} artists")

        # Buscar lanzamientos recientes de cada artista seguido
        collections = []
        for artist in followed_artists:
            artist_collections = await collections_db.get_new_releases_from_artist(artist["id"])
            collections.extend(artist_collections)

        # Serializar colecciones
        return {
            "data": [
                serialize_collection(col, await collections_db.get_songs_from_collection(col["_id"]))
                for col in collections
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get new releases: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch new releases"}
        )
    
    
@router.get("/discover-more")
async def get_discover_more_from_artist(
    user: dict = Depends(verify_token),
    artist_id: str = None
):
    try:
        if not artist_id:
            return {"collections": []}

        # Obtener colecciones del artista (solo publicadas si includeUnpublished=False)
        artist_collections = await collections_db.get_collections(
            artistId=artist_id,        
            includeUnpublished=False   
        )

        genres = set()
        for collection in artist_collections:
            genre = collection.get("genre")
            if genre:
                genres.add(genre)
        
        genre_collections = []
        for genre in genres:
            logger.info(f"Artist {artist_id} has collection in genre: {genre}")
            genre_collections_to_add = await collections_db.get_public_collections_by_genre(genre, limit=5)
            genre_collections.extend(genre_collections_to_add)

        serialized_collections = []
        for collection in genre_collections:
            songs = await collections_db.get_songs_from_collection(collection["_id"])
            serialized_collections.append(serialize_collection(collection, songs))
        
        return {"collections": serialized_collections}

    except Exception as e:
        logger.error(f"Failed to fetch discover-more section: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch discover-more section"}
        )


@router.get("/shortcuts")
async def get_shortcuts(user: dict = Depends(verify_token)):
    try:
        user_id = user["user_id"]
        logger.info(f"Fetching Discover More section for user {user_id}")


        user_top_plays = await metrics_db.get_user_top_n_plays(user_id, n=5)

        if user_top_plays:
            playlists = []
            collections = []
            for play in user_top_plays:
                song = await songs_db.get_song_by_id(play["song_id"])
                if not song:
                    continue

                # Get a playlist from the song's artist
                artist_playlists = await playlists_db.get_public_playlists_by_artist(song["artist"])
                if artist_playlists:
                    pl = artist_playlists[0]
                    pl_songs = await playlists_db.get_songs_from_playlist(pl["_id"])
                    playlists.append(serialize_playlist(pl, pl_songs))

                # Get a collection from the song's album
                album_collections = await collections_db.get_public_collections_by_album(song["album"])
                if album_collections:
                    col = album_collections[0]
                    col_songs = await collections_db.get_songs_from_collection(col["_id"])
                    collections.append(serialize_collection(col, col_songs))

            return {
                "playlists": playlists,
                "collections": collections,
            }

    except Exception as e:
        logger.error(f"Failed to fetch discover-more section: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch discover-more section"}
        )

