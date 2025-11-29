from resources.logger import logger
from db.database import get_db

async def set_user_genres(userId: str, genres: list[str]):
    """
    Save or update the user's genre preferences.
    """
    db = get_db()
    try:
        db.user_preferences.update_one(
            {"userId": userId},
            {"$set": {"genre_preferences": genres}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to set genres for user {userId}: {str(e)}")
        return None


async def set_user_artists(userId: str, artists: list[str]):
    """
    Save or update the user's artist preferences.
    """
    db = get_db()
    try:
        db.user_preferences.update_one(
            {"userId": userId},
            {"$set": {"artist_preferences": artists}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to set artists for user {userId}: {str(e)}")
        return None
    

async def get_user_genres(userId: str):
    db = get_db()
    try:
        doc = db.user_preferences.find_one({"userId": userId}, {"_id": 0, "genre_preferences": 1})
        if doc and "genre_preferences" in doc:
            return doc["genre_preferences"]
        return []
    except Exception as e:
        logger.error(f"Failed to get genre preferences for user {userId}: {e}")
        return None
    

async def get_user_artists(userId: str):
    db = get_db()
    try:
        doc = db.user_preferences.find_one({"userId": userId}, {"_id": 0, "artist_preferences": 1})
        if doc and "artist_preferences" in doc:
            return doc["artist_preferences"]
        return []
    except Exception as e:
        logger.error(f"Failed to get artist preferences for user {userId}: {e}")
        return None

async def get_random_genre():
    db = get_db()
    try:
        pipeline = [
            {"$unwind": "$genre_preferences"},
            {"$sample": {"size": 1}},
            {"$project": {"_id": 0, "genre": "$genre_preferences"}}
        ]
        result = list(db.user_preferences.aggregate(pipeline))
        if result:
            return result[0]["genre"]
        return None
    except Exception as e:
        logger.error(f"Failed to get random genre: {e}")
        return None

async def get_available_genres():
    """
    Get all unique genres from collections in the database.
    Returns a list of genre strings.
    """
    db = get_db()
    try:
        genres = db.collections.distinct("genre")
        # Filter out None and empty strings
        genres = [g for g in genres if g]
        logger.info(f"Found {len(genres)} available genres in database")
        return genres
    except Exception as e:
        logger.error(f"Failed to get available genres: {e}")
        return []