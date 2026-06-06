# crud.py

from database import SessionLocal, engine, Base
from models import Conversation, Message

# 第一次运行时创建所有表（相当于执行 CREATE TABLE）
Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库 session，用完自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── 新建会话 + 批量插入消息 ──────────────────────
def save_conversation(title: str, model: str, messages: list[dict]) -> int:
    with SessionLocal() as db:
        conv = Conversation(title=title, model_name=model)
        db.add(conv)
        db.flush()          # 让数据库分配 id，但还没 commit

        for m in messages:
            db.add(Message(
                conversation_id=conv.id,
                role=m["role"],
                content=m["content"]
            ))

        db.commit()
        db.refresh(conv)    # 刷新对象，确保 id 等字段已填充
        return conv.id


# ── 查询某会话历史（OpenAI API 兼容格式）────────
def get_history(conv_id: int) -> list[dict]:
    with SessionLocal() as db:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if not conv:
            return []
        # 直接用 relationship，无需手写 JOIN
        return [{"role": m.role, "content": m.content} for m in conv.messages]


# ── 列出所有会话（附消息条数）──────────────────
def list_conversations():
    with SessionLocal() as db:
        convs = db.query(Conversation).order_by(Conversation.created_at.desc()).all()
        return [
            {
                "id":        c.id,
                "title":     c.title,
                "model":     c.model_name,
                "msg_count": len(c.messages),
            }
            for c in convs
        ]


# ── 更新会话标题 ────────────────────────────────
def update_title(conv_id: int, new_title: str) -> bool:
    with SessionLocal() as db:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if not conv:
            return False
        conv.title = new_title   # 直接赋值，ORM 自动追踪变更
        db.commit()
        return True


# ── 删除会话（cascade 自动删关联消息）──────────
def delete_conversation(conv_id: int) -> bool:
    with SessionLocal() as db:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if not conv:
            return False
        db.delete(conv)
        db.commit()
        return True