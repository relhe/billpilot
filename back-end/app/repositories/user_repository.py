from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from passlib.context import CryptContext

from app.repositories.base import BaseRepository

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "users")

    async def get_by_username(self, username: str) -> dict | None:
        return await self._col.find_one({"username": username})

    async def create(self, username: str, plain_password: str) -> str:
        doc = {
            "username": username,
            "hashed_password": _pwd_ctx.hash(plain_password),
            "created_at": datetime.now(timezone.utc),
        }
        result = await self._col.insert_one(doc)
        return str(result.inserted_id)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return _pwd_ctx.verify(plain, hashed)
