# schemas.py

from pydantic import BaseModel,EmailStr,field_validator
from datetime import datetime

# ── 请求体 ─────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: int | None = None   # 传 None 表示新建会话，传 id 表示继续已有会话
    message: str
    model: str = "moonshot-v1-8k"

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

# schemas.py —— 新增用户部分



# ── 用户注册请求 ───────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    # 密码强度校验
    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("密码至少 8 位")
        return v

# ── 登录请求 ───────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# ── 用户信息响应（不含密码）────────────────────
class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime

    class Config:
     from_attributes = True
# schemas.py —— 新增

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int   # 过期时间（秒）

class LoginResponse(BaseModel):
    user: UserOut
    token: TokenResponse

# schemas.py —— 新增

class UserListItem(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class SetRoleRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ("user", "admin"):
            raise ValueError("角色只能是 user 或 admin")
        return v











