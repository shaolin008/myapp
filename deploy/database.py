# database.py —— 从 settings 读所有参数

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.POOL_SIZE,
    max_overflow=settings.MAX_OVERFLOW,
    pool_timeout=30,
    pool_pre_ping=True,
    echo=settings.DEBUG,        # DEBUG 模式下打印所有 SQL
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass