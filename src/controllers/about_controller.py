import databases.about_database as about_db
from fastapi import Depends, APIRouter
from fastapi.responses import JSONResponse
from auth import verify_token
from resources.logger import logger
from common.utils import create_error_response
from schemas import ArtistAbout, UpdateArtistAboutRequest

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

