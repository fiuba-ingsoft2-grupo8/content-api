import os
import sys
from db.supabase import get_client, SUPABASE_BUCKET
from resources.logger import logger
from fastapi import UploadFile
import uuid

async def upload_cover_image(entity_type: str, user_id: str, file: UploadFile, private: bool = False):
    if not "pytest" in sys.modules or os.getenv("TESTING") == "true":
        client = get_client()

        file_bytes = await file.read()
        ext = file.filename.split(".")[-1]
        unique_name = f"{uuid.uuid4()}.{ext}"
        file_path = f"{entity_type}/{user_id}/{unique_name}"

        client.storage.from_(SUPABASE_BUCKET).upload(
            file_path,
            file_bytes,
            file_options={"content-type": file.content_type}
        )

        url = client.storage.from_(SUPABASE_BUCKET).get_public_url(file_path)

        logger.info(f"File uploaded: {file_path}")
        return {"coverUrl": url}


async def upload_carousel_image(artist_id: str, image_number: int, file: UploadFile):
    """
    Upload a carousel image for an artist's about page.
    
    Args:
        artist_id: The artist's user ID
        image_number: The position number for this carousel image (1-5)
        file: The image file to upload
        
    Returns:
        dict with 'imageUrl' key containing the public URL of the uploaded image
    """
    if not "pytest" in sys.modules or os.getenv("TESTING") == "true":
        client = get_client()

        file_bytes = await file.read()
        ext = file.filename.split(".")[-1]
        filename = f"{artist_id}-carousel-{image_number}.{ext}"
        file_path = f"artists/carousel/{filename}"

        # Delete existing file with same name if it exists (to allow updates)
        try:
            client.storage.from_(SUPABASE_BUCKET).remove([file_path])
        except Exception as e:
            # File might not exist, that's okay
            logger.debug(f"No existing file to remove: {e}")

        client.storage.from_(SUPABASE_BUCKET).upload(
            file_path,
            file_bytes,
            file_options={"content-type": file.content_type}
        )

        url = client.storage.from_(SUPABASE_BUCKET).get_public_url(file_path)

        logger.info(f"Carousel image uploaded: {file_path}")
        return {"imageUrl": url}
    
    # During testing, return a mock URL
    return {"imageUrl": f"https://example.com/test-{artist_id}-carousel-{image_number}.jpg"}