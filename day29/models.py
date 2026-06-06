# models.py

# models.py —— 在原有基础上新增 User 和修改 Conversation

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean,Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class UserRole(enum.Enum):
    user  = "user"
    admin = "admin"

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active       = Column(Boolean, default=True)
    role            = Column(String(20), nullable=False, default="user")  # 新增
    created_at      = Column(DateTime, server_default=func.now())

    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


class Conversation(Base):
    __tablename__ = "conversations"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)  # nullable 兼容旧数据
    title      = Column(String(200), nullable=False, default="新对话")
    model_name = Column(String(50),  nullable=False, default="gpt-4o")
    created_at = Column(DateTime, server_default=func.now())

    user     = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id"
    )


class Message(Base):
    __tablename__ = "messages"

    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role            = Column(String(20),  nullable=False)
    content         = Column(Text,        nullable=False)
    token_count     = Column(Integer,     nullable=True)
    model_name      = Column(String(50),  nullable=True)
    created_at      = Column(DateTime, server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")