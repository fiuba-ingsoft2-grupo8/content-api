
from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
import httpx
from auth import verify_token
from resources.logger import logger
import os
from bson import ObjectId

import databases.songs_database as songs_db
import databases.metrics_database as metrics_db
import databases.collections_database as collections_db
import databases.playlists_database as playlists_db
from common.utils import serialize_collection, serialize_playlist, serialize_song
import databases.preferences_database as preferences_db
from db.database import get_db

router = APIRouter()
USER_API_BASE = os.getenv("USER_API_BASE", "http://host.docker.internal:8081")


async def _filter_songs_by_geography(user: dict, songs: list, db=None) -> list:
    """
    Filter songs based on geographical restrictions of their collections.
    
    A song is accessible if:
    - User is backoffice
    - User is the owner of the song
    - Song is not in any collection (standalone - available everywhere)
    - Song is in at least one collection available in user's country
    
    Args:
        user: User dictionary from verify_token
        songs: List of song documents
        db: Database instance (optional, will use get_db() if not provided)
        
    Returns:
        list: Filtered list of accessible songs
    """
    # Backoffice users can access all songs
    if user.get("user_type") == "backoffice":
        return songs
    
    if db is None:
        db = get_db()
    
    accessible_songs = []
    user_country = user.get("country", "")
    
    for song in songs:
        song_id = song.get("_id")
        
        # Check if user owns the song
        if song.get("artistId") == user.get("user_id"):
            accessible_songs.append(song)
            continue
        
        # Get collections this song belongs to
        collection_songs = list(db.collection_songs.find(
            {"song_id": ObjectId(song_id)},
            {"collection_id": 1}
        ))
        
        # If song is not in any collection (standalone), it's available everywhere
        if not collection_songs:
            accessible_songs.append(song)
            continue
        
        # Check if song is in at least one collection available in user's country
        collection_ids = [cs["collection_id"] for cs in collection_songs]
        
        collections = list(db.collections.find(
            {"_id": {"$in": collection_ids}},
            {"availableCountries": 1}
        ))
        
        is_accessible = False
        for collection in collections:
            available_countries = collection.get("availableCountries", [])
            
            # If collection has no restrictions, song is accessible
            if not available_countries:
                is_accessible = True
                break
            
            # If user's country is in the available countries, song is accessible
            if user_country in available_countries:
                is_accessible = True
                break
        
        if is_accessible:
            accessible_songs.append(song)
    
    return accessible_songs

@router.get("/daily-mix")
async def get_daily_mix(user: dict = Depends(verify_token)):
    try:
        user_id = user["user_id"]
        user_genres = await preferences_db.get_user_genres(user_id)
        
        # Get available genres from database as fallback
        available_genres = await preferences_db.get_available_genres()
        fallback_genres = available_genres if available_genres else ["pop", "rock", "hip-hop", "electronic"]
        
        genres_to_try = [user_genres] if user_genres else []
        genres_to_try.extend(fallback_genres)
        
        songs = []
        for genre in genres_to_try:
            if genre:
                songs = await songs_db.get_songs_by_genre(genre, limit=10)
                if songs:
                    logger.info(f"Found {len(songs)} songs for genre '{genre}'")
                    break
        
        # Filter songs based on geographical restrictions
        filtered_songs = await _filter_songs_by_geography(user, songs)
        logger.info(f"Filtered {len(songs)} songs to {len(filtered_songs)} available in user's country")
        
        playlist = await playlists_db.get_or_create_mix_playlist(user_id, "Daily Mix", filtered_songs)
        return { "data": serialize_playlist(playlist, filtered_songs) }

    except Exception as e:
        logger.error(f"Failed to fetch Daily Mix: {str(e)}")
        raise


