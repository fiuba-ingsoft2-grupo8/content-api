from resources.logger import logger
from db.database import get_db
from bson import ObjectId
from datetime import datetime

async def add_to_history(songId, userId):
    db = get_db()
    try:
        db.history.insert_one({"userId": userId, "songId": songId, "playedAt": datetime.now()})
        return None
    except Exception as e:
        return e

async def get_user_history(userId):
    db = get_db()