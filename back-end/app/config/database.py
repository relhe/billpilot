import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from app.config.settings import config

load_dotenv()

_db_cfg = config["database"]
DATABASE_NAME = _db_cfg["name"]
PAYMENTS_COLLECTION = _db_cfg["collections"]["payments"]
EVIDENCE_COLLECTION = _db_cfg["collections"]["evidence"]


def get_database():
    """
    Establish a connection to the MongoDB database.

    Returns:
        Database: A MongoDB database instance.
    Raises:
        ValueError: If the connection string is not found in environment variables.
        PyMongoError: If unable to connect to the MongoDB server.
    """
    try:
        CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")

        if not CONNECTION_STRING:
            raise ValueError(
                "MONGO_CONNECTION_STRING not found in environment variables")

        client = MongoClient(CONNECTION_STRING)
        return client.get_database(DATABASE_NAME)
    except PyMongoError as e:
        print("Failed to connect to MongoDB:", e)
        raise


db = get_database()

payments_collection = db[PAYMENTS_COLLECTION]
evidence_collection = db[EVIDENCE_COLLECTION]
