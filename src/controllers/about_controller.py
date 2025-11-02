import databases.about_database as about_db
import databases.storage_database as storage_db
from fastapi import Depends, APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from auth import verify_token
from resources.logger import logger
from common.utils import create_error_response
from schemas import ArtistAbout, UpdateArtistAboutRequest
import uuid

router = APIRouter()


def serialize_artist_about(about_doc):
    """Convert MongoDB artist about document to API response format."""
    if not about_doc:
        return None
    
    return {
        "artistId": about_doc.get("artist_id"),
        "artist": about_doc.get("artist"),
        "bio": about_doc.get("bio"),
        "socialMedia": about_doc.get("social_media"),
        "carouselImages": about_doc.get("carousel_images", []),
        "artistPick": about_doc.get("artist_pick")
    }


@router.post("/", status_code=201)
async def create_artist_about(user: dict = Depends(verify_token)):
    """
    Create a new artist about page for the authenticated user.
    Uses the user_id and stage_name from the token.
    All other fields are initialized as empty/null.
    """
    try:
        artist_id = user["user_id"]
        artist_name = user["stage_name"]
        
        # Create the artist about page
        about_doc = await about_db.create_artist_about(artist_id, artist_name)
        
        if about_doc is None:
            # Already exists
            return JSONResponse(
                status_code=409,
                content=create_error_response(
                    409,
                    "Conflict",
                    "Artist about page already exists for this artist",
                    "/about"
                )
            )
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "data": serialize_artist_about(about_doc)
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating artist about: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while creating the artist about page",
                "/about"
            )
        )


@router.put("/", status_code=200)
async def update_artist_about(
    update_request: UpdateArtistAboutRequest,
    user: dict = Depends(verify_token)
):
    """
    Update the authenticated user's artist about page.
    Cannot update artistId or artist fields.
    
    Validates:
    - Maximum 5 carousel images
    - Only one primary image in carousel
    """
    try:
        artist_id = user["user_id"]
        
        # Convert Pydantic model to dict, excluding None values
        update_data = update_request.model_dump(exclude_none=True)
        
        # Update the artist about page
        about_doc = await about_db.update_artist_about(artist_id, update_data)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "Artist about page not found. Please create it first using POST /about",
                    "/about"
                )
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": serialize_artist_about(about_doc)
            }
        )
        
    except Exception as e:
        logger.error(f"Error updating artist about: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while updating the artist about page",
                "/about"
            )
        )


@router.get("/{artist_id}", status_code=200)
async def get_artist_about(artist_id: str):
    """
    Get an artist's about page by their artist ID.
    This endpoint is public and doesn't require authentication.
    """
    try:
        about_doc = await about_db.get_artist_about_by_id(artist_id)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Artist about page not found for artist_id: {artist_id}",
                    f"/about/{artist_id}"
                )
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": serialize_artist_about(about_doc)
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving artist about: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while retrieving the artist about page",
                f"/about/{artist_id}"
            )
        )


@router.post("/carousel", status_code=201)
async def upload_carousel_image(
    file: UploadFile = File(...),
    user: dict = Depends(verify_token)
):
    """
    Upload an image to the artist's carousel.
    - Maximum 5 images allowed
    - First image uploaded will be marked as primary
    - Images are stored with format: {artist_id}-carousel-{number}
    """
    try:
        artist_id = user["user_id"]
        
        # Get artist's current about page
        about_doc = await about_db.get_artist_about_by_id(artist_id)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "Artist about page not found. Please create it first using POST /about",
                    "/about/carousel"
                )
            )
        
        # Get current carousel images
        current_images = about_doc.get("carousel_images", [])
        
        # Check if we already have 5 images
        if len(current_images) >= 5:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    "Maximum of 5 carousel images allowed. Please delete an existing image first.",
                    "/about/carousel"
                )
            )
        
        # Determine image number (1-5) based on current count
        image_number = len(current_images) + 1
        
        # Upload the image to Supabase
        upload_result = await storage_db.upload_carousel_image(artist_id, image_number, file)
        image_url = upload_result["imageUrl"]
        
        # Generate unique ID for the image
        image_id = str(uuid.uuid4())
        
        # Determine if this is the primary image (first one)
        is_primary = len(current_images) == 0
        
        # Add the new image to the carousel
        new_image = {
            "id": image_id,
            "url": image_url,
            "isPrimary": is_primary
        }
        current_images.append(new_image)
        
        # Update the about page with the new carousel
        update_data = {
            "carouselImages": current_images
        }
        
        updated_doc = await about_db.update_artist_about(artist_id, update_data)
        
        if updated_doc is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(
                    500,
                    "Internal Server Error",
                    "Failed to update artist about with new carousel image",
                    "/about/carousel"
                )
            )
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": f"Carousel image uploaded successfully as image #{image_number}",
                "data": {
                    "imageId": image_id,
                    "imageUrl": image_url,
                    "imageNumber": image_number,
                    "isPrimary": is_primary,
                    "totalImages": len(current_images)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error uploading carousel image: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while uploading the carousel image",
                "/about/carousel"
            )
        )


