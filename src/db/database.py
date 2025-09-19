import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("DATABASE_URL", "")

class Database:
    _client = None
    _db = None
    
    @classmethod
    def initialize(cls):
        """Initialize the database connection pool at application startup."""
        if cls._client is None:
            cls._client = MongoClient(
                MONGO_URL,
                maxPoolSize=50,          # Maximum number of connections in the pool
                minPoolSize=5,           # Minimum number of connections in the pool
                maxIdleTimeMS=30000,     # Close connections after 30 seconds of inactivity
                serverSelectionTimeoutMS=5000,  # 5 second timeout for server selection
                connectTimeoutMS=10000,  # 10 second timeout for initial connection
                socketTimeoutMS=20000,   # 20 second timeout for socket operations
            )
            cls._db = cls._client.content_db
            print("Database connection pool initialized")
    
    @classmethod
    def get_db(cls):
        """Get database instance. Raises exception if not initialized."""
        if cls._db is None:
            raise RuntimeError("Database not initialized. Call Database.initialize() first.")
        return cls._db
    
    @classmethod
    def close(cls):
        """Close the database connection pool."""
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db = None
            print("Database connection pool closed")

def get_db():
    return Database.get_db()
    