from databases.collections_database import USER_API_BASE
import schemas
from fastapi import Body, Depends, Header
from resources.logger import logger
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from auth import verify_token
from common.utils import create_error_response
import databases.preferences_database as preferences_db

router = APIRouter()


@router.post(
    "/preferences/genres",
    responses={
        200: {
            "description": "Successfully set genre preferences",
            "content": {
                "application/json": {
                    "examples": {
                        "ok": {
                            "summary": "Genres saved",
                            "value": {
                                "message": "Genres saved successfully",
                                "genres": ["Rock", "Jazz", "Pop"]
                            }
                        }
                    }
                }
            }
        }
    }
)
async def set_genre_preferences(request: schemas.setGenresRequest, user: dict = Depends(verify_token)):
    """
    Save up to 5 selected music genres for the current user.
    """
    try:
        genres = request.data

        if not isinstance(genres, list):
            raise ValueError("Field 'data' must be a list of genres.")

        if len(genres) > 5:
            raise ValueError("You can select up to 5 genres.")

        result = await preferences_db.set_user_genres(user["user_id"], genres)
        if result is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(
                    500,
                    "Internal Server Error",
                    "Failed to save genre preferences",
                    "/preferences/genres"
                )
            )

        logger.info(f"Saved genres for user {user['user_id']}: {genres}")

        return JSONResponse(
            status_code=200,
            content={
                "message": "Genres saved successfully",
                "genres": genres
            }
        )

    except Exception as e:
        logger.error(f"Failed to save genres for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                "/preferences/genres"
            )
        )


@router.post(
    "/preferences/artists",
    responses={
        200: {
            "description": "Successfully set artist preferences",
            "content": {
                "application/json": {
                    "examples": {
                        "ok": {
                            "summary": "Artists saved",
                            "value": {
                                "message": "Artists saved successfully",
                                "genres": ["The Strokes", "Daft Punk"]
                            }
                        }
                    }
                }
            }
        }
    }
)
async def set_artist_preferences(request: schemas.setArtistsRequest, user: dict = Depends(verify_token)):
    """
    Save up to 5 selected artists for the current user.
    """
    try:
        artists = request.data

        if not isinstance(artists, list):
            raise ValueError("Field 'data' must be a list of artists.")

        if len(artists) > 5:
            raise ValueError("You can select up to 5 artists.")

        result = await preferences_db.set_user_artists(user["user_id"], artists)
        if result is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(
                    500,
                    "Internal Server Error",
                    "Failed to save artist preferences",
                    "/preferences/artists"
                )
            )

        logger.info(f"Saved artists for user {user['user_id']}: {artists}")

        return JSONResponse(
            status_code=200,
            content={
                "message": "Artists saved successfully",
                "artists": artists
            }
        )

    except Exception as e:
        logger.error(f"Failed to save artists for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400,
                "Bad Request",
                str(e),
                "/preferences/artists"
            )
        )


@router.get(
    "/preferences/genres",
    responses={
        200: {
            "description": "Successfully retrieved genre preferences",
            "content": {
                "application/json": {
                    "example": {
                        "genres": ["rock", "jazz", "metal"]
                    }
                }
            }
        }
    }
)
async def get_genre_preferences(user: dict = Depends(verify_token)):
    user_id = user["user_id"]

    genres = await preferences_db.get_user_genres(user_id)
    if genres is None:
        return {"error": "Failed to retrieve preferences"}

    return {"genres": genres}


@router.get(
    "/preferences/artists",
    responses={
        200: {
            "description": "Successfully retrieved artist preferences",
            "content": {
                "application/json": {
                    "example": {
                        "artists": ["The Strokes", "Daft Punk"]
                    }
                }
            }
        }
    }
)
async def get_artist_preferences(user: dict = Depends(verify_token)):
    user_id = user["user_id"]

    artists = await preferences_db.get_user_artists(user_id)
    if artists is None:
        return {"error": "Failed to retrieve preferences"}

    return {"artists": artists}
