from datetime import datetime, timezone, timedelta
from resources.logger import logger
from db.database import get_db
from bson import ObjectId
from db.models import Like, Share, Play

# ============= LIKES =============

async def toggle_like(user_id: str, target_id: str, target_type: str):
    """
    Toggle like for a song or collection.
    Returns (is_liked, error) where is_liked indicates if item is now liked.
    """
    db = get_db()
    try:
        existing = db.likes.find_one({
            "user_id": user_id,
            "target_id": ObjectId(target_id),
            "target_type": target_type
        })
        
        if existing:
            # Unlike
            db.likes.delete_one({"_id": existing["_id"]})
            logger.info(f"User {user_id} unliked {target_type} {target_id}")
            return (False, None)
        else:
            # Like
            like = Like(
                user_id=user_id,
                target_id=ObjectId(target_id),
                target_type=target_type
            )
            db.likes.insert_one(like.model_dump(by_alias=True))
            logger.info(f"User {user_id} liked {target_type} {target_id}")
            return (True, None)
            
    except Exception as e:
        logger.error(f"Failed to toggle like: {str(e)}")
        return (False, e)

async def get_likes_count(target_id: str, target_type: str):
    """Get total number of likes for a target."""
    db = get_db()
    try:
        count = db.likes.count_documents({
            "target_id": ObjectId(target_id),
            "target_type": target_type
        })
        return count
    except Exception as e:
        logger.error(f"Failed to get likes count: {str(e)}")
        return 0

async def is_liked_by_user(user_id: str, target_id: str, target_type: str):
    """Check if user has liked the target."""
    db = get_db()
    try:
        exists = db.likes.find_one({
            "user_id": user_id,
            "target_id": ObjectId(target_id),
            "target_type": target_type
        })
        return exists is not None
    except Exception as e:
        logger.error(f"Failed to check if liked: {str(e)}")
        return False

# ============= SHARES =============

async def record_share(user_id: str, target_id: str, target_type: str):
    """Record a share event."""
    db = get_db()
    try:
        share = Share(
            user_id=user_id,
            target_id=ObjectId(target_id),
            target_type=target_type
        )
        db.shares.insert_one(share.model_dump(by_alias=True))
        logger.info(f"User {user_id} shared {target_type} {target_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to record share: {str(e)}")
        return e

async def get_shares_count(target_id: str, target_type: str):
    """Get total number of shares for a target."""
    db = get_db()
    try:
        count = db.shares.count_documents({
            "target_id": ObjectId(target_id),
            "target_type": target_type
        })
        return count
    except Exception as e:
        logger.error(f"Failed to get shares count: {str(e)}")
        return 0

# ============= PLAYS =============

async def record_play(user_id: str, song_id: str):
    """
    Record a play in the permanent plays table.
    This is separate from user history and is never deleted.
    """
    db = get_db()
    try:
        play = Play(
            user_id=user_id,
            song_id=ObjectId(song_id)
        )
        db.plays.insert_one(play.model_dump(by_alias=True))
        logger.info(f"Recorded play for song {song_id} by user {user_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to record play: {str(e)}")
        return e

async def get_plays_count(target_id: str, target_type: str = "song"):
    """
    Get total number of plays from the permanent plays table.
    For songs: count play entries
    For collections: count all plays of songs in the collection
    """
    db = get_db()
    try:
        if target_type == "song":
            count = db.plays.count_documents({"song_id": ObjectId(target_id)})
            return count
        elif target_type == "collection":
            # Get all songs in the collection
            collection_songs = list(db.collection_songs.find(
                {"collection_id": ObjectId(target_id)},
                {"song_id": 1}
            ))
            song_ids = [cs["song_id"] for cs in collection_songs]
            
            if not song_ids:
                return 0
            
            # Count plays for all songs in collection
            count = db.plays.count_documents({"song_id": {"$in": song_ids}})
            return count
        else:
            return 0
    except Exception as e:
        logger.error(f"Failed to get plays count: {str(e)}")
        return 0

# ============= SONG METRICS =============

