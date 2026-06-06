# database.py —— 整个项目只需要这一个配置文件

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
# SQLite 路径，明天切换 PostgreSQL 只改这一行
DATABASE_URL = "postgresql://chat_user:yourpassword@localhost:5432/chat_db"

engine = create_engine(
    DATABASE_URL,
    # PostgreSQL 不需要 check_same_thread，把它去掉
    pool_size=5,           # 连接池保持 5 个常驻连接
    max_overflow=10,       # 高峰期最多额外开 10 个连接
    pool_timeout=30,       # 等待连接超过 30 秒就报错
    pool_pre_ping=True,    # 每次取连接前先 ping 一下，自动剔除断连
    echo=False             # 改成 True 可以看到所有 SQL 日志，调试用
)


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass