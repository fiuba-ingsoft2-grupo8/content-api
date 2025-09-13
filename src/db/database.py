import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "")

def get_db():
    client = MongoClient(MONGO_URL)
    return client.content_db
    