# test_postgres.py —— 验证切换成功 + 观察连接池

import time
import threading
from database import engine, SessionLocal, Base
from models import Conversation, Message
from crud import save_conversation, get_history

def simulate_request(user_id: int):
    """模拟一个 API 请求"""
    conv_id = save_conversation(
        title=f"用户{user_id}的对话",
        model="gpt-4o",
        messages=[
            {"role": "user",      "content": f"用户{user_id}：你好"},
            {"role": "assistant", "content": f"你好，用户{user_id}！"},
        ]
    )
    history = get_history(conv_id)
    print(f"[线程{user_id}] 保存成功，id={conv_id}，消息数={len(history)}")

# ── 测试 1：基本连通性 ────────────────────────
print("=== 测试 1：连接 PostgreSQL ===")
with engine.connect() as conn:
    result = conn.execute(__import__('sqlalchemy').text("SELECT version()"))
    print(f"数据库版本：{result.fetchone()[0][:40]}...")

# ── 测试 2：20 个并发请求，观察连接池 ─────────
print("\n=== 测试 2：20 个并发请求 ===")
engine.echo = True   # 开启 SQL 日志，能看到连接复用

threads = [threading.Thread(target=simulate_request, args=(i,)) for i in range(20)]
start = time.time()
for t in threads: t.start()
for t in threads: t.join()
elapsed = time.time() - start

print(f"\n20 个并发请求完成，耗时 {elapsed:.2f}s")
print(f"连接池状态：已用 {engine.pool.checkedout()}，空闲 {engine.pool.checkedin()}")