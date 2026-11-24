
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "fd_rate_limiter")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is missing from your .env file")

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=10000,
)

# Verify the connection when the application starts.
client.admin.command("ping")

db = client[DATABASE_NAME]

token_buckets = db["token_buckets"]

# Remove expired documents automatically.
token_buckets.create_index(
    [("expires_at", ASCENDING)],
    expireAfterSeconds=0,
)

print("MongoDB connected successfully!")
print(f"Database: {DATABASE_NAME}")
