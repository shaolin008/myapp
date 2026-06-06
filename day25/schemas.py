# schemas.py

from pydantic import BaseModel
from datetime import datetime

# ── 请求体 ─────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: int | None = None   # 传 None 表示新建会话，传 id 表示继续已有会话
    message: str
    model: str = "gpt-4o"

# ── 响应体 ─────────────────────────────────────
class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True      # 允许从 SQLAlchemy 对象直接转换

class ChatResponse(BaseModel):
    session_id: int
    reply: str
    token_count: int | None = None

class HistoryResponse(BaseModel):
    session_id: int
    title: str
    model_name: str
    messages: list[MessageOut]