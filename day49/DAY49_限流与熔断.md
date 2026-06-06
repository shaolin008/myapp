# DAY 49：限流 + 熔断保护

**目标**：防止恶意调用或突发流量打垮你的服务。

---

## 1. 安装依赖

在 `deploy/requirements.txt` 添加：

```
slowapi==0.1.9
redis==5.2.1
httpx==0.28.1
```

重新构建：
```bash
docker compose build api
```

---

## 2. 全局限流

在 `deploy/main.py` 中添加：

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

# 用 Redis 做后端（多容器共享计数）
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://redis:6379/0"
)

app = FastAPI(title="AI 对话 API", lifespan=lifespan)
app.state.limiter = limiter

# 限流超限时的友好响应
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "请求太频繁，请稍后再试", "retry_after": "60秒"}
    )
```

---

## 3. 对不同接口设置不同限制

```python
# 健康检查：不限制
@app.get("/health")
def health_check():
    return {"status": "ok"}

# 注册：每分钟最多 3 次（防批量注册）
@app.post("/register")
@limiter.limit("3/minute")
def register(req: RegisterRequest):
    ...

# 登录：每分钟最多 10 次（防暴力破解）
@app.post("/login")
@limiter.limit("10/minute")
def login(req: LoginRequest):
    ...

# AI 对话：每分钟最多 20 次（DeepSeek API 也有频率限制）
@app.post("/chat")
@limiter.limit("20/minute")
def chat(req: ChatRequest, current_user=Depends(get_current_user)):
    ...
```

---

## 4. 熔断器（保护 DeepSeek API 调用）

改造 `deploy/ai.py`：

```python
from openai import OpenAI
from config import settings
import logging

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    timeout=30.0,        # 30 秒超时
    max_retries=2,       # 最多重试 2 次
)

def chat_with_ai(history: list[dict], model: str | None = None) -> dict:
    model = model or settings.DEFAULT_MODEL
    try:
        response = client.chat.completions.create(
            model=model,
            messages=history,
            max_tokens=1000,
        )
        return {
            "content": response.choices[0].message.content,
            "token_count": response.usage.total_tokens,
        }
    except Exception as e:
        logger.error(f"AI API 调用失败: {type(e).__name__}: {e}")
        return {
            "content": f"AI 服务暂时不可用，请稍后重试。（错误：{type(e).__name__}）",
            "token_count": 0,
        }
```

---

## 5. 验证

```bash
# 连续快速发 5 个注册请求
for i in $(seq 1 5); do
  curl -s -X POST http://localhost/register \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"test$i@test.com\",\"password\":\"Test123\"}" &
done
wait
# 第 4、5 个应该返回 429 Too Many Requests
```
