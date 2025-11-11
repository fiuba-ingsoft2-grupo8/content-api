from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional

import databases.activity_database as activity_db
import schemas
from auth import verify_token
from common.utils import create_error_response
from resources.logger import logger

router = APIRouter()


@router.get("/{user_id}")
async def get_user_activity(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of activities to return"),
    user: dict = Depends(verify_token)
):
    try:
        logger.info(f"Fetching activity for user {user_id} (limit={limit})")
        
        # Get activities
        activities = await activity_db.get_user_activity(user_id, limit)
        
        # Enrich with full details
        enriched_activities = await activity_db.enrich_activity_with_details(activities)
        
        logger.info(f"Successfully retrieved {len(enriched_activities)} activities for user {user_id}")
        return {"data": enriched_activities}
        
    except Exception as e:
        logger.error(f"Failed to fetch activity for user {user_id}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), f"/activity/{user_id}"
            ),
        )


@router.get("/")
async def get_following_activity(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of activities to return"),
    user: dict = Depends(verify_token)
):
    try:
        user_id = user["user_id"]
        logger.info(f"Fetching following activity feed for user {user_id} (limit={limit})")
        
        # Get activities from followed users
        activities = await activity_db.get_following_activity(user_id, limit)
        
        # Enrich with full details
        enriched_activities = await activity_db.enrich_activity_with_details(activities)
        
        logger.info(f"Successfully retrieved {len(enriched_activities)} activities for user {user_id}'s feed")
        return {"data": enriched_activities}
        
    except Exception as e:
        logger.error(f"Failed to fetch following activity feed for user {user['user_id']}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(
                400, "Bad Request", str(e), "/activity"
            ),
        )

