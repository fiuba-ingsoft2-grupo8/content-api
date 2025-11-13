from datetime import datetime, timezone
from resources.logger import logger
from db.database import get_db
from bson import ObjectId
import httpx
import os


async def get_user_activity(user_id: str, limit: int = 50, activity_type: str = None):
    """
    Get recent activity for a specific user.
    Returns combined list of likes, plays, and published playlists.
    
    Args:
        user_id: User ID to fetch activities for
        limit: Maximum number of activities to return
        activity_type: Optional filter by activity type ('like', 'play', 'playlist_published', 'share')
    """
    db = get_db()
    activities = []
    
    try:
        # Get recent likes (if not filtered or filter matches)
        if activity_type is None or activity_type == "like":
            likes = list(db.likes.find(
                {"user_id": user_id}
            ).sort("created_at", -1).limit(limit))
            
            for like in likes:
                activity = {
                    "type": "like",
                    "userId": user_id,
                    "targetId": str(like["target_id"]),
                    "targetType": like["target_type"],
                    "timestamp": like["created_at"],
                    "createdAt": like["created_at"]
                }
                activities.append(activity)
        
        # Get recent plays (from permanent plays table)
        if activity_type is None or activity_type == "play":
            plays = list(db.plays.find(
                {"user_id": user_id}
            ).sort("played_at", -1).limit(limit))
            
            for play in plays:
                activity = {
                    "type": "play",
                    "userId": user_id,
                    "songId": str(play["song_id"]),
                    "targetType": "song",
                    "timestamp": play["played_at"],
                    "playedAt": play["played_at"]
                }
                activities.append(activity)
        
        # Get recently published playlists
        if activity_type is None or activity_type == "playlist_published":
            playlists = list(db.playlists.find(
                {"userId": user_id, "is_published": True}
            ).sort("published_at", -1).limit(limit))
            
            for playlist in playlists:
                activity = {
                    "type": "playlist_published",
                    "userId": user_id,
                    "playlistId": str(playlist["_id"]),
                    "playlistName": playlist.get("name", ""),
                    "timestamp": playlist["published_at"],
                    "publishedAt": playlist["published_at"]
                }
                activities.append(activity)
        
        # TODO: Add shares when implemented
        # shares = list(db.shares.find(
        #     {"user_id": user_id}
        # ).sort("created_at", -1).limit(limit))
        # 
        # for share in shares:
        #     activity = {
        #         "type": "share",
        #         "userId": user_id,
        #         "targetId": str(share["target_id"]),
        #         "targetType": share["target_type"],
        #         "timestamp": share["created_at"],
        #         "createdAt": share["created_at"]
        #     }
        #     activities.append(activity)
        
        # Sort all activities by timestamp (most recent first)
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Return only the requested limit
        return activities[:limit]
        
    except Exception as e:
        logger.error(f"Failed to get user activity for {user_id}: {str(e)}")
        return []


