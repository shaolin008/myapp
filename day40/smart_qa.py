import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day31'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day34'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day35'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day37'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day39'))

from dotenv import load_dotenv
load_dotenv()

import json
import psycopg2
import uvicorn
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from openai import OpenAI
from document_loader import ingest_file, init_table
from hybrid_search import hybrid_search
from multi_tool_agent import ALL_TOOLS, call_all_tools

# ── 初始化 ────────────────────────────────────────

app = FastAPI(title="智能问答系统", version="1.0.0")
security = HTTPBearer()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

def get_conn():
    return psycopg2.connect(
        "postgresql://chat_user:188160@localhost:5432/chat_db"
    )


# ── JWT 验证（复用模块A） ─────────────────────────

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证模块A颁发的 JWT Token"""
    import jwt
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET", "your_jwt_secret"),
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token 无效")


# ── 会话历史存储 ──────────────────────────────────

def save_message(session_id: str, role: str, content: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO messages (session_id, role, content, created_at)
                VALUES (%s, %s, %s, %s)
            """, (session_id, role, content, datetime.now()))
        conn.commit()


def get_history(session_id: str, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, content FROM messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (session_id, limit))
            rows = cur.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


# ── 核心 Agent ────────────────────────────────────

SYSTEM_PROMPT = """你是一个智能问答助手，具备以下能力：
1. 搜索知识库回答专业问题
2. 进行数学计算
3. 获取当前时间
4. 读写文件

回答原则：
- 优先从知识库检索答案
- 知识库没有时，用自身知识回答并说明
- 回答简洁清晰，重点突出
- 不确定时主动说明"""


def run_agent(user_message: str, history: list[dict], max_steps: int = 5) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    for _ in range(max_steps):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content

        messages.append(msg)
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            result = call_all_tools(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return "处理超时，请简化问题重试"


# ── API 接口 ──────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    timestamp: str


@app.on_event("startup")
async def startup():
    init_table()
    # 创建会话历史表
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS messages CASCADE;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id         SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, created_at);
            """)
        conn.commit()
    print("智能问答系统已就绪")


@app.post("/qa/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user=Depends(verify_token)):
    """带身份验证的智能问答接口"""
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")

    # 读取历史
    history = get_history(req.session_id)

    # 运行 Agent
    answer = run_agent(req.message, history)

    # 保存对话
    save_message(req.session_id, "user", req.message)
    save_message(req.session_id, "assistant", answer)

    return ChatResponse(
        session_id=req.session_id,
        answer=answer,
        timestamp=datetime.now().isoformat(),
    )


@app.post("/qa/chat/public", response_model=ChatResponse)
async def chat_public(req: ChatRequest):
    """无需登录的公开问答接口（演示用）"""
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")

    history = get_history(req.session_id)
    answer = run_agent(req.message, history)
    save_message(req.session_id, "user", req.message)
    save_message(req.session_id, "assistant", answer)

    return ChatResponse(
        session_id=req.session_id,
        answer=answer,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/qa/history/{session_id}")
async def get_chat_history(session_id: str):
    """获取会话历史"""
    history = get_history(session_id, limit=20)
    return {"session_id": session_id, "messages": history}


@app.get("/qa/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)