import databases.playlists_database as playlists_db
import databases.songs_database as songs_db
import schemas
from fastapi import Body
from fastapi.responses import JSONResponse
from resources.logger import logger
from fastapi import APIRouter
from common.utils import create_error_response, serialize_playlist

router = APIRouter()

# @router.post("/history")
# async def add_to_history(request: schemas.ListeningHistoryRequest):
#     logger.info(f"Adding song with id {request.songId} to user {request.userId}'s listening history")

#     error = await songs_db.add_to_history(request.songId, request.userId)
#     if error:
#         logger.info(f"Failed to log song with id {id} to user {request.userId}'s listening history")
#         return JSONResponse(
#             status_code=400,
#             content=create_error_response(400, "Bad Request", str(error), "/history"),
#         )

#     logger.info(f"Succesfully logged song with id {id} to user {request.userId}'s listening history")
#     return JSONResponse(status_code=201, content={"message": "Added to history"})

# @router.put("/history")
# async def update_song_progress():
#     pass

# @router.get("/history")
# async def get_history():
#     pass

# @router.delete("/history")
# async def clear_history():
#     pass

# @router.put("/history")
# async def pause_history():
#     pass

# @router.get("/history")
# async def filter_history():
#     pass