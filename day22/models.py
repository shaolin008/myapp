# models.py

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Conversation(Base):
    __tablename__ = "conversations"          # 对应数据库表名

    id         = Column(Integer, primary_key=True, index=True)
    title      = Column(String(200), nullable=False, default="新对话")
    model_name = Column(String(50),  nullable=False, default="gpt-4o")
    created_at = Column(DateTime, server_default=func.now())

    # relationship：让 Python 对象能直接访问关联的消息列表
    # cascade="all, delete-orphan" 对应 SQL 的 ON DELETE CASCADE
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id"
    )

    def __repr__(self):
        return f"<Conversation id={self.id} title='{self.title}'>"


class Message(Base):
    __tablename__ = "messages"

    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role            = Column(String(20), nullable=False)   # user / assistant / system
    content         = Column(Text, nullable=False)
    created_at      = Column(DateTime, server_default=func.now())

    # back_populates 建立双向引用：message.conversation 可以拿到父会话
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message role={self.role} content='{self.content[:20]}...'>"