async def get_following_activity(user_id: str, authorization_token: str, limit: int = 50, activity_type: str = None):
    """
    Get recent activity from users that the current user follows.
    Returns combined list of activities ordered chronologically.
    
    Args:
        user_id: User ID to fetch activity feed for
        authorization_token: JWT token for authenticating with user API
        limit: Maximum number of activities to return
        activity_type: Optional filter by activity type ('like', 'play', 'playlist_published', 'share')
    """
    db = get_db()
    activities = []
    
    try:
        # Get list of users that current user follows from external API
        following_ids = []
        
        # Only make the request if we have a valid token (not during tests)
        if authorization_token and "test" not in authorization_token.lower():
            try:
                user_api_url = f"{os.getenv('USER_API_BASE')}/following"
                headers = {"content-type": "application/json"}
                if authorization_token:
                    headers["Authorization"] = authorization_token
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        user_api_url,
                        headers=headers,
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        following_list = data.get("following", [])
                        following_ids = [user["id"] for user in following_list]
                        logger.info(f"User {user_id} is following {len(following_ids)} users")
                    else:
                        logger.warning(f"Failed to fetch following list for user {user_id}: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching following list from user API: {str(e)}")
        
        if not following_ids:
            logger.info(f"User {user_id} is not following anyone")
            return []
        
        # Get recent likes from followed users (if not filtered or filter matches)
        if activity_type is None or activity_type == "like":
            likes = list(db.likes.find(
                {"user_id": {"$in": following_ids}}
            ).sort("created_at", -1).limit(limit * 2))  # Get more to have enough after filtering
            
            for like in likes:
                activity = {
                    "type": "like",
                    "userId": like["user_id"],
                    "targetId": str(like["target_id"]),
                    "targetType": like["target_type"],
                    "timestamp": like["created_at"],
                    "createdAt": like["created_at"]
                }
                activities.append(activity)
        
        # Get recent plays from followed users
        if activity_type is None or activity_type == "play":
            plays = list(db.plays.find(
                {"user_id": {"$in": following_ids}}
            ).sort("played_at", -1).limit(limit * 2))
            
            for play in plays:
                activity = {
                    "type": "play",
                    "userId": play["user_id"],
                    "songId": str(play["song_id"]),
                    "targetType": "song",
                    "timestamp": play["played_at"],
                    "playedAt": play["played_at"]
                }
                activities.append(activity)
        
        # Get recently published playlists from followed users
        if activity_type is None or activity_type == "playlist_published":
            playlists = list(db.playlists.find(
                {"userId": {"$in": following_ids}, "is_published": True}
            ).sort("published_at", -1).limit(limit * 2))
            
            for playlist in playlists:
                activity = {
                    "type": "playlist_published",
                    "userId": playlist["userId"],
                    "playlistId": str(playlist["_id"]),
                    "playlistName": playlist.get("name", ""),
                    "timestamp": playlist["published_at"],
                    "publishedAt": playlist["published_at"]
                }
                activities.append(activity)
        
        # TODO: Add shares when implemented
        # shares = list(db.shares.find(
        #     {"user_id": {"$in": following_ids}}
        # ).sort("created_at", -1).limit(limit * 2))
        # 
        # for share in shares:
        #     activity = {
        #         "type": "share",
        #         "userId": share["user_id"],
        #         "targetId": str(share["target_id"]),
        #         "targetType": share["target_type"],
        #         "timestamp": share["created_at"],
        #         "createdAt": share["created_at"]
        #     }
        #     activities.append(activity)
        
        # Sort all activities by timestamp (most recent first)
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Return only the requested limit
        return activities[:limit]
        
    except Exception as e:
        logger.error(f"Failed to get following activity for user {user_id}: {str(e)}")
        return []


async def enrich_activity_with_details(activities: list):
    """
    Enrich activities with full details about songs, playlists, collections, etc.
    """
    db = get_db()
    enriched = []
    
    try:
        for activity in activities:
            enriched_activity = activity.copy()
            
            # Enrich likes
            if activity["type"] == "like":
                target_type = activity["targetType"]
                target_id = activity["targetId"]
                
                if target_type == "song":
                    song = db.songs.find_one({"_id": ObjectId(target_id)})
                    if song:
                        enriched_activity["song"] = {
                            "_id": str(song["_id"]),
                            "title": song.get("title", ""),
                            "artist": song.get("artist", ""),
                            "coverUrl": song.get("coverUrl")
                        }
                elif target_type == "collection":
                    collection = db.collections.find_one({"_id": ObjectId(target_id)})
                    if collection:
                        enriched_activity["collection"] = {
                            "_id": str(collection["_id"]),
                            "name": collection.get("name", ""),
                            "artistName": collection.get("artistName", ""),
                            "coverUrl": collection.get("coverUrl"),
                            "type": collection.get("type", "")
                        }
            
            # Enrich plays
            elif activity["type"] == "play":
                song_id = activity["songId"]
                song = db.songs.find_one({"_id": ObjectId(song_id)})
                if song:
                    enriched_activity["song"] = {
                        "_id": str(song["_id"]),
                        "title": song.get("title", ""),
                        "artist": song.get("artist", ""),
                        "coverUrl": song.get("coverUrl")
                    }
            
            # Playlist published already has basic info, could add more if needed
            # elif activity["type"] == "playlist_published":
            #     # Already has playlistId and playlistName
            #     pass
            
            enriched.append(enriched_activity)
        
        return enriched
        
    except Exception as e:
        logger.error(f"Failed to enrich activities: {str(e)}")
        return activities  # Return original if enrichment fails

