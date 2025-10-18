import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")


class Supabase:
    _client = None
    
    @classmethod
    def initialize(cls):
        """Initialize the database connection pool at application startup."""
        if cls._client is None:
            cls._client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    @classmethod
    def get_client(cls):
        """Get database instance. Raises exception if not initialized."""
        if cls._client is None:
            raise RuntimeError("Database not initialized. Call Supabase.initialize() first.")
        return cls._client

def get_client():
    return Supabase.get_client()
    