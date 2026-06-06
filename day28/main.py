# main.py

from fastapi import FastAPI, HTTPException,Depends
from contextlib import asynccontextmanager
from database import engine, Base,SessionLocal
from schemas import ChatRequest, ChatResponse, HistoryResponse, MessageOut,RegisterRequest, LoginRequest, UserOut,LoginResponse, TokenResponse,UserListItem, SetRoleRequest
from crud import (get_or_create_conversation, append_messages,
                  get_history, get_full_history_for_ai,
                  delete_conversation, list_all_conversations,list_all_users,
                  get_user_by_email, create_user, authenticate_user,set_user_active, set_user_role, delete_user)
from ai import chat_with_ai
from auth import create_access_token, get_current_user
from config import settings
from models import User
from auth import require_admin

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
# ── 管理员：查看所有用户 ──────────────────────
@app.get("/admin/users", response_model=list[UserListItem])
def admin_list_users(
    admin: User = Depends(require_admin)   # 只需这一行，非管理员自动 403
):
    return list_all_users()


# ── 管理员：修改用户角色 ──────────────────────
@app.patch("/admin/users/{user_id}/role")
def admin_set_role(
    user_id: int,
    req: SetRoleRequest,
    admin: User = Depends(require_admin)
):
    # 防止管理员降低自己的权限
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    user = set_user_role(user_id, req.role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User {user.email} role updated to {user.role} successfully"}


# ── 管理员：禁用/启用用户 ─────────────────────
@app.patch("/admin/users/{user_id}/active")
def admin_set_active(
    user_id: int,
    is_active: bool,
    admin: User = Depends(require_admin)
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    user = set_user_active(user_id, is_active)
    if not user:
        raise HTTPException(status_code=404, detail="User does not exist")
    status_str = "Enable" if is_active else "Disable"
    return {"message": f"User {user.email} has been{status_str}"}


# ── 管理员：删除用户 ──────────────────────────
@app.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    admin: User = Depends(require_admin)
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    if not delete_user(user_id):
        raise HTTPException(status_code=404, detail="User does not exist")
    return {"message": f"User {user_id} has been deleted"}