async def get_song_metrics(song_id: str):
    """Get complete metrics for a song."""
    try:
        plays = await get_plays_count(song_id, "song")
        likes = await get_likes_count(song_id, "song")
        shares = await get_shares_count(song_id, "song")
        
        return {
            "songId": song_id,
            "plays": plays,
            "likes": likes,
            "shares": shares
        }
    except Exception as e:
        logger.error(f"Failed to get song metrics: {str(e)}")
        return None

# ============= COLLECTION METRICS =============

async def get_collection_metrics(collection_id: str):
    """
    Get complete metrics for a collection.
    Likes = sum of likes from all songs in the collection.
    """
    db = get_db()
    try:
        plays = await get_plays_count(collection_id, "collection")
        shares = await get_shares_count(collection_id, "collection")
        
        # Get all songs in the collection
        collection_songs = list(db.collection_songs.find(
            {"collection_id": ObjectId(collection_id)},
            {"song_id": 1}
        ))
        song_ids = [cs["song_id"] for cs in collection_songs]
        
        # Sum likes from all songs in the collection
        total_likes = 0
        if song_ids:
            total_likes = db.likes.count_documents({
                "target_id": {"$in": song_ids},
                "target_type": "song"
            })
        
        return {
            "collectionId": collection_id,
            "totalPlays": plays,
            "likes": total_likes,
            "shares": shares
        }
    except Exception as e:
        logger.error(f"Failed to get collection metrics: {str(e)}")
        return None

# ============= ARTIST METRICS =============

async def get_monthly_listeners(artist_id: str, current_period_start: datetime, previous_period_start: datetime):
    """
    Get unique listeners in the current month vs previous month.
    Uses the permanent plays table instead of user history.
    """
    db = get_db()
    try:
        # Get all songs by this artist
        artist_songs = list(db.songs.find({"artistId": artist_id}, {"_id": 1}))
        song_ids = [song["_id"] for song in artist_songs]
        
        if not song_ids:
            return {"value": 0, "delta": 0, "percentChange": 0.0}
        
        # Current period listeners
        current_listeners = db.plays.distinct("user_id", {
            "song_id": {"$in": song_ids},
            "played_at": {"$gte": current_period_start}
        })
        current_count = len(current_listeners)
        
        # Previous period listeners
        previous_listeners = db.plays.distinct("user_id", {
            "song_id": {"$in": song_ids},
            "played_at": {
                "$gte": previous_period_start,
                "$lt": current_period_start
            }
        })
        previous_count = len(previous_listeners)
        
        delta = current_count - previous_count
        percent_change = ((current_count - previous_count) / previous_count * 100) if previous_count > 0 else 0.0
        
        return {
            "value": current_count,
            "delta": delta,
            "percentChange": round(percent_change, 2)
        }
    except Exception as e:
        logger.error(f"Failed to get monthly listeners: {str(e)}")
        return {"value": 0, "delta": 0, "percentChange": 0.0}

async def get_period_plays(artist_id: str, current_period_start: datetime, previous_period_start: datetime):
    """
    Get total plays in the current period vs previous period.
    Uses the permanent plays table instead of user history.
    """
    db = get_db()
    try:
        # Get all songs by this artist
        artist_songs = list(db.songs.find({"artistId": artist_id}, {"_id": 1}))
        song_ids = [song["_id"] for song in artist_songs]
        
        if not song_ids:
            return {"value": 0, "delta": 0, "percentChange": 0.0}
        
        # Current period plays
        current_plays = db.plays.count_documents({
            "song_id": {"$in": song_ids},
            "played_at": {"$gte": current_period_start}
        })
        
        # Previous period plays
        previous_plays = db.plays.count_documents({
            "song_id": {"$in": song_ids},
            "played_at": {
                "$gte": previous_period_start,
                "$lt": current_period_start
            }
        })
        
        delta = current_plays - previous_plays
        percent_change = ((current_plays - previous_plays) / previous_plays * 100) if previous_plays > 0 else 0.0
        
        return {
            "value": current_plays,
            "delta": delta,
            "percentChange": round(percent_change, 2)
        }
    except Exception as e:
        logger.error(f"Failed to get period plays: {str(e)}")
        return {"value": 0, "delta": 0, "percentChange": 0.0}

