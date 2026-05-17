import asyncio

from database.db import engine, Base
from database.models import Order, Settings


async def create():

    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )

    print("TABLES CREATED")


asyncio.run(create())