@router.get("/mood-mix")
async def get_mood_mix(user: dict = Depends(verify_token)):
    try:
        user_id = user["user_id"]
        playlist_genre = await preferences_db.get_random_genre()
        
        # Get available genres from database as fallback
        available_genres = await preferences_db.get_available_genres()
        fallback_genres = available_genres if available_genres else ["pop", "rock", "hip-hop", "electronic"]
        
        genres_to_try = [playlist_genre] if playlist_genre else []
        genres_to_try.extend(fallback_genres)
        
        songs = []
        for genre in genres_to_try:
            if genre:
                songs = await songs_db.get_songs_by_genre(genre, limit=10)
                if songs:
                    logger.info(f"Found {len(songs)} songs for genre '{genre}'")
                    break
        
        # Filter songs based on geographical restrictions
        filtered_songs = await _filter_songs_by_geography(user, songs)
        logger.info(f"Filtered {len(songs)} songs to {len(filtered_songs)} available in user's country")
        
        playlist = await playlists_db.get_or_create_mix_playlist(user_id, "Mood Mix", filtered_songs)
        return { "data": serialize_playlist(playlist, filtered_songs) }

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
            genre_songs = await songs_db.get_songs_by_genre(genre or "pop", limit=10)
            if genre_songs:
                songs.extend(genre_songs)
        
        # If no songs found from artist genres, try fallback genres
        if not songs:
            # Get available genres from database as fallback
            available_genres = await preferences_db.get_available_genres()
            fallback_genres = available_genres if available_genres else ["pop", "rock", "hip-hop", "electronic"]
            
            for genre in fallback_genres:
                genre_songs = await songs_db.get_songs_by_genre(genre, limit=10)
                if genre_songs:
                    logger.info(f"Found {len(genre_songs)} songs for fallback genre '{genre}'")
                    songs = genre_songs
                    break

        # Filter songs based on geographical restrictions
        filtered_songs = await _filter_songs_by_geography(user, songs)
        logger.info(f"Filtered {len(songs)} songs to {len(filtered_songs)} available in user's country")

        playlist = await playlists_db.get_or_create_mix_playlist(user_id, "Because You Listened To", filtered_songs)
        return { "data": serialize_playlist(playlist, filtered_songs) }

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
        timeout = httpx.Timeout(30.0, connect=10.0)

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
        serialized_collections = []
        for col in collections:
            songs = await collections_db.get_songs_from_collection(col["_id"])
            serialized_collections.append(serialize_collection(col, songs))
        
        return {
            "data": serialized_collections
        }

    except Exception as e:
        logger.error(f"Failed to get new releases: {type(e).__name__}: {str(e)}", exc_info=True)
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
            logger.info(f"No artist found")
            return {"collections": []}

        # Obtener colecciones del artista (solo publicadas si includeUnpublished=False)
        artist_collections = await collections_db.get_collections(
            artistId=artist_id,        
            includeUnpublished=False   
        )

        genres = set()
        if len(artist_collections) == 0:
            logger.info(f"No collections found by artist")
        for collection in artist_collections:
            genre = collection["genre"]
            if genre:
                genres.add(genre)
        
        genre_collections = []
        for genre in genres:
            logger.info(f"Artist {artist_id} has collection in genre: {genre}")
            genre_collections_to_add = await collections_db.get_collections(genre=genre)
            logger.info("0\n")
            for collection in genre_collections_to_add:
                logger.info(f"{collection}")
            genre_collections.extend(genre_collections_to_add)

        serialized_collections = []
        for collection in genre_collections:
            songs = await collections_db.get_songs_from_collection(collection["_id"])
            logger.info("1\n")
            serialized_collections.append(serialize_collection(collection, songs))
        
        logger.info(f"serialized collections: {serialized_collections}")
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
                song = await songs_db.get_song(play["song_id"])
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

@router.get("/similar-artists")
async def get_similar_artists(
    user: dict = Depends(verify_token),
    artist_id: str = None
):
    try:
        if not artist_id:
            return {"artists": []}

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

        similar_artists = set()
        for genre in genres:
            logger.info(f"Artist {artist_id} has collection in genre: {genre}")
            collections = await collections_db.get_collections(genre=genre, includeUnpublished=False)
            # Ya vienen ordenadas por fecha de publicación descendente
            for col in collections:
                if col.get("artistId") and col.get("artistId") != artist_id:
                    similar_artists.add(col.get("artistId"))


        return {
            "artists": similar_artists,
            "count": len(similar_artists)
        }

    except Exception as e:
        logger.error(f"Failed to get similar artists: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch similar artists"}
        )