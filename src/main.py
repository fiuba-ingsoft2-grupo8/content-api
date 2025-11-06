import os
import sys
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from resources.logger import logger, LOGGING_CONFIG
from controllers import songs_controller, playlists_controller, liked_songs_controller, history_controller, collections_controller, metrics_controller, search_controller, about_controller
from common.utils import create_error_response
from db.database import Database
from db.supabase import Supabase
from auth import verify_token

logger.info("Load configurations")
load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

def is_testing():
    """Check if we're currently running tests."""
    return "pytest" in sys.modules or os.getenv("TESTING") == "true"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup - Skip database initialization during tests
    if not is_testing():
        logger.info("Initializing database connection pool...")
        Database.initialize()
        Supabase.initialize()
        logger.info("Database connection pool initialized successfully")
    else:
        logger.info("Skipping database initialization during tests")
    
    yield
    
    # Shutdown - Skip database cleanup during tests
    if not is_testing():
        logger.info("Closing database connection pool...")
        Database.close()
        logger.info("Database connection pool closed successfully")
    else:
        logger.info("Skipping database cleanup during tests")

logger.info("Initializing FastAPI application")
app = FastAPI(title="Melodia API", version="1.0.0", lifespan=lifespan)
logger.info("FastAPI application initialized")

# Routers
app.include_router(songs_controller.router, prefix="/songs", tags=["songs"])
app.include_router(playlists_controller.router, prefix="/playlists", tags=["playlists"])
app.include_router(liked_songs_controller.router, prefix="/likedSongs", tags=["likedSongs"])
app.include_router(history_controller.router, prefix="/history", tags=["history"])
app.include_router(collections_controller.router, prefix="/collections", tags=["collections"])
app.include_router(search_controller.router, prefix="/search", tags=["search"])
app.include_router(metrics_controller.router, prefix="/metrics", tags=["metrics"])
app.include_router(about_controller.router, prefix="/about", tags=["about"])

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return JSONResponse(status_code=200, content={})

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