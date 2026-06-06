# security.py

from passlib.context import CryptContext

# 使用 bcrypt 算法，rounds=12 是安全与速度的平衡点
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """注册时调用：把明文密码转成哈希"""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """登录时调用：验证密码是否正确，返回 True/False"""
    return pwd_context.verify(plain_password, hashed_password)