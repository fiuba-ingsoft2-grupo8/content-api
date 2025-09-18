import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("URI", "")

def get_db():
    client = MongoClient(URI)
    return client.content_db
    