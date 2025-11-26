from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from db.database import get_db
from resources.logger import logger


async def create_artist_about(artist_id: str, artist_name: str):
    """
    Create a new artist about page.
    
    Args:
        artist_id: User ID of the artist
        artist_name: Stage name of the artist
    
    Returns:
        Created document or None if already exists
    """
    db = get_db()
    
    try:
        # Check if artist about page already exists
        existing = db.artist_about.find_one({"artist_id": artist_id})
        if existing:
            logger.warning(f"Artist about page already exists for artist_id={artist_id}")
            return None
        
        # Create the document
        about_doc = {
            "artist_id": artist_id,
            "artist": artist_name,
            "bio": None,
            "social_media": None,
            "carousel_images": [],
            "artist_pick": None
        }
        
        result = db.artist_about.insert_one(about_doc)
        logger.info(f"Successfully created artist about page for artist_id={artist_id}")
        
        # Return the created document
        return db.artist_about.find_one({"_id": result.inserted_id})
        
    except Exception as e:
        logger.error(f"Failed to create artist about page: {str(e)}")
        return None


async def get_artist_about_by_id(artist_id: str):
    """
    Get an artist about page by artist ID.
    
    Args:
        artist_id: User ID of the artist
    
    Returns:
        Artist about document or None if not found
    """
    db = get_db()
    
    try:
        about_doc = db.artist_about.find_one({"artist_id": artist_id})
        
        if about_doc:
            logger.info(f"Successfully retrieved artist about page for artist_id={artist_id}")
        else:
            logger.warning(f"Artist about page not found for artist_id={artist_id}")
        
        return about_doc
        
    except Exception as e:
        logger.error(f"Failed to get artist about page: {str(e)}")
        return None


async def update_artist_about(artist_id: str, update_data: dict):
    """
    Update an artist about page.
    
    Args:
        artist_id: User ID of the artist
        update_data: Dictionary containing fields to update
    
    Returns:
        Updated document or None if not found
    """
    db = get_db()
    
    try:
        # Convert camelCase keys to snake_case for database
        db_update_data = {}
        
        if "bio" in update_data:
            db_update_data["bio"] = update_data["bio"]
        
        if "socialMedia" in update_data:
            db_update_data["social_media"] = update_data["socialMedia"]
        
        if "carouselImages" in update_data:
            carousel_images = update_data["carouselImages"]
            
            # Validate max 5 images
            if len(carousel_images) > 5:
                logger.warning(f"Carousel images exceed maximum of 5 for artist_id={artist_id}")
                return None
            
            # Validate only one primary image
            primary_count = sum(1 for img in carousel_images if img.get("isPrimary", False))
            if primary_count > 1:
                logger.warning(f"Multiple primary images not allowed for artist_id={artist_id}")
                return None
            
            db_update_data["carousel_images"] = carousel_images
        
        if "artistPick" in update_data:
            db_update_data["artist_pick"] = update_data["artistPick"]
        
        if not db_update_data:
            logger.warning(f"No valid fields to update for artist_id={artist_id}")
            return None
        
        result = db.artist_about.update_one(
            {"artist_id": artist_id},
            {"$set": db_update_data}
        )
        
        if result.matched_count == 0:
            logger.warning(f"Artist about page not found for artist_id={artist_id}")
            return None
        
        logger.info(f"Successfully updated artist about page for artist_id={artist_id}")
        
        # Return the updated document
        return db.artist_about.find_one({"artist_id": artist_id})
        
    except Exception as e:
        logger.error(f"Failed to update artist about page: {str(e)}")
        return None


async def get_artist_appearances(artist_id: str, stage_name: str, limit: int = 6):
    """
    Get collections and playlists where an artist appears (as main artist or in credits).
    
    Args:
        artist_id: User ID of the artist
        stage_name: Stage name of the artist (used for credits matching)
        limit: Number of items to return (default 6, will be split 3-3 if both types exist)
    
    Returns:
        Dictionary with 'collections' and 'playlists' lists
    """
    db = get_db()
    
    try:
        now = datetime.now(timezone.utc)
        
        # Find collections where artist is main artist OR in credits
        # Only published collections (releaseDate <= now)
        collections_query = {
            "$or": [
                {"artistId": artist_id},
                {"credits": stage_name}
            ],
            "releaseDate": {"$lte": now}
        }
        
        # Get collections sorted by release date descending, then alphabetically
        collections = list(
            db.collections.find(collections_query)
            .sort([("releaseDate", -1), ("name", 1)])
            .limit(limit)
        )
        
        # Find playlists containing songs by this artist
        # First get all songs by this artist (by stage_name since that's in credits)
        songs_query = {"artist": stage_name}
        artist_songs = list(db.songs.find(songs_query, {"_id": 1}))
        song_ids = [song["_id"] for song in artist_songs]
        
        playlists = []
        if song_ids:
            # Find playlists that contain at least one of these songs
            playlist_ids = list(
                db.playlist_songs.aggregate([
                    {"$match": {"song_id": {"$in": song_ids}}},
                    {"$group": {"_id": "$playlist_id"}},
                    {"$limit": limit * 2}  # Get more to filter after
                ])
            )
            
            playlist_oids = [p["_id"] for p in playlist_ids]
            
            if playlist_oids:
                # Get only published playlists, exclude mixes and liked songs
                playlists_query = {
                    "_id": {"$in": playlist_oids},
                    "is_published": True,
                    "isMix": {"$ne": True},
                    "isLikedSongs": {"$ne": True}
                }
                
                playlists = list(db.playlists.find(playlists_query))
                
                # Calculate popularity score for each playlist
                # Based on: number of songs, number of followers (for now, simplified)
                for playlist in playlists:
                    # Count songs in this playlist
                    song_count = db.playlist_songs.count_documents({
                        "playlist_id": playlist["_id"]
                    })
                    
                    # For now, use song count as popularity (can be extended later)
                    # Could add: likes, shares, views, etc.
                    playlist["_popularity"] = song_count
                
                # Sort by popularity descending, then alphabetically
                playlists.sort(key=lambda p: (-p.get("_popularity", 0), p.get("name", "")))
                
                # Remove temporary popularity field
                for playlist in playlists:
                    playlist.pop("_popularity", None)
                
                # Limit results
                playlists = playlists[:limit]
        
        logger.info(
            f"Found {len(collections)} collections and {len(playlists)} playlists "
            f"for artist {stage_name} (id={artist_id})"
        )
        
        return {
            "collections": collections,
            "playlists": playlists
        }
        
    except Exception as e:
        logger.error(f"Failed to get artist appearances: {str(e)}")
        return {
            "collections": [],
            "playlists": []
        }
