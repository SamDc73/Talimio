from collections.abc import AsyncGenerator

from pydantic_settings import BaseSettings
from surrealdb.clients.http import HTTPClient


class DatabaseSettings(BaseSettings):
    SURREALDB_HOST: str = "127.0.0.1"
    SURREALDB_PORT: int = 8000
    SURREALDB_USER: str = "root"
    SURREALDB_PASS: str = "root"
    SURREALDB_NS: str = "learning_roadmap"
    SURREALDB_DB: str = "learning_roadmap"

    @property
    def url(self) -> str:
        return f"http://{self.SURREALDB_HOST}:{self.SURREALDB_PORT}"

db_settings = DatabaseSettings()
db = HTTPClient(db_settings.url, db_settings.SURREALDB_NS, db_settings.SURREALDB_DB)
db.configure(db_settings.SURREALDB_USER, db_settings.SURREALDB_PASS)

async def get_db() -> AsyncGenerator[HTTPClient, None]:
    try:
        yield db
    finally:
        await db.close()
