from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
DATABASE_NAME = os.getenv("DATABASE_NAME", "postgres")
DATABASE_PORT = os.getenv("DATABASE_PORT", "5432")
DATABASE_USER = os.getenv("DATABASE_USER", "postgres")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "password")

DATABASE_URL = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300, echo=False, pool_size=5, max_overflow=0, connect_args={"sslmode": "require"})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def wait_for_db(max_retries=30, delay=1):
    """
    Wait for the database to become available by attempting connections.
    
    This function implements a retry mechanism to wait for the database to be ready,
    which is particularly useful in containerized environments where the database
    service might not be immediately available when the application starts.
    """
    logger.info(
        f"Waiting for database connection (max_retries={max_retries}, delay={delay}s)"
    )
    retries = 0
    while retries < max_retries:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("Database connection successful!")
                return True
        except Exception as e:
            retries += 1
            logger.warning(f"Database not ready (attempt {retries}/{max_retries}): {e}")
            if retries >= max_retries:
                logger.error("Failed to connect to database after maximum retries")
                raise e
            time.sleep(delay)
    return False


def get_db():
    """
    Create and manage a database session for dependency injection.
    
    This function serves as a FastAPI dependency that provides database sessions
    to API endpoints. It ensures proper session lifecycle management including
    creation, error handling, and cleanup.
    """
    logger.debug("Creating database session")
    db = SessionLocal()
    try:
        yield db
        logger.debug("Database session completed successfully")
    except Exception as e:
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()
        logger.debug("Database session closed")
