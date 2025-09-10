import os
import logging
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import asyncio
from typing import AsyncGenerator


logger = logging.getLogger(__name__)
load_dotenv()

URI_TEST = os.getenv("URI_TEST")          # ej: mongodb://user:pass@mongodb:27017/?authSource=admin
MONGO_DB_NAME = os.getenv("MONGO_INITDB_DATABASE", "userdb")       # ej: userdb

mongo_client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None

async def init_db():
    """
    Inicializa el cliente de Mongo y expone la DB global `db`.
    Realiza un ping para confirmar conectividad.
    """
    global mongo_client, db
    if mongo_client is None:
        mongo_client = AsyncIOMotorClient(
            URI_TEST,
            serverSelectionTimeoutMS=int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")),
            maxPoolSize=int(os.getenv("MONGO_MAX_POOL_SIZE", "20")),
            minPoolSize=int(os.getenv("MONGO_MIN_POOL_SIZE", "0")),
            retryWrites=True,
        )
        db = mongo_client[MONGO_DB_NAME]
        # Verifica conectividad
        await db.command("ping")
    return db

async def close_db():
    """
    Cierra el cliente de Mongo (llamar en shutdown de la app).
    """
    global mongo_client
    if mongo_client is not None:
        mongo_client.close()
        mongo_client = None

async def wait_for_db(max_retries: int = 30, delay: float = 1.0) -> bool:
    """
    Espera a que MongoDB esté disponible haciendo un `ping` con reintentos.
    Útil en entornos con arranque orquestado (Docker Compose/K8s).
    """
    logger.info(f"Waiting for MongoDB (max_retries={max_retries}, delay={delay}s)")
    retries = 0
    while retries < max_retries:
        try:
            await init_db()
            assert db is not None
            await db.command("ping")
            logger.info("MongoDB connection successful!")
            return True
        except Exception as e:
            retries += 1
            logger.warning(f"Mongo not ready (attempt {retries}/{max_retries}): {e}")
            if retries >= max_retries:
                logger.error("Failed to connect to Mongo after maximum retries")
                raise
            await asyncio.sleep(delay)
    return False


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    Dependencia de FastAPI que entrega la base de datos.
    No crea/cierra 'sesiones' por request; simplemente asegura que la DB exista.
    """
    await init_db()
    yield db  # type: ignore[misc]