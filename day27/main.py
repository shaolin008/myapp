# main.py

from fastapi import FastAPI, HTTPException,Depends
from contextlib import asynccontextmanager
from database import engine, Base,SessionLocal
from schemas import ChatRequest, ChatResponse, HistoryResponse, MessageOut,RegisterRequest, LoginRequest, UserOut,LoginResponse, TokenResponse
from crud import (get_or_create_conversation, append_messages,
                  get_history, get_full_history_for_ai,
                  delete_conversation, list_all_conversations,
                  get_user_by_email, create_user, authenticate_user)
from ai import chat_with_ai
from auth import create_access_token, get_current_user
from config import settings
from models import User

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)   # 启动时确保表存在
    yield

app = FastAPI(title="AI 对话 API", lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user)   # 加这一行
):
    # current_user 就是当前登录的用户对象，可以直接用
    conv_id = get_or_create_conversation(req.session_id, req.model)
    history = get_full_history_for_ai(conv_id)
    history.append({"role": "user", "content": req.message})
    result = chat_with_ai(history, req.model)
    append_messages(conv_id, req.message, result["content"],
                    result["token_count"], req.model)
    return ChatResponse(
        session_id=conv_id,
        reply=result["content"],
        token_count=result["token_count"]
    )


@app.post("/register", response_model=UserOut, status_code=201)
def register(req: RegisterRequest):
    """用户注册"""
    # 检查邮箱是否已注册
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    user = create_user(req.email, req.password)
    return user


@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = create_access_token(user.id, user.email)
    return LoginResponse(
        user=UserOut.model_validate(user),
        token=TokenResponse(
            access_token=token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    )

@app.get("/history/{session_id}", response_model=HistoryResponse)
def get_chat_history(
    session_id: int,
    current_user: User = Depends(get_current_user)
):
    conv = get_history(session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    # 确保只能查自己的会话
    if conv.user_id and conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该会话")
    return HistoryResponse(
        session_id=conv.id,
        title=conv.title,
        model_name=conv.model_name,
        messages=[MessageOut.model_validate(m) for m in conv.messages]
    )


@app.delete("/session/{session_id}")
def delete_session(session_id: int):
    """删除会话（级联删除所有消息）"""
    if not delete_conversation(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": f"会话 {session_id} 已删除"}


@app.get("/sessions")
def list_sessions(current_user: User = Depends(get_current_user)):
    with SessionLocal() as db:
        from models import Conversation
        convs = (db.query(Conversation)
                   .filter(Conversation.user_id == current_user.id)
                   .order_by(Conversation.created_at.desc())
                   .all())
        return [{"id": c.id, "title": c.title, "msg_count": len(c.messages)}
                for c in convs]
@app.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user