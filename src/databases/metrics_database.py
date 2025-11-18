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

async def record_play(user_id: str, song_id: str, country: str = None):
    """
    Record a play in the permanent plays table.
    This is separate from user history and is never deleted.
    """
    db = get_db()
    try:
        play = Play(
            user_id=user_id,
            song_id=ObjectId(song_id),
            country=country
        )
        db.plays.insert_one(play.model_dump(by_alias=True))
        logger.info(f"Recorded play for song {song_id} by user {user_id} from {country or 'unknown'}")
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

async def get_monthly_listeners(artist_id: str, current_period_start: datetime, previous_period_start: datetime, country: str = None):
    """
    Get unique listeners in the current period vs previous period.
    Uses the permanent plays table instead of user history.
    Optionally filter by country.
    """
    db = get_db()
    try:
        # Get all songs by this artist
        artist_songs = list(db.songs.find({"artistId": artist_id}, {"_id": 1}))
        song_ids = [song["_id"] for song in artist_songs]
        
        if not song_ids:
            return {"value": 0, "delta": 0, "percentChange": 0.0}
        
        # Build base query
        base_query = {"song_id": {"$in": song_ids}}
        if country:
            base_query["country"] = country
        
        # Current period listeners
        current_query = {**base_query, "played_at": {"$gte": current_period_start}}
        current_listeners = db.plays.distinct("user_id", current_query)
        current_count = len(current_listeners)
        
        # Previous period listeners
        previous_query = {
            **base_query,
            "played_at": {
                "$gte": previous_period_start,
                "$lt": current_period_start
            }
        }
        previous_listeners = db.plays.distinct("user_id", previous_query)
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

async def get_period_plays(artist_id: str, current_period_start: datetime, previous_period_start: datetime, country: str = None):
    """
    Get total plays in the current period vs previous period.
    Uses the permanent plays table instead of user history.
    Optionally filter by country.
    """
    db = get_db()
    try:
        # Get all songs by this artist
        artist_songs = list(db.songs.find({"artistId": artist_id}, {"_id": 1}))
        song_ids = [song["_id"] for song in artist_songs]
        
        if not song_ids:
            return {"value": 0, "delta": 0, "percentChange": 0.0}
        
        # Build base query
        base_query = {"song_id": {"$in": song_ids}}
        if country:
            base_query["country"] = country
        
        # Current period plays
        current_query = {**base_query, "played_at": {"$gte": current_period_start}}
        current_plays = db.plays.count_documents(current_query)
        
        # Previous period plays
        previous_query = {
            **base_query,
            "played_at": {
                "$gte": previous_period_start,
                "$lt": current_period_start
            }
        }
        previous_plays = db.plays.count_documents(previous_query)
        
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

