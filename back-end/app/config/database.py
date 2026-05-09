from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config.settings import Settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db(settings: Settings) -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_connection_string)
    _db = _client[settings.db_name]


async def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None


def get_db() -> AsyncIOMotorDatabase | None:
    return _db
