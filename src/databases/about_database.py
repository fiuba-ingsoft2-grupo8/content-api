from bson import ObjectId
from db.database import get_db
from db.models import ArtistAbout
from resources.logger import logger

async def create_artist_about(artist_id: str, artist_name: str):
    """
    Create a new artist about page with artistId and artist name.
    All other fields are initialized as empty/null.
    
    Args:
        artist_id: The user ID of the artist
        artist_name: The stage name of the artist
        
    Returns:
        The created artist about document or None if it already exists
    """
    db = get_db()
    try:
        # Check if artist already has an about page
        existing = db.artist_about.find_one({"artist_id": artist_id})
        if existing:
            logger.warning(f"Artist about page already exists for artist_id: {artist_id}")
            return None
        
        # Create new artist about document
        about_doc = ArtistAbout(
            artist_id=artist_id,
            artist=artist_name,
            bio=None,
            social_media=None,
            carousel_images=[],
            artist_pick=None
        )
        
        result = db.artist_about.insert_one(about_doc.model_dump(by_alias=True))
        
        if result.inserted_id:
            created_doc = db.artist_about.find_one({"_id": result.inserted_id})
            logger.info(f"Created artist about page for artist_id: {artist_id}")
            return created_doc
        
        return None
        
    except Exception as e:
        logger.error(f"Error generating artist about: {e}")
        return None


async def update_artist_about(artist_id: str, update_data: dict):
    """
    Update an artist's about page. Cannot update artistId or artist fields.
    
    Args:
        artist_id: The user ID of the artist
        update_data: Dictionary with fields to update (bio, social_media, carousel_images, artist_pick)
        
    Returns:
        The updated artist about document or None if not found
    """
    db = get_db()
    try:
        # Remove any attempts to update protected fields
        update_data.pop("artistId", None)
        update_data.pop("artist_id", None)
        update_data.pop("artist", None)
        
        # Convert field names to snake_case for database first
        db_update_data = {}
        if "bio" in update_data:
            db_update_data["bio"] = update_data["bio"]
        if "socialMedia" in update_data:
            db_update_data["social_media"] = update_data["socialMedia"]
        if "carousel_images" in update_data:
            db_update_data["carousel_images"] = update_data["carousel_images"]
        if "carouselImages" in update_data:
            db_update_data["carousel_images"] = update_data["carouselImages"]
        if "artistPick" in update_data:
            db_update_data["artist_pick"] = update_data["artistPick"]
        if "artist_pick" in update_data:
            db_update_data["artist_pick"] = update_data["artist_pick"]
        
        # Now validate carousel images after conversion
        if "carousel_images" in db_update_data and db_update_data["carousel_images"] is not None:
            # Validate carousel images limit (max 5)
            if len(db_update_data["carousel_images"]) > 5:
                logger.error("Cannot have more than 5 carousel images")
                return None
            
            # Ensure only one primary image
            primary_count = sum(1 for img in db_update_data["carousel_images"] if img.get("isPrimary", False))
            if primary_count > 1:
                logger.error("Cannot have more than one primary image")
                return None
        
        # Update the document
        result = db.artist_about.find_one_and_update(
            {"artist_id": artist_id},
            {"$set": db_update_data},
            return_document=True
        )
        
        if result:
            logger.info(f"Updated artist about page for artist_id: {artist_id}")
            return result
        
        logger.warning(f"Artist about page not found for artist_id: {artist_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error updating artist about: {e}")
        return None


async def get_artist_about_by_id(artist_id: str):
    """
    Get an artist's about page by their artist ID.
    
    Args:
        artist_id: The user ID of the artist
        
    Returns:
        The artist about document or None if not found
    """
    db = get_db()
    try:
        about = db.artist_about.find_one({"artist_id": artist_id})
        
        if about:
            logger.info(f"Retrieved artist about page for artist_id: {artist_id}")
            return about
        
        logger.warning(f"Artist about page not found for artist_id: {artist_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving artist about: {e}")
        return None

