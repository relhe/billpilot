from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


class BaseRepository:
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self._col = db[collection_name]

    @staticmethod
    def to_object_id(id_str: str) -> ObjectId | None:
        if ObjectId.is_valid(id_str):
            return ObjectId(id_str)
        return None
