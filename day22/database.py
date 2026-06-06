# database.py —— 整个项目只需要这一个配置文件

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# SQLite 路径，明天切换 PostgreSQL 只改这一行
DATABASE_URL = "sqlite:///./chat_history.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 特有，多线程安全
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass