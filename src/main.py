import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from resources.logger import logger, LOGGING_CONFIG
from controllers import songs_controller, playlists_controller
from common.utils import create_error_response

logger.info("Load configurations")
load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

logger.info("Initializing FastAPI application")
app = FastAPI(title="Melodia API", version="1.0.0")
logger.info("FastAPI application initialized")

# Routers
app.include_router(songs_controller.router, prefix="/songs", tags=["songs"])
app.include_router(playlists_controller.router, prefix="/playlists", tags=["playlists"])

# Global validation handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Request validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=400,
        content=create_error_response(
            status_code=400,
            title="Bad Request",
            detail="Invalid request body",
            instance=str(request.url.path),
        ),
    )

if __name__ == "__main__":
    logger.info("Starting Fast API")
    uvicorn.run(app, host=HOST, port=PORT, log_config=LOGGING_CONFIG)