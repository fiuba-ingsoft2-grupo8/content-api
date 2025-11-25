
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from auth import verify_token
from resources.logger import logger

import databases.songs_database as songs_db
import databases.collections_database as collections_db
import databases.playlists_database as playlists_db
from common.utils import serialize_collection, serialize_playlist, serialize_song

router = APIRouter()

@router.get("/daily-mix")
async def get_daily_mix(user: dict = Depends(verify_token)):
    try:
        songs = await songs_db.get_random_songs()
        return { "data": [serialize_song(song) for song in songs] }
    except Exception as e:
        logger.error(f"Failed to fetch songs: {str(e)}")
        raise


@router.get("/mood-mix")
async def get_mood_mix(user: dict = Depends(verify_token)):
    try:
        songs = await songs_db.get_random_songs()
        return { "data": [serialize_song(song) for song in songs] }
    except Exception as e:
        logger.error(f"Failed to fetch songs: {str(e)}")
        raise


@router.get("/because-you-listened")
async def get_because_you_listened_to(user: dict = Depends(verify_token)):
    try:
        songs = await songs_db.get_random_songs()
        return { "data": [serialize_song(song) for song in songs] }
    except Exception as e:
        logger.error(f"Failed to fetch songs: {str(e)}")
        raise


@router.get("/new-releases")
async def get_new_releases(user: dict = Depends(verify_token)):
    try:
        logger.info("Fetching New Release (mock)")

        collections = await collections_db.get_random_collections(limit=5)
        serialized_collections = []
        for collection in collections:
            songs = await collections_db.get_songs_from_collection(collection["_id"])
            serialized_collections.append(serialize_collection(collection, songs))

        return {
            "data": serialized_collections
        }

    except Exception as e:
        logger.error(f"Failed to get new releases: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch new releases"}
        )


@router.get("/discover-more")
async def get_discover_more_from_artist(user: dict = Depends(verify_token)):
    try:
        user_id = user["user_id"]
        logger.info(f"Fetching Discover More section for user {user_id}")

        # mock: random public playlists
        playlists = await playlists_db.get_random_playlists(limit=5)
        serialized_playlists = []
        for playlist in playlists:
            songs = await playlists_db.get_songs_from_playlist(playlist["_id"])
            serialized_playlists.append(serialize_playlist(playlist, songs))

        # mock: random public collections
        collections = await collections_db.get_random_collections(limit=5)
        serialized_collections = []
        for collection in collections:
            songs = await collections_db.get_songs_from_collection(collection["_id"])
            serialized_collections.append(serialize_collection(collection, songs))

        return {
            "playlists": serialized_playlists,
            "collections": serialized_collections,
        }

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

        # mock: random public playlists
        playlists = await playlists_db.get_random_playlists(limit=5)
        serialized_playlists = []
        for playlist in playlists:
            songs = await playlists_db.get_songs_from_playlist(playlist["_id"])
            serialized_playlists.append(serialize_playlist(playlist, songs))

        # mock: random public collections
        collections = await collections_db.get_random_collections(limit=5)
        serialized_collections = []
        for collection in collections:
            songs = await collections_db.get_songs_from_collection(collection["_id"])
            serialized_collections.append(serialize_collection(collection, songs))

        return {
            "playlists": serialized_playlists,
            "collections": serialized_collections,
        }

    except Exception as e:
        logger.error(f"Failed to fetch discover-more section: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch discover-more section"}
        )
