# crud.py
# crud.py（完整版）

from sqlalchemy.orm import Session,joinedload
from database import SessionLocal
from models import Conversation, Message,User
from security import hash_password, verify_password

def get_or_create_conversation(session_id: int | None, model: str) -> int:
    """有 session_id 就复用，没有就新建"""
    with SessionLocal() as db:
        if session_id:
            conv = db.query(Conversation).filter(Conversation.id == session_id).first()
            if conv:
                return conv.id
        # 新建
        conv = Conversation(title="新对话", model_name=model)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv.id


def append_messages(conv_id: int, user_msg: str, ai_reply: str,
                    token_count: int | None, model: str):
    """把用户消息和 AI 回复一起存入数据库"""
    with SessionLocal() as db:
        db.add(Message(
            conversation_id=conv_id,
            role="user",
            content=user_msg,
            model_name=model
        ))
        db.add(Message(
            conversation_id=conv_id,
            role="assistant",
            content=ai_reply,
            token_count=token_count,
            model_name=model
        ))
        # 第一条消息时，用消息内容前 20 字作为会话标题
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if conv and conv.title == "新对话":
            conv.title = user_msg[:20] + ("..." if len(user_msg) > 20 else "")
        db.commit()


def get_history(conv_id: int) -> Conversation | None:
    """查询完整会话（含所有消息）"""
    with SessionLocal() as db:
        # expire_on_commit=False 防止 session 关闭后对象失效
        db.expire_on_commit = False
        return (db.query(Conversation)
                .options(joinedload(Conversation.messages))
                .filter(Conversation.id == conv_id)
                .first())


def get_full_history_for_ai(conv_id: int) -> list[dict]:
    """返回 OpenAI API 兼容格式的历史消息"""
    with SessionLocal() as db:
        msgs = (db.query(Message)
                  .filter(Message.conversation_id == conv_id)
                  .order_by(Message.id)
                  .all())
        return [{"role": m.role, "content": m.content} for m in msgs]


def delete_conversation(conv_id: int) -> bool:
    with SessionLocal() as db:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if not conv:
            return False
        db.delete(conv)
        db.commit()
        return True


def list_all_conversations() -> list[dict]:
    with SessionLocal() as db:
        convs = (db.query(Conversation)
                   .order_by(Conversation.created_at.desc())
                   .all())
        return [
            {"id": c.id, "title": c.title,
             "model": c.model_name, "msg_count": len(c.messages)}
            for c in convs
        ]

def get_user_by_email(email: str) -> User | None:
    """按邮箱查用户，注册去重和登录验证都用它"""
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).first()


def create_user(email: str, password: str) -> User:
    """注册新用户，密码自动哈希"""
    with SessionLocal() as db:
        user = User(
            email=email,
            hashed_password=hash_password(password)  # 明文密码在这里变成哈希
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def authenticate_user(email: str, password: str) -> User | None:
    """
    登录验证：
    - 邮箱不存在 → 返回 None
    - 密码错误   → 返回 None
    - 验证通过   → 返回 User 对象
    两种失败情况故意返回同样的结果，防止攻击者通过错误信息判断邮箱是否注册过
    """
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user