async def get_artist_metrics(
    artist_id: str, 
    period: str = "monthly",
    start_date: datetime = None,
    end_date: datetime = None,
    country: str = None
):
    """
    Get complete artist metrics with flexible period filtering.
    
    Args:
        artist_id: Artist's user ID
        period: 'daily', 'weekly', 'monthly', or 'custom'
        start_date: Custom period start (required if period='custom')
        end_date: Custom period end (required if period='custom')
        country: ISO country code to filter by (optional)
    
    Returns:
        Dict with artist metrics including listeners, plays, saves, and shares
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Calculate periods based on period type
        if period == "daily":
            current_period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            previous_period_start = current_period_start - timedelta(days=1)
        elif period == "weekly":
            # Current week (starting Monday)
            days_since_monday = now.weekday()
            current_period_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            previous_period_start = current_period_start - timedelta(weeks=1)
        elif period == "custom":
            if not start_date or not end_date:
                raise ValueError("start_date and end_date are required for custom period")
            current_period_start = end_date
            period_duration = end_date - start_date
            previous_period_start = start_date - period_duration
        else:  # monthly (default)
            current_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if current_period_start.month == 1:
                previous_period_start = current_period_start.replace(year=current_period_start.year - 1, month=12)
            else:
                previous_period_start = current_period_start.replace(month=current_period_start.month - 1)
        
        # Get metrics with filters
        monthly_listeners = await get_monthly_listeners(artist_id, current_period_start, previous_period_start, country)
        plays = await get_period_plays(artist_id, current_period_start, previous_period_start, country)
        saves = await get_period_saves(artist_id, current_period_start, previous_period_start)
        shares = await get_period_shares(artist_id, current_period_start, previous_period_start)
        
        return {
            "artistId": artist_id,
            "period": period,
            "country": country,
            "monthlyListeners": monthly_listeners,
            "plays": plays,
            "saves": saves,
            "shares": shares
        }
    except Exception as e:
        logger.error(f"Failed to get artist metrics: {str(e)}")
        return None

# ============= ARTIST BREAKDOWNS =============

async def get_artist_top_songs(
    artist_id: str,
    limit: int = 10,
    sort_by: str = "plays",
    start_date: datetime = None,
    end_date: datetime = None,
    country: str = None
):
    """
    Get top songs for an artist sorted by plays or likes.
    
    Args:
        artist_id: Artist's user ID
        limit: Number of songs to return (default 10)
        sort_by: 'plays' or 'likes' (default 'plays')
        start_date: Filter plays from this date (optional)
        end_date: Filter plays until this date (optional)
        country: ISO country code to filter by (optional)
    
    Returns:
        List of top songs with their metrics
    """
    db = get_db()
    try:
        # Get all songs by this artist
        artist_songs = list(db.songs.find({"artistId": artist_id}))
        
        if not artist_songs:
            return []
        
        # Build metrics for each song
        songs_with_metrics = []
        for song in artist_songs:
            song_id = song["_id"]
            
            # Build query for plays
            plays_query = {"song_id": song_id}
            if start_date:
                plays_query["played_at"] = {"$gte": start_date}
            if end_date:
                plays_query.setdefault("played_at", {})["$lte"] = end_date
            if country:
                plays_query["country"] = country
            
            # Count plays
            plays_count = db.plays.count_documents(plays_query)
            
            # Count likes (no date filter for likes as they're cumulative)
            likes_count = db.likes.count_documents({
                "target_id": song_id,
                "target_type": "song"
            })
            
            songs_with_metrics.append({
                "songId": str(song_id),
                "title": song["title"],
                "artist": song["artist"],
                "coverUrl": song.get("coverUrl"),
                "plays": plays_count,
                "likes": likes_count
            })
        
        # Sort by the requested metric
        sort_key = "plays" if sort_by == "plays" else "likes"
        songs_with_metrics.sort(key=lambda x: x[sort_key], reverse=True)
        
        return songs_with_metrics[:limit]
        
    except Exception as e:
        logger.error(f"Failed to get artist top songs: {str(e)}")
        return []

async def get_artist_top_markets(
    artist_id: str,
    limit: int = 10,
    start_date: datetime = None,
    end_date: datetime = None
):
    """
    Get top markets (countries) for an artist by play count.
    
    Args:
        artist_id: Artist's user ID
        limit: Number of markets to return (default 10)
        start_date: Filter plays from this date (optional)
        end_date: Filter plays until this date (optional)
    
    Returns:
        List of top markets with play counts
    """
    db = get_db()
    try:
        # Get all songs by this artist
        artist_songs = list(db.songs.find({"artistId": artist_id}, {"_id": 1}))
        song_ids = [song["_id"] for song in artist_songs]
        
        if not song_ids:
            return []
        
        # Build query for plays
        match_query = {
            "song_id": {"$in": song_ids},
            "country": {"$ne": None}  # Exclude plays without country data
        }
        if start_date:
            match_query["played_at"] = {"$gte": start_date}
        if end_date:
            match_query.setdefault("played_at", {})["$lte"] = end_date
        
        # Aggregate plays by country
        pipeline = [
            {"$match": match_query},
            {"$group": {
                "_id": "$country",
                "plays": {"$sum": 1},
                "listeners": {"$addToSet": "$user_id"}
            }},
            {"$project": {
                "country": "$_id",
                "plays": 1,
                "listeners": {"$size": "$listeners"}
            }},
            {"$sort": {"plays": -1}},
            {"$limit": limit}
        ]
        
        results = list(db.plays.aggregate(pipeline))
        
        # Format results
        markets = []
        for result in results:
            markets.append({
                "country": result["country"],
                "plays": result["plays"],
                "listeners": result["listeners"]
            })
        
        return markets
        
    except Exception as e:
        logger.error(f"Failed to get artist top markets: {str(e)}")
        return []

async def get_artist_top_playlists(
    artist_id: str,
    limit: int = 10
):
    """
    Get top playlists that include songs from this artist.
    
    Args:
        artist_id: Artist's user ID
        limit: Number of playlists to return (default 10)
    
    Returns:
        List of playlists with the count of artist songs they contain
    """
    db = get_db()
    try:
        # Get all songs by this artist
        artist_songs = list(db.songs.find({"artistId": artist_id}, {"_id": 1}))
        song_ids = [song["_id"] for song in artist_songs]
        
        if not song_ids:
            return []
        
        # Find all playlists containing these songs
        pipeline = [
            {"$match": {"song_id": {"$in": song_ids}}},
            {"$group": {
                "_id": "$playlist_id",
                "songCount": {"$sum": 1}
            }},
            {"$sort": {"songCount": -1}},
            {"$limit": limit}
        ]
        
        playlist_stats = list(db.playlist_songs.aggregate(pipeline))
        
        # Get playlist details
        playlists = []
        for stat in playlist_stats:
            playlist = db.playlists.find_one({"_id": stat["_id"]})
            if playlist:
                playlists.append({
                    "playlistId": str(playlist["_id"]),
                    "name": playlist.get("name", "Unknown Playlist"),
                    "description": playlist.get("description"),
                    "coverUrl": playlist.get("cover_image"),
                    "userId": playlist.get("userId"),
                    "songCount": stat["songCount"],
                    "isPublished": playlist.get("is_published", False)
                })
        
        return playlists
        
    except Exception as e:
        logger.error(f"Failed to get artist top playlists: {str(e)}")
        return []

