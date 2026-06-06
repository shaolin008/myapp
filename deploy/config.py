# config.py

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── 应用基础 ──────────────────────────────
    APP_ENV: str = "dev"
    DEBUG: bool = False

    # ── 数据库 ────────────────────────────────
    DATABASE_URL: str
    POOL_SIZE: int = 5
    MAX_OVERFLOW: int = 10

    # ── JWT ───────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── OpenAI ────────────────────────────────
    DEEPSEEK_API_KEY: str
    DEFAULT_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # ── 跨域 ──────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        """把逗号分隔的字符串转成列表"""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "prod"

    class Config:
        # 根据 APP_ENV 环境变量决定读哪个文件
        env_file = f".env.{os.getenv('APP_ENV', 'dev')}"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """
    用 lru_cache 缓存 Settings 实例
    整个应用生命周期里只解析一次 .env 文件，不是每次调用都重新读
    """
    return Settings()


# 全局单例，其他模块直接 from config import settings 使用
settings = get_settings()