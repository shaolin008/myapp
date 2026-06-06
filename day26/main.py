# main.py

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from database import engine, Base
from schemas import ChatRequest, ChatResponse, HistoryResponse, MessageOut,RegisterRequest, LoginRequest, UserOut
from crud import (get_or_create_conversation, append_messages,
                  get_history, get_full_history_for_ai,
                  delete_conversation, list_all_conversations,
                  get_user_by_email, create_user, authenticate_user)
from ai import chat_with_ai

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)   # 启动时确保表存在
    yield

app = FastAPI(title="AI 对话 API", lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """发送消息，自动保存对话历史"""
    # 1. 获取或新建会话
    conv_id = get_or_create_conversation(req.session_id, req.model)

    # 2. 拼上历史，发给 AI
    history = get_full_history_for_ai(conv_id)
    history.append({"role": "user", "content": req.message})
    result = chat_with_ai(history, req.model)

    # 3. 存入数据库
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


@app.post("/login", response_model=UserOut)
def login(req: LoginRequest):
    """用户登录（今天先返回用户信息，明天 DAY 27 加 JWT Token）"""
    user = authenticate_user(req.email, req.password)
    if not user:
        # 故意不区分"邮箱不存在"和"密码错误"
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    return user

@app.get("/history/{session_id}", response_model=HistoryResponse)
def get_chat_history(session_id: int):
    """查询某会话的完整历史"""
    conv = get_history(session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
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
def list_sessions():
    """列出所有会话"""
    return list_all_conversations()