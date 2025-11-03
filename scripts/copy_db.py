#!/usr/bin/env python3
"""
Script to copy all data from remote MongoDB to local MongoDB.
Usage: python scripts/copy_db.py
or: make copy
"""

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URLs
REMOTE_URL = os.getenv("DATABASE_URL")
LOCAL_URL = "mongodb://admin:admin_password@localhost:27017/userdb?authSource=admin"

# Database name
DB_NAME = "content_db"

# Collections to copy
COLLECTIONS = [
    "songs",
    "playlists",
    "playlist_songs",
    "collections",
    "collection_songs",
    "likes",
    "shares",
    "plays",
    "history",
    "artist_about"
]

def connect_to_databases():
    """Connect to both remote and local databases."""
    print("🔌 Connecting to databases...")
    
    try:
        # Connect to remote database
        remote_client = MongoClient(REMOTE_URL, serverSelectionTimeoutMS=5000)
        remote_db = remote_client[DB_NAME]
        remote_client.admin.command('ping')
        print(f"✅ Connected to REMOTE database: {REMOTE_URL[:50]}...")
        
        # Connect to local database
        local_client = MongoClient(LOCAL_URL, serverSelectionTimeoutMS=5000)
        local_db = local_client[DB_NAME]
        local_client.admin.command('ping')
        print(f"✅ Connected to LOCAL database: {LOCAL_URL}")
        
        return remote_db, local_db, remote_client, local_client
        
    except Exception as e:
        print(f"❌ Error connecting to databases: {e}")
        print("\n💡 Make sure:")
        print("   1. Your local MongoDB is running (docker compose up)")
        print("   2. Your .env file has the correct DATABASE_URL")
        sys.exit(1)

def copy_collection(remote_db, local_db, collection_name):
    """Copy a single collection from remote to local."""
    try:
        # Get remote collection
        remote_collection = remote_db[collection_name]
        remote_count = remote_collection.count_documents({})
        
        if remote_count == 0:
            print(f"  ⚠️  {collection_name}: No documents found (skipping)")
            return 0
        
        # Get all documents from remote
        documents = list(remote_collection.find({}))
        
        # Drop local collection if it exists
        local_db[collection_name].drop()
        
        # Insert documents into local
        if documents:
            local_db[collection_name].insert_many(documents)
        
        local_count = local_db[collection_name].count_documents({})
        print(f"  ✅ {collection_name}: Copied {local_count} documents")
        
        return local_count
        
    except Exception as e:
        print(f"  ❌ {collection_name}: Error - {e}")
        return 0

def main():
    """Main function to copy all data from remote to local."""
    print("\n" + "="*60)
    print("  📦 MongoDB Database Copy Tool")
    print("  Remote → Local")
    print("="*60 + "\n")
    
    # Connect to databases
    remote_db, local_db, remote_client, local_client = connect_to_databases()
    
    print("\n📋 Starting copy process...\n")
    
    total_copied = 0
    
    # Copy each collection
    for collection_name in COLLECTIONS:
        count = copy_collection(remote_db, local_db, collection_name)
        total_copied += count
    
    # Close connections
    remote_client.close()
    local_client.close()
    
    print("\n" + "="*60)
    print(f"  ✨ Copy completed successfully!")
    print(f"  Total documents copied: {total_copied}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()

