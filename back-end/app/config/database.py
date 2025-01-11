import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from app.constants.constants import DATABASE_NAME, PAYMENTS_COLLECTION, \
    EVIDENCE_COLLECTION

load_dotenv()


def get_database():
    """
    Establish a connection to the MongoDB database.

    Returns:
        Database: A MongoDB database instance.
    Raises:
        ValueError: If the connection string is not found in environment\
            variables.
        PyMongoError: If unable to connect to the MongoDB server.
    """
    try:
        CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")

        if not CONNECTION_STRING:
            raise ValueError(
                "Connection string not found in environment variables")

        # Now connect to MongoDB using the connection string
        client = MongoClient(CONNECTION_STRING)

        # Return the "billpilot" database
        return client.get_database(DATABASE_NAME)
    except PyMongoError as e:
        print("Failed to connect to MongoDB:", e)
        raise


# Get the database instance
db = get_database()

# Available collections
payments_collection = db[PAYMENTS_COLLECTION]
evidence_collection = db[EVIDENCE_COLLECTION]