async def get_period_saves(artist_id: str, current_period_start: datetime, previous_period_start: datetime):
    """
    Get total saves (likes) for artist's songs in period.
    Only counts song likes (collections don't have direct likes).
    """
    db = get_db()
    try:
        # Get all songs by this artist
        artist_songs = list(db.songs.find({"artistId": artist_id}, {"_id": 1}))
        song_ids = [song["_id"] for song in artist_songs]
        
        if not song_ids:
            return {"value": 0, "delta": 0, "percentChange": 0.0}
        
        # Current period saves (only song likes)
        current_saves = db.likes.count_documents({
            "target_id": {"$in": song_ids},
            "target_type": "song",
            "created_at": {"$gte": current_period_start}
        })
        
        # Previous period saves (only song likes)
        previous_saves = db.likes.count_documents({
            "target_id": {"$in": song_ids},
            "target_type": "song",
            "created_at": {
                "$gte": previous_period_start,
                "$lt": current_period_start
            }
        })
        
        delta = current_saves - previous_saves
        percent_change = ((current_saves - previous_saves) / previous_saves * 100) if previous_saves > 0 else 0.0
        
        return {
            "value": current_saves,
            "delta": delta,
            "percentChange": round(percent_change, 2)
        }
    except Exception as e:
        logger.error(f"Failed to get period saves: {str(e)}")
        return {"value": 0, "delta": 0, "percentChange": 0.0}

async def get_period_shares(artist_id: str, current_period_start: datetime, previous_period_start: datetime):
    """
    Get total shares for artist's content in period.
    Includes shares of both songs and collections.
    """
    db = get_db()
    try:
        # Get all songs by this artist
        artist_songs = list(db.songs.find({"artistId": artist_id}, {"_id": 1}))
        song_ids = [song["_id"] for song in artist_songs]
        
        # Get all collections by this artist
        artist_collections = list(db.collections.find({"artistId": artist_id}, {"_id": 1}))
        collection_ids = [col["_id"] for col in artist_collections]
        
        # Build query conditions
        query_conditions = []
        if song_ids:
            query_conditions.append({"target_id": {"$in": song_ids}, "target_type": "song"})
        if collection_ids:
            query_conditions.append({"target_id": {"$in": collection_ids}, "target_type": "collection"})
        
        if not query_conditions:
            return {"value": 0, "delta": 0, "percentChange": 0.0}
        
        # Current period shares
        current_shares = db.shares.count_documents({
            "$or": query_conditions,
            "created_at": {"$gte": current_period_start}
        })
        
        # Previous period shares
        previous_shares = db.shares.count_documents({
            "$or": query_conditions,
            "created_at": {
                "$gte": previous_period_start,
                "$lt": current_period_start
            }
        })
        
        delta = current_shares - previous_shares
        percent_change = ((current_shares - previous_shares) / previous_shares * 100) if previous_shares > 0 else 0.0
        
        return {
            "value": current_shares,
            "delta": delta,
            "percentChange": round(percent_change, 2)
        }
    except Exception as e:
        logger.error(f"Failed to get period shares: {str(e)}")
        return {"value": 0, "delta": 0, "percentChange": 0.0}

async def get_artist_metrics(artist_id: str):
    """
    Get complete artist metrics.
    Period is current month vs previous month.
    """
    try:
        now = datetime.now(timezone.utc)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Previous month start
        if current_month_start.month == 1:
            previous_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
        else:
            previous_month_start = current_month_start.replace(month=current_month_start.month - 1)
        
        monthly_listeners = await get_monthly_listeners(artist_id, current_month_start, previous_month_start)
        plays = await get_period_plays(artist_id, current_month_start, previous_month_start)
        saves = await get_period_saves(artist_id, current_month_start, previous_month_start)
        shares = await get_period_shares(artist_id, current_month_start, previous_month_start)
        
        return {
            "artistId": artist_id,
            "monthlyListeners": monthly_listeners,
            "plays": plays,
            "saves": saves,
            "shares": shares
        }
    except Exception as e:
        logger.error(f"Failed to get artist metrics: {str(e)}")
        return None

