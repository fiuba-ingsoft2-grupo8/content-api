from resources.logger import logger
from db.database import get_db
from bson import ObjectId
from datetime import datetime

async def add_to_history(songId, userId):
    db = get_db()
    try:
        existing = db.history.find_one({"songId": ObjectId(songId), "userId": userId})
        if existing:
            db.history.update_one(
                {"userId": userId, "songId": ObjectId(songId)},
                {"$set": {"playedAt": datetime.now(), "progress": 0}}
            )
        else:
            db.history.insert_one({
                "songId": ObjectId(songId),
                "userId": userId,
                "playedAt": datetime.now(),
                "progress": 0
            })

        return None
    except Exception as e:
        return e

async def get_user_history(userId, search=None):
    db = get_db()
    try:
        query = {"userId": userId}
        if search:
            matching_songs = list(db.songs.find({
                "$or": [
                    {"title": {"$regex": search, "$options": "i"}},
                    {"artist": {"$regex": search, "$options": "i"}}
                ]
            }, {"_id": 1}))

            song_ids = [str(s["_id"]) for s in matching_songs]
            query["songId"] = {"$in": song_ids}

        records = list(
            db.history.find(query).sort("playedAt", -1)
        )

        logger.info(f"Found {len(records)} history entries for user {userId}")
        return records
    except Exception as e:
        logger.error(f"Failed to fetch history for user {userId}: {str(e)}")
        return []

async def update_history_progress(userId: str, songId: str, progress: int):
    db = get_db()
    try:
        result = db.history.update_one(
            {"userId": userId, "songId": ObjectId(songId)},
            {"$set": {"playedAt": datetime.now(), "progress": progress}}
        )
        if result.matched_count == 0:
            return f"No history entry found for song {songId} and user {userId}"
        return None
    except Exception as e:
        return e

async def clear_user_history(userId: str):
    db = get_db()
    try:
        db.history.delete_many({"userId": userId})
        return None
    except Exception as e:
        return e

async def get_history_state(userId: str):
    """
    Get the history state for a user.
    Returns {"isPaused": bool} or None if no state exists (defaults to not paused).
    """
    db = get_db()
    try:
        state = db.history_state.find_one({"userId": userId})
        if state:
            return {"isPaused": state.get("isPaused", False)}
        return {"isPaused": False}  # Default: history is not paused
    except Exception as e:
        logger.error(f"Failed to get history state for user {userId}: {str(e)}")
        return None

async def toggle_history_state(userId: str):
    """
    Toggle the history pause state for a user.
    If the user doesn't have a state record, create one with isPaused=True.
    Returns the new state {"isPaused": bool} or error.
    """
    db = get_db()
    try:
        existing = db.history_state.find_one({"userId": userId})
        
        if existing:
            # Toggle the current state
            new_state = not existing.get("isPaused", False)
            db.history_state.update_one(
                {"userId": userId},
                {"$set": {"isPaused": new_state}}
            )
            return {"isPaused": new_state}
        else:
            # First time pausing: create record with isPaused=True
            db.history_state.insert_one({
                "userId": userId,
                "isPaused": True
            })
            return {"isPaused": True}
    except Exception as e:
        logger.error(f"Failed to toggle history state for user {userId}: {str(e)}")
        return None