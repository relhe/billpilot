import pytest
from unittest.mock import MagicMock, patch


def test_get_db_returns_none_before_connect():
    from app.config import database
    database._db = None
    result = database.get_db()
    assert result is None


@pytest.mark.asyncio
async def test_connect_and_close_db():
    from app.config import database
    from app.config.settings import get_settings
    get_settings.cache_clear()

    mock_client = MagicMock()
    mock_db = MagicMock(name="mock_db")
    mock_client.__getitem__ = MagicMock(return_value=mock_db)

    with patch("app.config.database.AsyncIOMotorClient", return_value=mock_client):
        settings = get_settings()
        await database.connect_db(settings)
        assert database.get_db() is not None
        await database.close_db()
        assert database.get_db() is None
