# auth.py

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings
from crud import get_user_by_id   # 下面会补充这个函数
from models import User

# FastAPI 的 Bearer Token 解析器
bearer_scheme = HTTPBearer()


def create_access_token(user_id: int, email: str) -> str:
    """生成 JWT Token"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),   # subject：标准字段，存用户 id
        "email": email,
        "exp": expire,         # expiration：标准字段，过期时间
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> User:
    """
    FastAPI 依赖项：从请求头解析并验证 Token，返回当前用户
    在需要登录的接口上加 current_user: User = Depends(get_current_user) 即可保护
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token 无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_id(int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    return user