@router.put("/carousel/primary/{image_id}", status_code=200)
async def set_primary_carousel_image(
    image_id: str,
    user: dict = Depends(verify_token)
):
    """
    Set a carousel image as the primary image.
    Only one image can be primary at a time.
    All other images will be set to isPrimary: false.
    """
    try:
        artist_id = user["user_id"]
        
        # Get artist's current about page
        about_doc = await about_db.get_artist_about_by_id(artist_id)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "Artist about page not found",
                    f"/about/carousel/primary/{image_id}"
                )
            )
        
        # Get current carousel images
        current_images = about_doc.get("carousel_images", [])
        
        if not current_images:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "No carousel images found",
                    f"/about/carousel/primary/{image_id}"
                )
            )
        
        # Find the image with the given ID
        image_found = False
        updated_images = []
        
        for img in current_images:
            if img.get("id") == image_id:
                image_found = True
                updated_images.append({
                    "id": img["id"],
                    "url": img["url"],
                    "isPrimary": True
                })
            else:
                updated_images.append({
                    "id": img["id"],
                    "url": img["url"],
                    "isPrimary": False
                })
        
        if not image_found:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Carousel image with ID {image_id} not found",
                    f"/about/carousel/primary/{image_id}"
                )
            )
        
        # Update the about page with the modified carousel
        update_data = {
            "carouselImages": updated_images
        }
        
        updated_doc = await about_db.update_artist_about(artist_id, update_data)
        
        if updated_doc is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(
                    500,
                    "Internal Server Error",
                    "Failed to update primary image",
                    f"/about/carousel/primary/{image_id}"
                )
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Image {image_id} set as primary",
                "data": serialize_artist_about(updated_doc)
            }
        )
        
    except Exception as e:
        logger.error(f"Error setting primary carousel image: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while setting the primary image",
                f"/about/carousel/primary/{image_id}"
            )
        )


@router.delete("/carousel/{image_id}", status_code=200)
async def delete_carousel_image(
    image_id: str,
    user: dict = Depends(verify_token)
):
    """
    Delete a carousel image by its ID.
    If the deleted image was primary and other images exist,
    the first remaining image will be set as primary.
    """
    try:
        artist_id = user["user_id"]
        
        # Get artist's current about page
        about_doc = await about_db.get_artist_about_by_id(artist_id)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "Artist about page not found",
                    f"/about/carousel/{image_id}"
                )
            )
        
        # Get current carousel images
        current_images = about_doc.get("carousel_images", [])
        
        if not current_images:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "No carousel images found",
                    f"/about/carousel/{image_id}"
                )
            )
        
        # Find and remove the image with the given ID
        image_found = False
        was_primary = False
        updated_images = []
        
        for img in current_images:
            if img.get("id") == image_id:
                image_found = True
                was_primary = img.get("isPrimary", False)
                # Don't add this image to updated_images (effectively deleting it)
            else:
                updated_images.append(img)
        
        if not image_found:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Carousel image with ID {image_id} not found",
                    f"/about/carousel/{image_id}"
                )
            )
        
        # If the deleted image was primary and there are remaining images,
        # set the first one as primary
        if was_primary and len(updated_images) > 0:
            updated_images[0]["isPrimary"] = True
        
        # Update the about page with the modified carousel
        update_data = {
            "carouselImages": updated_images
        }
        
        updated_doc = await about_db.update_artist_about(artist_id, update_data)
        
        if updated_doc is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(
                    500,
                    "Internal Server Error",
                    "Failed to delete carousel image",
                    f"/about/carousel/{image_id}"
                )
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Image {image_id} deleted successfully",
                "data": {
                    "deletedImageId": image_id,
                    "remainingImages": len(updated_images),
                    "newPrimarySet": was_primary and len(updated_images) > 0
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error deleting carousel image: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while deleting the carousel image",
                f"/about/carousel/{image_id}"
            )
        )

