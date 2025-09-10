from fastapi import FastAPI, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from datetime import datetime, timezone
import uvicorn
import os
from dotenv import load_dotenv
from db import models
import schemas
from db.database import engine, get_db, wait_for_db
from resources.logger import logger, LOGGING_CONFIG

from controllers import songs_controller
from controllers import playlists_controller

from common.utils import create_error_response

logger.info("Load configurations")
load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

logger.info("Waiting for database")
wait_for_db()
logger.info("Creating database tables if they don't exist")
models.Base.metadata.create_all(bind=engine)
logger.info("Database initialization complete")

logger.info("Initializing FastAPI application")
app = FastAPI(title="Melodia API", version="1.0.0")
logger.info("FastAPI application initialized")

app.include_router(songs_controller.router, prefix="/songs", tags=["songs"])
app.include_router(playlists_controller.router, prefix="/playlists", tags=["playlists"])

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Global exception handler for FastAPI request validation errors.
    
    This handler catches all RequestValidationError exceptions thrown by FastAPI
    when request data fails Pydantic validation. It logs the validation errors
    and returns a standardized 400 Bad Request response.
    """
    logger.warning(
        f"Request validation error on {request.method} {request.url.path}: {exc.errors()}"
    )
    logger.debug(f"Request validation details: {exc}")
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
