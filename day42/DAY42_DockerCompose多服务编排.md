# DAY 42：docker-compose 多服务编排

**目标**：用 docker-compose 同时管理 FastAPI + PostgreSQL + Redis 三个服务。

---

## 1. 为什么需要 docker-compose

Dockerfile 只能构建**一个**容器。而生产环境需要：
- FastAPI 应用容器
- PostgreSQL 数据库容器
- Redis 容器（后面做限流用）

docker-compose 用一个 YAML 文件定义所有容器、网络和数据卷，一条命令全部启动。

---

## 2. 修改 database.py 支持容器环境

`deploy/database.py`：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.POOL_SIZE,
    max_overflow=settings.MAX_OVERFLOW,
    pool_timeout=30,
    pool_pre_ping=True,   # Docker 环境必备
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass
```

> `pool_pre_ping=True` 让每次连接前先 ping，确保连接有效——容器环境下 PostgreSQL 可能重启导致旧连接失效。

---

## 3. 修改 main.py 的启动逻辑

容器环境下数据库可能还没初始化好。修改 `deploy/main.py`：

```python
import time
from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import engine, Base, SessionLocal
# ... 其他 import 保持不变

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时等待数据库就绪，然后建表"""
    max_retries = 10
    for i in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            print(f"✅ 数据库已就绪，环境：{settings.APP_ENV}")
            break
        except Exception as e:
            if i == max_retries - 1:
                raise
            print(f"⏳ 等待数据库启动... ({i+1}/{max_retries})")
            time.sleep(3)
    yield

app = FastAPI(title="AI 对话 API", lifespan=lifespan)
# ... 其余路由保持不变
```

---

## 4. 写 docker-compose.yml

在 `deploy/` 目录下新建 `docker-compose.yml`：

```yaml
version: "3.9"

services:
  # ── PostgreSQL 数据库 ─────────────────────
  db:
    image: postgres:16-alpine
    container_name: myapp_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: chat_db
      POSTGRES_USER: chat_user
      POSTGRES_PASSWORD: 你的数据库密码
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5433:5432"     # 映射到 5433 避免和本地 PostgreSQL 冲突
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U chat_user -d chat_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ── Redis 缓存/限流 ──────────────────────
  redis:
    image: redis:7-alpine
    container_name: myapp_redis
    restart: unless-stopped
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # ── FastAPI 应用 ─────────────────────────
  api:
    build: .
    container_name: myapp_api
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env.prod
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - uploads:/app/uploads

volumes:
  pgdata:
  redisdata:
  uploads:
```

---

## 5. 更新 .env.prod

关键：DATABASE_URL 中的主机名要用 docker-compose 的服务名 `db`：

```
APP_ENV=prod
DEBUG=false
DATABASE_URL=postgresql://chat_user:你的数据库密码@db:5432/chat_db
SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DEEPSEEK_API_KEY=sk-你的DeepSeekKey
DEFAULT_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com
ALLOWED_ORIGINS=http://localhost:3000
```

生成随机 SECRET_KEY：
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 6. 启动全部服务

```bash
cd D:\AI相关\文件总集\开发学习\deploy

# 启动（首次会自动构建镜像）
docker compose up -d

# 查看运行状态
docker compose ps
# 期望：三个服务都是 Up 状态

# 查看 API 日志
docker compose logs -f api

# 测试健康检查
curl http://localhost:8000/health
```

---

## 7. 初始化数据库

```bash
docker compose exec api python -c "from database import engine, Base; Base.metadata.create_all(bind=engine); print('建表完成')"
```

---

## 常见问题

| 问题 | 解决 |
|------|------|
| `docker-compose` 命令不存在 | 用 `docker compose`（无横线） |
| db 容器反复重启 | `docker compose logs db` 查看，通常是端口冲突 |
| api 连不上 db | 确认 DATABASE_URL 里主机名是 `db` 不是 `localhost` |
