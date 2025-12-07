import asyncio
import os
from database import engine, Base

async def recreate_database():
    """Удаляет и пересоздает базу данных"""
    if os.path.exists("script_analyzer.db"):
        os.remove("script_analyzer.db")
        print("🗑️ Старая база данных удалена")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Новая база данных создана с актуальной структурой")

if __name__ == "__main__":
    asyncio.run(recreate_database())