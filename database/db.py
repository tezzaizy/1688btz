from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR}/orders.db"

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)

from sqlalchemy.orm import DeclarativeBase



engine = create_async_engine(
    DATABASE_URL,
    echo=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def init_db():

    # ВАЖНО: импорт моделей внутри функции
    import database.models

    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )


if __name__ == "__main__":

    import asyncio

    asyncio.run(init_db())