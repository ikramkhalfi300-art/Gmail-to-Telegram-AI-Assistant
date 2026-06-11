from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()
DATABASE_URL = "sqlite+aiosqlite:///./email_assistant.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():

    from app.models.user import User
    from app.models.email import Email
    from app.models.draft import Draft

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)